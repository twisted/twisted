# -*- test-case-name: twisted.python.logger.test.test_legacy -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Integration with L{twisted.python.log}.
"""

from zope.interface import implementer

from twisted.python.reflect import safe_str
from twisted.python.failure import Failure

from ._levels import LogLevel
from ._format import formatEvent
from ._logger import Logger
from ._observer import ILogObserver
from ._stdlib import (toStdlibLogLevelMapping, fromStdlibLogLevelMapping,
                      StringifiableFromEvent)



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
        @param logger: A logger.
        @type logger: L{Logger}
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

        @param message: A message.
        @type message: L{tuple} of L{bytes}

        @param kwargs: Fields in the legacy log message.
        @type kwargs: L{dict}
        """
        if message:
            message = " ".join(map(safe_str, message))
        else:
            message = None

        self.newStyleLogger.emit(LogLevel.info, message, **kwargs)


    def err(self, _stuff=None, _why=None, **kwargs):
        """
        This method is API-compatible with L{twisted.python.log.err} and exists
        for compatibility with that API.

        @param _stuff: Something that describes a problem.
        @type _stuff: L{Failure}, L{str}, or L{Exception}

        @param _why: A string describing what caused the failure.
        @type _why: L{str}

        @param kwargs: Additional fields.
        @type kwargs: L{dict}
        """
        if _stuff is None:
            _stuff = Failure()
        elif isinstance(_stuff, Exception):
            _stuff = Failure(_stuff)

        if isinstance(_stuff, Failure):
            if _why:
                text = safe_str(_why)
            else:
                text = "Unhandled Error"

            text = "{why}\n{traceback}".format(
                why=text,
                traceback=_stuff.getTraceback(),
            )

            self.newStyleLogger.emit(
                LogLevel.critical,
                text, failure=_stuff, why=_why, isError=1, **kwargs
            )
        else:
            # We got called with an invalid _stuff.
            self.newStyleLogger.emit(
                LogLevel.critical,
                repr(_stuff), why=_why, isError=1, **kwargs
            )



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

        # Twisted's logging supports indicating a python log level, so let's
        # provide the equivalent to our logging levels.
        level = event.get("log_level", None)
        if level in toStdlibLogLevelMapping:
            event["logLevel"] = toStdlibLogLevelMapping[level]

        # The "message" key is required by textFromEventDict()
        if "message" not in event:
            event["message"] = ()

        system = event.get("log_system", None)
        if system is not None:
            event["system"] = system

        # Format new style -> old style
        if event.get("log_format", None) is not None and "format" not in event:
            # Create an object that implements __str__() in order to defer the
            # work of formatting until it's needed by a legacy log observer.
            event["format"] = "%(log_legacy)s"
            event["log_legacy"] = StringifiableFromEvent(event.copy())

        # From log.failure() -> isError blah blah
        if "log_failure" in event:
            event["failure"] = event["log_failure"]
            event["isError"] = 1
            event["why"] = formatEvent(event)
        elif "isError" not in event:
            event["isError"] = 0

        self.legacyObserver(event)



def publishToNewObserver(observer, eventDict, textFromEventDict):
    """
    Publish an old-style (L{twisted.python.log}) event to a new-style
    (L{twisted.python.logger}) observer.

    @note: It's possible that a new-style event was sent to a
        L{LegacyLogObserverWrapper}, and may now be getting sent back to a
        new-style observer.  In this case, it's already a new-style event,
        adapted to also look like an old-style event, and we don't need to
        tweak it again to be a new-style event, hence the checks for
        already-defined new-style keys.

    @param observer: A new-style observer to handle this event.
    @type observer: L{ILogObserver}

    @param eventDict: An L{old-style <twisted.python.log>}, log event.
    @type eventDict: L{dict}

    @param textFromEventDict: callable that can format an old-style event as a
        string.  Passed here rather than imported to avoid circular dependency.
    @type textFromEventDict: 1-arg L{callable} taking L{dict} returning L{str}

    @return: L{None}
    """

    if "log_format" not in eventDict:
        text = textFromEventDict(eventDict)
        if text is not None:
            eventDict["log_text"] = text
            eventDict["log_format"] = "{log_text}"

    if "log_level" not in eventDict:
        if "logLevel" in eventDict:
            level = fromStdlibLogLevelMapping[eventDict["logLevel"]]
        elif eventDict["isError"]:
            level = LogLevel.critical
        else:
            level = LogLevel.info

        eventDict["log_level"] = level

    if "log_namespace" not in eventDict:
        eventDict["log_namespace"] = "log_legacy"

    if "log_system" not in eventDict and "system" in eventDict:
        eventDict["log_system"] = eventDict["system"]

    observer(eventDict)
