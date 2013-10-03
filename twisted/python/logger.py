# -*- test-case-name: twisted.python.test.test_logger -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Classes and functions to do granular logging.

Example usage in a module C{some.module}::

    from twisted.python.logger import Logger
    log = Logger()

    def handleData(data):
        log.debug("Got data: {data!r}.", data=data)

Or in a class::

    from twisted.python.logger import Logger

    class Foo(object):
        log = Logger()

        def oops(self, data):
            self.log.error("Oops! Invalid data from server: {data!r}",
                           data=data)

C{Logger}s have namespaces, for which logging can be configured independently.
Namespaces may be specified by passing in a C{namespace} argument to L{Logger}
when instantiating it, but if none is given, the logger will derive its own
namespace by using the module name of the callable that instantiated it, or, in
the case of a class, by using the fully qualified name of the class.

In the first example above, the namespace would be C{some.module}, and in the
second example, it would be C{some.module.Foo}.
"""

__all__ = [
    "InvalidLogLevelError",
    "LogLevel",
    "formatEvent",
    "Logger",
    "LegacyLogger",
    "ILogObserver",
    "LogPublisher",
    "PredicateResult",
    "ILogFilterPredicate",
    "FilteringLogObserver",
    "LogLevelFilterPredicate",
    "FileLogObserver",
    "PythonLogObserver",
    "LegacyLogObserverWrapper",
]



from string import Formatter
from inspect import currentframe
import logging as py_logging
from time import time
from datetime import datetime as DateTime, tzinfo as TZInfo, timedelta as TimeDelta
from collections import deque

from zope.interface import Interface, implementer
from twisted.python.constants import NamedConstant, Names
from twisted.python.util import untilConcludes, OrderedDict
from twisted.python.failure import Failure
from twisted.python.reflect import safe_str, safe_repr

OBSERVER_REMOVED = (
    "Temporarily removing observer {observer} due to exception: {e}"
)

TIME_FORMAT_RFC3339 = "%Y-%m-%dT%H:%M:%S%z"



#
# Log level definitions
#

class InvalidLogLevelError(Exception):
    """
    Someone tried to use a L{LogLevel} that is unknown to the logging system.
    """
    def __init__(self, level):
        """
        @param level: a L{LogLevel}
        """
        super(InvalidLogLevelError, self).__init__(str(level))
        self.level = level



class LogLevel(Names):
    """
    Constants denoting log levels:

     - C{debug}: Information of use to a developer of the software, not
       generally of interest to someone running the software unless they are
       attempting to diagnose a software issue.

     - C{info}: Informational events: Routine information about the status of
       an application, such as incoming connections, startup of a subsystem,
       etc.

     - C{warn}: Warnings events: Events that may require greater attention than
       informational events but are not a systemic failure condition, such as
       authorization failures, bad data from a network client, etc.

     - C{error}: Error conditions: Events indicating a systemic failure, such
       as unhandled exceptions, loss of connectivity to a back-end database,
       etc.
    """
    debug = NamedConstant()
    info  = NamedConstant()
    warn  = NamedConstant()
    error = NamedConstant()

    @classmethod
    def levelWithName(cls, name):
        """
        @param name: the name of a L{LogLevel}

        @return: the L{LogLevel} with the specified C{name}
        """
        try:
            return cls.lookupByName(name)
        except ValueError:
            raise InvalidLogLevelError(name)


    @classmethod
    def _priorityForLevel(cls, constant):
        """
        We want log levels to have defined ordering - the order of definition -
        but they aren't value constants (the only value is the name).  This is
        arguably a bug in Twisted, so this is just a workaround for U{until
        this is fixed in some way
        <https://twistedmatrix.com/trac/ticket/6523>}.
        """
        return cls._levelPriorities[constant]


LogLevel._levelPriorities = dict(
    (constant, idx) for (idx, constant) in
    (enumerate(LogLevel.iterconstants()))
)



#
# Mappings to Python's logging module
#
pythonLogLevelMapping = {
    LogLevel.debug: py_logging.DEBUG,
    LogLevel.info:  py_logging.INFO,
    LogLevel.warn:  py_logging.WARNING,
    LogLevel.error: py_logging.ERROR,
    # LogLevel.critical: py_logging.CRITICAL,
}



##
# Loggers
##

def formatEvent(event):
    """
    Formats an event as a L{unicode}, using the format in
    C{event["log_format"]}.

    This implementation should never raise an exception; if the formatting
    cannot be done, the returned string will describe the event generically so
    that a useful message is emitted regardless.

    @param event: a logging event

    @return: a L{unicode}
    """
    try:
        format = event.get("log_format", None)

        if format is None:
            raise ValueError("No log format provided")

        # Make sure format is unicode.
        if isinstance(format, bytes):
            # If we get bytes, assume it's UTF-8 bytes
            format = format.decode("utf-8")

        elif isinstance(format, unicode):
            pass

        else:
            raise TypeError("Log format must be unicode or bytes, not {0!r}"
                            .format(format))

        return formatWithCall(format, event)

    except Exception as e:
        return formatUnformattableEvent(event, e)



def formatUnformattableEvent(event, error):
    """
    Formats an event as a L{unicode} that describes the event generically and a
    formatting error.

    @param event: a logging event
    @type dict: L{dict}

    @param error: the formatting error
    @type error: L{Exception}

    @return: a L{unicode}
    """
    try:
        return (
            u"Unable to format event {event!r}: {error}"
            .format(event=event, error=error)
        )
    except Exception:
        # Yikes, something really nasty happened.
        #
        # Try to recover as much formattable data as possible; hopefully at
        # least the namespace is sane, which will help you find the offending
        # logger.
        failure = Failure()

        text = ", ".join(" = ".join((safe_repr(key), safe_repr(value)))
                         for key, value in event.items())

        return (
            u"MESSAGE LOST: unformattable object logged: {error}\n"
            u"Recoverable data: {text}\n"
            u"Exception during formatting:\n{failure}"
            .format(error=safe_repr(error), failure=failure, text=text)
        )



class Logger(object):
    """
    Logging object.
    """

    publisher = lambda self, event: None


    @staticmethod
    def _namespaceFromCallingContext():
        """
        Derive a namespace from the module containing the caller's caller.

        @return: a namespace
        """
        return currentframe().f_back.f_back.f_globals["__name__"]


    def __init__(self, namespace=None, source=None):
        """
        @param namespace: The namespace for this logger.  Uses a dotted
            notation, as used by python modules.  If not C{None}, then the name
            of the module of the caller is used.

        @param source: The object which is emitting events to this
            logger; this is automatically set on instances of a class
            if this L{Logger} is an attribute of that class.
        """
        if namespace is None:
            namespace = self._namespaceFromCallingContext()

        self.namespace = namespace
        self.source = source


    def __get__(self, oself, type=None):
        """
        When used as a descriptor, i.e.::

            # athing.py
            class Something(object):
                log = Logger()
                def hello(self):
                    self.log.info("Hello")

        a L{Logger}'s namespace will be set to the name of the class it is
        declared on.  In the above example, the namespace would be
        C{athing.Something}.

        Additionally, it's source will be set to the actual object referring to
        the L{Logger}.  In the above example, C{Something.log.source} would be
        C{Something}, and C{Something().log.source} would be an instance of
        C{Something}.
        """
        if oself is None:
            source = type
        else:
            source = oself

        return self.__class__(
            '.'.join([type.__module__, type.__name__]),
            source
        )


    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.namespace)


    def emit(self, level, format=None, **kwargs):
        """
        Emit a log event to all log observers at the given level.

        @param level: a L{LogLevel}

        @param format: a message format using new-style (PEP 3101)
            formatting.  The logging event (which is a L{dict}) is
            used to render this format string.

        @param kwargs: additional keyword parameters to include with
            the event.
        """
        if level not in LogLevel.iterconstants():
            self.failure(
                "Got invalid log level {invalidLevel!r} in {logger}.emit().",
                Failure(InvalidLogLevelError(level)),
                invalidLevel=level,
                logger=self,
            )
            #level = LogLevel.error
            # FIXME: continue to emit?
            return

        event = kwargs
        event.update(
            log_logger=self, log_level=level, log_namespace=self.namespace,
            log_source=self.source, log_format=format, log_time=time(),
        )

        if "log_trace" in event:
            event["log_trace"].append((self, self.publisher))

        self.publisher(event)


    def failure(self, format, failure=None, level=LogLevel.error, **kwargs):
        """
        Log an failure and emit a traceback.

        For example::

            try:
                frob(knob)
            except Exception:
                log.failure("While frobbing {knob}", knob=knob)

        or::

            d = deferredFrob(knob)
            d.addErrback(lambda f: log.failure, "While frobbing {knob}",
                         f, knob=knob)

        @param format: a message format using new-style (PEP 3101)
            formatting.  The logging event (which is a L{dict}) is
            used to render this format string.

        @param failure: a L{Failure} to log.  If C{None}, a L{Failure} is
            created from the exception in flight.

        @param level: a L{LogLevel} to use.

        @param kwargs: additional keyword parameters to include with the
            event.
        """
        if failure is None:
            failure = Failure()

        self.emit(level, format, log_failure=failure, **kwargs)



class LegacyLogger(object):
    """
    A logging object that provides some compatibility with the
    L{twisted.python.log} module.

    Specifically, it provides compatible C{msg()} and C{err()} which
    forwards events to a L{Logger}'s C{emit()}, which will in turn
    produce new-style events.

    This allows existing code to use this module without changes::

        from twisted.python.logger import LegacyLogger
        log = LegacyLogger()

        log.msg("blah")

        log.msg(warning=message, category=reflect.qual(category),
                filename=filename, lineno=lineno,
                format="%(filename)s:%(lineno)s: %(category)s: %(warning)s")

        try:
            1/0
        except Exception as e:
            log.err(e, "Math is hard")
    """

    def __init__(self, logger=None):
        """
        @param logger: a L{Logger}
        """
        if logger is None:
            self.newStyleLogger = Logger(Logger._namespaceFromCallingContext())
        else:
            self.newStyleLogger = logger

        import twisted.python.log as oldStyleLogger
        self.oldStyleLogger = oldStyleLogger


    def __getattribute__(self, name):
        try:
            return super(LegacyLogger, self).__getattribute__(name)
        except AttributeError:
            return getattr(self.oldStyleLogger, name)


    def msg(self, *message, **kwargs):
        """
        This method is API-compatible with L{twisted.python.log.msg} and exists
        for compatibility with that API.
        """
        if message:
            message = " ".join(map(safe_str, message))
        else:
            message = None
        return self.newStyleLogger.emit(LogLevel.info, message, **kwargs)


    def err(self, _stuff=None, _why=None, **kwargs):
        """
        This method is API-compatible with L{twisted.python.log.err} and exists
        for compatibility with that API.
        """
        if _stuff is None:
            _stuff = Failure()
        elif isinstance(_stuff, Exception):
            _stuff = Failure(_stuff)

        if isinstance(_stuff, Failure):
            self.newStyleLogger.emit(LogLevel.error, failure=_stuff, why=_why,
                                     isError=1, **kwargs)
        else:
            # We got called with an invalid _stuff.
            self.newStyleLogger.emit(LogLevel.error, repr(_stuff), why=_why,
                                     isError=1, **kwargs)



def bindEmitters(level):
    doc = """
    Emit a log event at log level L{{{level}}}.

    @param format: a message format using new-style (PEP 3101)
        formatting.  The logging event (which is a L{{dict}}) is used to
        render this format string.

    @param kwargs: additional keyword parameters to include with the
        event.
    """.format(level=level.name)

    #
    # Attach methods to Logger
    #
    def log_emit(self, format=None, **kwargs):
        self.emit(level, format, **kwargs)

    log_emit.__doc__ = doc

    setattr(Logger, level.name, log_emit)



def _bindLevels():
    for level in LogLevel.iterconstants():
        bindEmitters(level)

_bindLevels()


#
# Observers
#

class ILogObserver(Interface):
    """
    An observer which can handle log events.
    """

    def __call__(event):
        """
        Log an event.

        @type event: C{dict} with (native) C{str} keys.

        @param event: A dictionary with arbitrary keys as defined by
            the application emitting logging events, as well as keys
            added by the logging system, with are:
            ...
        """



@implementer(ILogObserver)
class LogPublisher(object):
    """
    I{ILogObserver} that fans out events to other observers.

    Keeps track of a set of L{ILogObserver} objects and forwards
    events to each.
    """
    log = Logger()

    def __init__(self, *observers):
        self._observers = OrderedDict()
        for observer in observers:
            self._observers[observer] = None


    @property
    def observers(self):
        # Don't return a mutable object
        return self._observers.keys()


    def addObserver(self, observer):
        """
        Registers an observer with this publisher.

        @param observer: An L{ILogObserver} to add.
        """
        if not callable(observer):
            raise TypeError("Observer is not callable: {0!r}".format(observer))
        self._observers[observer] = None


    def removeObserver(self, observer):
        """
        Unregisters an observer with this publisher.

        @param observer: An L{ILogObserver} to remove.
        """
        try:
            del self._observers[observer]
        except KeyError:
            pass


    def __call__(self, event):
        """
        Forward events to contained observers.
        """
        if "log_trace" in event:
            def trace(observer):
                event["log_trace"].append((self, observer))
        else:
            trace = None

        for observer in self.observers:
            if trace is not None:
                trace(observer)

            try:
                observer(event)
            except Exception:
                #
                # We have to remove the offending observer because
                # we're going to badmouth it to all of its friends
                # (other observers) and it might get offended and
                # raise again, causing an infinite loop.
                #
                self.removeObserver(observer)
                try:
                    self.log.failure(OBSERVER_REMOVED, observer=observer)
                except Exception:
                    pass
                finally:
                    self.addObserver(observer)



class PredicateResult(Names):
    """
    Predicate results.
    """
    yes   = NamedConstant() # Log this
    no    = NamedConstant() # Don't log this
    maybe = NamedConstant() # No opinion



class ILogFilterPredicate(Interface):
    """
    A predicate that determined whether an event should be logged.
    """

    def __call__(event):
        """
        Determine whether an event should be logged.

        @returns: a L{PredicateResult}.
        """



@implementer(ILogObserver)
class FilteringLogObserver(object):
    """
    L{ILogObserver} that wraps another L{ILogObserver}, but filters
    out events based on applying a series of L{ILogFilterPredicate}s.
    """

    def __init__(self, observer, predicates):
        """
        @param observer: an L{ILogObserver} to which this observer
            will forward events.

        @param predicates: an ordered iterable of predicates to apply
            to events before forwarding to the wrapped observer.
        """
        self.observer   = observer
        self.predicates = list(predicates)


    def shouldLogEvent(self, event):
        """
        Determine whether an event should be logged, based
        C{self.predicates}.

        @param event: an event
        """
        for predicate in self.predicates:
            result = predicate(event)
            if result == PredicateResult.yes:
                return True
            if result == PredicateResult.no:
                return False
            if result == PredicateResult.maybe:
                continue
            raise TypeError("Invalid predicate result: {0!r}".format(result))
        return True


    def __call__(self, event):
        """
        Forward to next observer if predicate allows it.
        """
        if self.shouldLogEvent(event):
            if "log_trace" in event:
                event["log_trace"].append((self, self.observer))
            self.observer(event)



@implementer(ILogFilterPredicate)
class LogLevelFilterPredicate(object):
    """
    L{ILogFilterPredicate} that filters out events with a log level
    lower than the log level for the event's namespace.

    Events that not not have a log level or namespace are also dropped.
    """
    defaultLogLevel = LogLevel.info


    def __init__(self):
        self._logLevelsByNamespace = {}
        self.clearLogLevels()


    def logLevelForNamespace(self, namespace):
        """
        @param namespace: a logging namespace, or C{None} for the default
            namespace.

        @return: the L{LogLevel} for the specified namespace.
        """
        if not namespace:
            return self._logLevelsByNamespace[None]

        if namespace in self._logLevelsByNamespace:
            return self._logLevelsByNamespace[namespace]

        segments = namespace.split(".")
        index = len(segments) - 1

        while index > 0:
            namespace = ".".join(segments[:index])
            if namespace in self._logLevelsByNamespace:
                return self._logLevelsByNamespace[namespace]
            index -= 1

        return self._logLevelsByNamespace[None]


    def setLogLevelForNamespace(self, namespace, level):
        """
        Sets the global log level for a logging namespace.

        @param namespace: a logging namespace

        @param level: the L{LogLevel} for the given namespace.
        """
        if level not in LogLevel.iterconstants():
            raise InvalidLogLevelError(level)

        if namespace:
            self._logLevelsByNamespace[namespace] = level
        else:
            self._logLevelsByNamespace[None] = level


    def clearLogLevels(self):
        """
        Clears all global log levels to the default.
        """
        self._logLevelsByNamespace.clear()
        self._logLevelsByNamespace[None] = self.defaultLogLevel


    def __call__(self, event):
        level     = event.get("log_level", None)
        namespace = event.get("log_namespace", None)

        if (
            level is None or
            namespace is None or
            LogLevel._priorityForLevel(level) <
            LogLevel._priorityForLevel(self.logLevelForNamespace(namespace))
        ):
            return PredicateResult.no

        return PredicateResult.maybe



@implementer(ILogObserver)
class FileLogObserver(object):
    """
    Log observer that writes to a file-like object.
    """

    def __init__(self, fileHandle, encoding="utf-8", timeFormat=TIME_FORMAT_RFC3339):
        """
        @param fileHandle: a file-like object to write events to.

        @param encoding: the encoding to use when writing events to
            C{fileHandle}.

        @param timeFormat: the format to use when adding timestamp
            prefixes to logged events.  If C{None}, no timestamp
            prefix is added.
        """
        self.fileHandle = fileHandle
        self.encoding = encoding
        self.timeFormat = timeFormat


    def __call__(self, event):
        """
        Write event to file.
        """
        eventText = formatEvent(event).encode(self.encoding)
        eventText = eventText.replace(b"\n", b"\n\t")

        if not eventText:
            return

        if self.timeFormat is not None and event.get("log_time", None) is not None:
            t = event["log_time"]
            tz = MagicTimeZone(t)
            datetime = DateTime.fromtimestamp(t, tz)
            timeStamp = datetime.strftime(self.timeFormat)
        else:
            timeStamp = b"-"

        system = event.get("log_system", None)

        if system is None:
            system = b"{namespace}#{level}".format(
                namespace=event.get("log_namespace", b"-"),
                level=event.get("log_level", b"-"),
            )
        else:
            try:
                system = str(system)
            except Exception:
                system = b"UNFORMATTABLE"

        text = b"{timeStamp} [{system}] {event}\n".format(
            timeStamp=timeStamp,
            system=system,
            event=eventText,
        )

        untilConcludes(self.fileHandle.write, text)
        untilConcludes(self.fileHandle.flush)



@implementer(ILogObserver)
class PythonLogObserver(object):
    """
    Log observer that writes to the python standard library's
    L{logging} module.

    WARNING: specific logging configurations (example: network) can
    lead to a blocking system. Nothing is done here to prevent that,
    so be sure to not use this: code within Twisted, such as
    twisted.web, assumes that logging does not block.
    """

    def __init__(self, name="twisted"):
        """
        @param loggerName: logger identifier.
        @type loggerName: C{str}
        """
        self.logger = py_logging.getLogger(name)

    def __call__(self, event):
        """
        Format an event and bridge it to Python logging.
        """
        level = event.get("log_level", LogLevel.info)
        py_level = pythonLogLevelMapping.get(level, py_logging.INFO)
        self.logger.log(py_level, StringifiableFromEvent(event))



@implementer(ILogObserver)
class RingBufferLogObserver(object):
    """
    L{ILogObserver} that stores events in a ring buffer of a fixed
    size:

        >>> from twisted.python.logger import RingBufferLogObserver
        >>> observer = RingBufferLogObserver(5)
        >>> for n in range(10):
        ...   observer({"n":n})
        ... 
        >>> len(observer)
        5
        >>> tuple(observer)
        ({'n': 5}, {'n': 6}, {'n': 7}, {'n': 8}, {'n': 9})
        >>> observer.clear()
        >>> tuple(observer)
        ()
    """

    def __init__(self, size):
        """
        @param size: the maximum number of events to buffer.
        """
        self._buffer = deque(maxlen=size)


    def __call__(self, event):
        self._buffer.append(event)


    def __iter__(self):
        """
        Iterate over the buffered events.
        """
        return iter(self._buffer)


    def __len__(self):
        """
        @return: the number of events in the buffer.
        """
        return len(self._buffer)


    def clear(self):
        """
        Clear the event buffer.
        """
        self._buffer.clear()



@implementer(ILogObserver)
class LegacyLogObserverWrapper(object):
    """
    L{ILogObserver} that wraps an L{twisted.python.log.ILogObserver}.

    Received (new-style) events are modified prior to forwarding to
    the legacy observer to ensure compatibility with observers that
    expect legacy events.
    """

    def __init__(self, legacyObserver):
        """
        @param legacyObserver: an L{twisted.python.log.ILogObserver} to which
            this observer will forward events.
        """
        self.legacyObserver = legacyObserver


    def __repr__(self):
        return (
            "{self.__class__.__name__}({self.legacyObserver})"
            .format(self=self)
        )


    def __call__(self, event):
        """
        Forward events to the legacy observer after editing them to
        ensure compatibility.
        """
        #
        # Twisted's logging supports indicating a python log level, so let's
        # provide the equivalent to our logging levels.
        #
        level = event.get("log_level", None)
        if level in pythonLogLevelMapping:
            event["logLevel"] = pythonLogLevelMapping[level]

        # The "message" key is required by textFromEventDict()
        if "message" not in event:
            event["message"] = ()

        system = event.get("log_system", None)
        if system is not None:
            event["system"] = system

        # Format new style -> old style
        if event.get("log_format", None) is not None:
            #
            # Create an object that implements __str__() in order to
            # defer the work of formatting until it's needed by a
            # legacy log observer.
            #
            event["format"] = "%(log_legacy)s"
            event["log_legacy"] = StringifiableFromEvent(event)

        # log.failure() -> isError blah blah
        if "log_failure" in event:
            event["failure"] = event["log_failure"]
            event["isError"] = 1
            event["why"] = formatEvent(event)
        elif "isError" not in event:
            event["isError"] = 0

        self.legacyObserver(event)



class DefaultLogPublisher(object):
    """
    This observer sets up a set of chained observers as follows:

        1. B{rootPublisher} - a L{LogPublisher}

        2. B{filters}: a L{FilteringLogObserver} that filters out messages
           using a L{LogLevelFilterPredicate}

        3. B{filteredPublisher} - a L{LogPublisher}

    The purpose of this class is to provide a default log observer with
    sufficient hooks to enable applications to add observers that can either
    receive all log messages, or only log messages that are configured to pass
    though the L{LogLevelFilterPredicate}::

        from twisted.python.logger import Logger, ILogObserver

        log = Logger()

        @implementer(ILogObserver)
        class AMPObserver(object):
            def __call__(self, event):
                # eg.: Hold events in a ring buffer and expose them via AMP.
                ...

        @implementer(ILogObserver)
        class FileObserver(object):
            def __call__(self, event):
                # eg.: Take events and write them into a file.
                ...

        # Send all events to the AMPObserver
        log.publisher.addObserver(AMPObserver(), filtered=False)

        # Send filtered events to the FileObserver
        log.publisher.addObserver(AMPObserver())

    With no observers added, the default behavior is that logged events are
    dropped.
    """

    def __init__(self):
        self.filteredPublisher = LogPublisher()
        self.levels            = LogLevelFilterPredicate()
        self.filters           = FilteringLogObserver(self.filteredPublisher,
                                                      (self.levels,))
        self.rootPublisher     = LogPublisher(self.filters)

        self.filteredPublisher.name = "default filtered publisher"
        self.filters.name = "default filtering observer"
        self.rootPublisher.name = "default root publisher"


    def addObserver(self, observer, filtered=True):
        """
        Registers an observer with this publisher.

        @param observer: An L{ILogObserver} to add.

        @param filtered: If true, registers C{observer} after filters are
            applied; otherwise C{observer} will get all events.
        """
        if filtered:
            self.filteredPublisher.addObserver(observer)
            self.rootPublisher.removeObserver(observer)
        else:
            self.rootPublisher.addObserver(observer)
            self.filteredPublisher.removeObserver(observer)


    def removeObserver(self, observer):
        """
        Unregisters an observer with this publisher.

        @param observer: An L{ILogObserver} to remove.
        """
        self.rootPublisher.removeObserver(observer)
        self.filteredPublisher.removeObserver(observer)


    def __call__(self, event):
        if "log_trace" in event:
            event["log_trace"].append((self, self.rootPublisher))

        self.rootPublisher(event)



Logger.publisher = DefaultLogPublisher()



#
# Utilities
#

class StringifiableFromEvent(object):
    """
    An object that implements C{__str__()} in order to defer the work of
    formatting until it's converted into a C{str}.
    """
    def __init__(self, event):
        self.event = event


    def __unicode__(self):
        return formatEvent(self.event)


    def __str__(self):
        return unicode(self).encode("utf-8")



class CallMapping(object):
    def __init__(self, submapping):
        self._submapping = submapping


    def __getitem__(self, key):
        callit = key.endswith(u"()")
        realKey = key[:-2] if callit else key
        value = self._submapping[realKey]
        if callit:
            value = value()
        return value



def formatWithCall(formatString, mapping):
    """
    Format a string like L{unicode.format}, but:

        - taking only a name mapping; no positional arguments

        - with the additional syntax that an empty set of parentheses
          correspond to a formatting item that should be called, and its result
          C{str}'d, rather than calling C{str} on the element directly as
          normal.

    For example::

        >>> formatWithCall("{string}, {function()}.",
        ...                dict(string="just a string",
        ...                     function=lambda: "a function"))
        'just a string, a function.'

    @param formatString: A PEP-3101 format string.
    @type formatString: L{unicode}

    @param mapping: A L{dict}-like object to format.

    @return: The string with formatted values interpolated.
    @rtype: L{unicode}
    """
    return unicode(
        theFormatter.vformat(formatString, (), CallMapping(mapping))
    )

theFormatter = Formatter()



class MagicTimeZone(TZInfo):
    """
    Magic TimeZone.
    """
    def __init__(self, t):
        self._offset = DateTime.fromtimestamp(t) - DateTime.utcfromtimestamp(t)

    def utcoffset(self, dt):
        return self._offset

    def tzname(self, dt):
        return "Magic"

    def dst(self, dt):
        return timeDeltaZero

timeDeltaZero = TimeDelta(0)



def formatTrace(trace):
    def formatWithName(obj):
        if hasattr(obj, "name"):
            return "{0} ({1})".format(obj, obj.name)
        else:
            return "{0}".format(obj)

    result = []
    lineage = []

    for parent, child in trace:
        if not lineage or lineage[-1] is not parent:
            if parent in lineage:
                while lineage[-1] is not parent:
                    lineage.pop()

            else:
                if not lineage:
                    result.append(u"{0}\n".format(formatWithName(parent)))

                lineage.append(parent)

        result.append(u"  " * len(lineage))
        result.append(u"-> {0}\n".format(formatWithName(child)))

    return u"".join(result)
