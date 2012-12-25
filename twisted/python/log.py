# -*- test-case-name: twisted.test.test_log -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Logging and metrics infrastructure.
"""

from __future__ import division, absolute_import

import sys
import time
import warnings
from datetime import datetime, tzinfo
import logging

from zope.interface import Interface

from twisted.python.compat import unicode, _PY3
from twisted.python import context
from twisted.python import _reflectpy3 as reflect
from twisted.python import _utilpy3 as util
from twisted.python import failure
from twisted.python.threadable import synchronize


class ILogContext:
    """
    Actually, this interface is just a synonym for the dictionary interface,
    but it serves as a key for the default information in a log.

    I do not inherit from C{Interface} because the world is a cruel place.
    """



class ILogObserver(Interface):
    """
    An observer which can do something with log events.

    Given that most log observers are actually bound methods, it's okay to not
    explicitly declare provision of this interface.
    """
    def __call__(eventDict):
        """
        Log an event.

        @type eventDict: C{dict} with C{str} keys.
        @param eventDict: A dictionary with arbitrary keys.  However, these
            keys are often available:
              - C{message}: A C{tuple} of C{str} containing messages to be
                logged.
              - C{system}: A C{str} which indicates the "system" which is
                generating this event.
              - C{isError}: A C{bool} indicating whether this event represents
                an error.
              - C{failure}: A L{failure.Failure} instance
              - C{why}: Used as header of the traceback in case of errors.
              - C{format}: A string format used in place of C{message} to
                customize the event.  The intent is for the observer to format
                a message by doing something like C{format % eventDict}.
        """



context.setDefault(ILogContext,
                   {"isError": 0,
                    "system": "-"})

def callWithContext(ctx, func, *args, **kw):
    newCtx = context.get(ILogContext).copy()
    newCtx.update(ctx)
    return context.call({ILogContext: newCtx}, func, *args, **kw)

def callWithLogger(logger, func, *args, **kw):
    """
    Utility method which wraps a function in a try:/except:, logs a failure if
    one occurrs, and uses the system's logPrefix.
    """
    try:
        lp = logger.logPrefix()
    except KeyboardInterrupt:
        raise
    except:
        lp = '(buggy logPrefix method)'
        err(system=lp)
    try:
        return callWithContext({"system": lp}, func, *args, **kw)
    except KeyboardInterrupt:
        raise
    except:
        err(system=lp)



_keepErrors = 0
_keptErrors = []
_ignoreErrors = []


def err(_stuff=None, _why=None, **kw):
    """
    Write a failure to the log.

    The C{_stuff} and C{_why} parameters use an underscore prefix to lessen
    the chance of colliding with a keyword argument the application wishes
    to pass.  It is intended that they be supplied with arguments passed
    positionally, not by keyword.

    @param _stuff: The failure to log.  If C{_stuff} is C{None} a new
        L{Failure} will be created from the current exception state.  If
        C{_stuff} is an C{Exception} instance it will be wrapped in a
        L{Failure}.
    @type _stuff: C{NoneType}, C{Exception}, or L{Failure}.

    @param _why: The source of this failure.  This will be logged along with
        C{_stuff} and should describe the context in which the failure
        occurred.
    @type _why: C{str}
    """
    if _stuff is None:
        _stuff = failure.Failure()
    if isinstance(_stuff, failure.Failure):
        if _keepErrors:
            if _ignoreErrors:
                keep = 0
                for err in _ignoreErrors:
                    r = _stuff.check(err)
                    if r:
                        keep = 0
                        break
                    else:
                        keep = 1
                if keep:
                    _keptErrors.append(_stuff)
            else:
                _keptErrors.append(_stuff)
        msg(failure=_stuff, why=_why, isError=1, **kw)
    elif isinstance(_stuff, Exception):
        msg(failure=failure.Failure(_stuff), why=_why, isError=1, **kw)
    else:
        msg(repr(_stuff), why=_why, isError=1, **kw)

deferr = err


class Logger:
    """
    This represents a class which may 'own' a log. Used by subclassing.
    """
    def logPrefix(self):
        """
        Override this method to insert custom logging behavior.  Its
        return value will be inserted in front of every line.  It may
        be called more times than the number of output lines.
        """
        return '-'



class LogPublisher:
    """
    Class for singleton log message publishing.
    """

    synchronized = ['msg']

    def __init__(self):
        self.observers = []

    def addObserver(self, other):
        """
        Add a new observer.

        @type other: Provider of L{ILogObserver}
        @param other: A callable object that will be called with each new log
            message (a dict).
        """
        assert callable(other)
        self.observers.append(other)

    def removeObserver(self, other):
        """
        Remove an observer.
        """
        self.observers.remove(other)

    def msg(self, *message, **kw):
        """
        Log a new message.

        The message should be a native string, i.e. bytes on Python 2 and
        Unicode on Python 3. For compatibility with both use the native string
        syntax, for example::

        >>> log.msg('Hello, world.')

        You MUST avoid passing in Unicode on Python 2, and the form::

        >>> log.msg('Hello ', 'world.')

        This form only works (sometimes) by accident.
        """
        actualEventDict = (context.get(ILogContext) or {}).copy()
        actualEventDict.update(kw)
        actualEventDict['message'] = message
        actualEventDict['time'] = time.time()
        for i in range(len(self.observers) - 1, -1, -1):
            try:
                self.observers[i](actualEventDict)
            except KeyboardInterrupt:
                # Don't swallow keyboard interrupt!
                raise
            except UnicodeEncodeError:
                raise
            except:
                observer = self.observers[i]
                self.observers[i] = lambda event: None
                try:
                    self._err(failure.Failure(),
                        "Log observer %s failed." % (observer,))
                except:
                    # Sometimes err() will throw an exception,
                    # e.g. RuntimeError due to blowing the stack; if that
                    # happens, there's not much we can do...
                    pass
                self.observers[i] = observer


    def _err(self, failure, why):
        """
        Log a failure.

        Similar in functionality to the global {err} function, but the failure
        gets published only to observers attached to this publisher.

        @param failure: The failure to log.
        @type failure: L{Failure}.

        @param why: The source of this failure.  This will be logged along with
            the C{failure} and should describe the context in which the failure
            occurred.
        @type why: C{str}
        """
        self.msg(failure=failure, why=why, isError=1)


    def showwarning(self, message, category, filename, lineno, file=None,
                    line=None):
        """
        Twisted-enabled wrapper around L{warnings.showwarning}.

        If C{file} is C{None}, the default behaviour is to emit the warning to
        the log system, otherwise the original L{warnings.showwarning} Python
        function is called.
        """
        if file is None:
            self.msg(warning=message, category=reflect.qual(category),
                     filename=filename, lineno=lineno,
                     format="%(filename)s:%(lineno)s: %(category)s: %(warning)s")
        else:
            if sys.version_info < (2, 6):
                _oldshowwarning(message, category, filename, lineno, file)
            else:
                _oldshowwarning(message, category, filename, lineno, file, line)

synchronize(LogPublisher)



try:
    theLogPublisher
except NameError:
    theLogPublisher = LogPublisher()
    addObserver = theLogPublisher.addObserver
    removeObserver = theLogPublisher.removeObserver
    msg = theLogPublisher.msg
    showwarning = theLogPublisher.showwarning



def _safeFormat(fmtString, fmtDict):
    """
    Try to format the string C{fmtString} using C{fmtDict} arguments,
    swallowing all errors to always return a string.
    """
    # There's a way we could make this if not safer at least more
    # informative: perhaps some sort of str/repr wrapper objects
    # could be wrapped around the things inside of C{fmtDict}. That way
    # if the event dict contains an object with a bad __repr__, we
    # can only cry about that individual object instead of the
    # entire event dict.
    try:
        text = fmtString % fmtDict
    except KeyboardInterrupt:
        raise
    except:
        try:
            text = ('Invalid format string or unformattable object in log message: %r, %s' % (fmtString, fmtDict))
        except:
            try:
                text = 'UNFORMATTABLE OBJECT WRITTEN TO LOG with fmt %r, MESSAGE LOST' % (fmtString,)
            except:
                text = 'PATHOLOGICAL ERROR IN BOTH FORMAT STRING AND MESSAGE DETAILS, MESSAGE LOST'
    return text


def textFromEventDict(eventDict):
    """
    Extract text from an event dict passed to a log observer. If it cannot
    handle the dict, it returns None.

    The possible keys of eventDict are:
     - C{message}: by default, it holds the final text. It's required, but can
       be empty if either C{isError} or C{format} is provided (the first
       having the priority).
     - C{isError}: boolean indicating the nature of the event.
     - C{failure}: L{failure.Failure} instance, required if the event is an
       error.
     - C{why}: if defined, used as header of the traceback in case of errors.
     - C{format}: string format used in place of C{message} to customize
       the event. It uses all keys present in C{eventDict} to format
       the text.
    Other keys will be used when applying the C{format}, or ignored.
    """
    edm = eventDict['message']
    if not edm:
        if eventDict['isError'] and 'failure' in eventDict:
            text = ((eventDict.get('why') or 'Unhandled Error')
                    + '\n' + eventDict['failure'].getTraceback())
        elif 'format' in eventDict:
            text = _safeFormat(eventDict['format'], eventDict)
        else:
            # we don't know how to log this
            return
    else:
        text = ' '.join(map(reflect.safe_str, edm))
    return text


def _posixTime(utcDateTime, _EPOCH=datetime.utcfromtimestamp(0)):
    """
    Return a POSIX timestamp that coresponds to the C{utcDateTime}.

    @type utcDateTime: C{datetime.datetime}
    @param utcDateTime: aware or unaware C{datetime} object in UTC timezone.
    @rtype: C{float}
    """
    delta = utcDateTime.replace(tzinfo=None) - _EPOCH
    return 24 * 60 * 60 * delta.days + delta.seconds + delta.microseconds / 1e6



class _LocalTimezone(tzinfo):
    """
    Represents the local timezone, as configured for the computer where this
    code is running.
    """

    def utcoffset(self, dt):
        """
        Return offset of local time C{dt} from UTC, in minutes east of UTC.

        @type dt: C{datetime.datetime}
        @rtype: C{datetime.timedelta}
        """
        when = time.mktime(dt.timetuple())
        return datetime.fromtimestamp(when) - datetime.utcfromtimestamp(when)


    def dst(self, dt):
        """
        Return the daylight saving time adjustment for local time C{dt}.

        C{_LocalTimezone} objects are not aware of DST, so this always
        returns C{None}.

        @type dt: C{datetime.datetime}
        """
        # The dostring is not entirely accurate, we could calculate DST offset
        # similary as tzname below. For that we would need UTC offset, but
        # utcoffset() calls dt.timetuple(), which tries to call dt.tz.dst(),
        # leading to infinite recursion. Anyway, it's not like this information
        # is displayed anywhere.
        return None


    def tzname(self, dt):
        """
        Return the name of the local timezone at C{dt} local time.

        @type dt: C{datetime.datetime}
        @rtype: C{str}
        """
        when = _posixTime(dt - self.utcoffset(dt))
        return time.tzname[time.localtime(when).tm_isdst]


    def fromutc(self, dt):
        """
        Return an aware local C{datetime.datetime} object, equivalent to
        UTC C{datetime.datetime} object C{dt}.
        """
        when = _posixTime(dt)
        offset = datetime.fromtimestamp(when) - datetime.utcfromtimestamp(when)
        return dt + offset



class FileLogObserver:
    """
    Log observer that writes to a file-like object.

    @type timeFormat: C{str} or C{NoneType}
    @ivar timeFormat: If not C{None}, the format string passed to
        C{datetime.strftime()} when formatting log event times.
    @type timezoneInfo: C{datetime.tzinfo}
    @ivar timezoneInfo: The timezone to which the time of the logged event will
        be converted before it will be formatted.
    """
    timeFormat = None

    def __init__(self, f, timezoneInfo=_LocalTimezone()):
        """
        @type f: C{file}
        @param f: A file-like object to which the log entries will be written.
        @type timezoneInfo: C{datetime.tzinfo}
        @param timezoneInfo: The timezone that should be used for timestamp
            formatting.
        """
        self.write = f.write
        self.flush = f.flush
        self.timezoneInfo = timezoneInfo


    def getTimezoneOffset(self, when):
        """
        Return the current local timezone offset from UTC.

        @type when: C{float}
        @param when: POSIX (ie, UTC) timestamp for which to find the offset.

        @rtype: C{int}
        @return: The number of seconds offset from UTC.  West is positive,
        east is negative.
        """
        offset = datetime.utcfromtimestamp(when) - datetime.fromtimestamp(when)
        return offset.days * (60 * 60 * 24) + offset.seconds


    def formatTime(self, when):
        """
        Format the given UTC timestamp as a string representing that time in
        the C{self.timezoneInfo} timezone.

        By default it's formatted as a ISO8601-like string (ISO8601 date and
        ISO8601 time separated by a space, followed by local timezone offset).
        It can be customized using the C{timeFormat} attribute, which will be
        used as input for the underlying C{datetime.strftime} call.

        @type when: C{float}
        @param when: POSIX (ie, UTC) timestamp to format.

        @rtype: C{str}
        """
        awareDateTime = datetime.fromtimestamp(when, self.timezoneInfo)
        timeFormat = self.timeFormat
        if timeFormat is None:
            timeFormat = "%Y-%m-%d %H:%M:%S%z"
        return awareDateTime.strftime(timeFormat)


    def emit(self, eventDict):
        text = textFromEventDict(eventDict)
        if text is None:
            return

        timeStr = self.formatTime(eventDict['time'])
        fmtDict = {'system': eventDict['system'], 'text': text.replace("\n", "\n\t")}
        msgStr = _safeFormat("[%(system)s] %(text)s\n", fmtDict)

        util.untilConcludes(self.write, timeStr + " " + msgStr)
        util.untilConcludes(self.flush)  # Hoorj!

    def start(self):
        """
        Start observing log events.
        """
        addObserver(self.emit)

    def stop(self):
        """
        Stop observing log events.
        """
        removeObserver(self.emit)


class PythonLoggingObserver(object):
    """
    Output twisted messages to Python standard library L{logging} module.

    WARNING: specific logging configurations (example: network) can lead to
    a blocking system. Nothing is done here to prevent that, so be sure to not
    use this: code within Twisted, such as twisted.web, assumes that logging
    does not block.
    """

    def __init__(self, loggerName="twisted"):
        """
        @param loggerName: identifier used for getting logger.
        @type loggerName: C{str}
        """
        self.logger = logging.getLogger(loggerName)

    def emit(self, eventDict):
        """
        Receive a twisted log entry, format it and bridge it to python.

        By default the logging level used is info; log.err produces error
        level, and you can customize the level by using the C{logLevel} key::

        >>> log.msg('debugging', logLevel=logging.DEBUG)

        """
        if 'logLevel' in eventDict:
            level = eventDict['logLevel']
        elif eventDict['isError']:
            level = logging.ERROR
        else:
            level = logging.INFO
        text = textFromEventDict(eventDict)
        if text is None:
            return
        self.logger.log(level, text)

    def start(self):
        """
        Start observing log events.
        """
        addObserver(self.emit)

    def stop(self):
        """
        Stop observing log events.
        """
        removeObserver(self.emit)


class StdioOnnaStick:
    """
    Class that pretends to be stdout/err, and turns writes into log messages.

    @ivar isError: boolean indicating whether this is stderr, in which cases
                   log messages will be logged as errors.

    @ivar encoding: unicode encoding used to encode any unicode strings
                    written to this object.
    """

    closed = 0
    softspace = 0
    mode = 'wb'
    name = '<stdio (log)>'

    def __init__(self, isError=0, encoding=None):
        self.isError = isError
        if encoding is None:
            encoding = sys.getdefaultencoding()
        self.encoding = encoding
        self.buf = ''
  
    def close(self):
        pass

    def fileno(self):
        return -1

    def flush(self):
        pass

    def read(self):
        raise IOError("can't read from the log!")

    readline = read
    readlines = read
    seek = read
    tell = read

    def write(self, data):
        if not _PY3 and isinstance(data, unicode):
            data = data.encode(self.encoding)
        d = (self.buf + data).split('\n')
        self.buf = d[-1]
        messages = d[0:-1]
        for message in messages:
            msg(message, printed=1, isError=self.isError)

    def writelines(self, lines):
        for line in lines:
            if not _PY3 and isinstance(line, unicode):
                line = line.encode(self.encoding)
            msg(line, printed=1, isError=self.isError)


try:
    _oldshowwarning
except NameError:
    _oldshowwarning = None


def startLogging(file, *a, **kw):
    """
    Initialize logging to a specified file.

    @return: A L{FileLogObserver} if a new observer is added, None otherwise.
    """
    if isinstance(file, StdioOnnaStick):
        return
    flo = FileLogObserver(file)
    startLoggingWithObserver(flo.emit, *a, **kw)
    return flo



def startLoggingWithObserver(observer, setStdout=1):
    """
    Initialize logging to a specified observer. If setStdout is true
    (defaults to yes), also redirect sys.stdout and sys.stderr
    to the specified file.
    """
    global defaultObserver, _oldshowwarning
    if not _oldshowwarning:
        _oldshowwarning = warnings.showwarning
        warnings.showwarning = showwarning
    if defaultObserver:
        defaultObserver.stop()
        defaultObserver = None
    addObserver(observer)
    msg("Log opened.")
    if setStdout:
        sys.stdout = logfile
        sys.stderr = logerr


class NullFile:
    softspace = 0
    def read(self): pass
    def write(self, bytes): pass
    def flush(self): pass
    def close(self): pass


def discardLogs():
    """
    Throw away all logs.
    """
    global logfile
    logfile = NullFile()


# Prevent logfile from being erased on reload.  This only works in cpython.
try:
    logfile
except NameError:
    logfile = StdioOnnaStick(0, getattr(sys.stdout, "encoding", None))
    logerr = StdioOnnaStick(1, getattr(sys.stderr, "encoding", None))



class DefaultObserver:
    """
    Default observer.

    Will ignore all non-error messages and send error messages to sys.stderr.
    Will be removed when startLogging() is called for the first time.
    """
    stderr = sys.stderr

    def _emit(self, eventDict):
        if eventDict["isError"]:
            if 'failure' in eventDict:
                text = ((eventDict.get('why') or 'Unhandled Error')
                        + '\n' + eventDict['failure'].getTraceback())
            else:
                text = " ".join([str(m) for m in eventDict["message"]]) + "\n"

            self.stderr.write(text)
            self.stderr.flush()

    def start(self):
        addObserver(self._emit)

    def stop(self):
        removeObserver(self._emit)



try:
    defaultObserver
except NameError:
    defaultObserver = DefaultObserver()
    defaultObserver.start()

