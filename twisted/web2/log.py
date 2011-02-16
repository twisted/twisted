# -*- test-case-name: twisted.web2.test.test_log -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""Logging tools. This is still in flux (even moreso than the rest of web2)."""

import time
from twisted.python import log as tlog
from twisted.internet import defer
from twisted.web2 import iweb, stream, resource
from zope.interface import implements, Attribute, Interface

class _LogByteCounter(object):
    implements(stream.IByteStream)
    
    def __init__(self, stream, done):
        self.stream=stream
        self.done=done
        self.len=0
        
    length=property(lambda self: self.stream.length)
    
    def _callback(self, data):
        if data is None:
            if self.done:
                done=self.done; self.done=None
                done(True, self.len)
        else:
            self.len += len(data)
        return data
    
    def read(self):
        data = self.stream.read()
        if isinstance(data, defer.Deferred):
            return data.addCallback(self._callback)
        return self._callback(data)
    
    def close(self):
        if self.done:
            done=self.done; self.done=None
            done(False, self.len)
        self.stream.close()

    
class ILogInfo(Interface):
    """Auxilliary information about the response useful for logging."""
    
    bytesSent=Attribute("Number of bytes sent.")
    responseCompleted=Attribute("Whether or not the response was completed.")
    secondsTaken=Attribute("Number of seconds taken to serve the request.")
    startTime=Attribute("Time at which the request started")

    
class LogInfo(object):
    implements(ILogInfo)

    responseCompleted=None
    secondsTaken=None
    bytesSent=None
    startTime=None

    
def logFilter(request, response, startTime=None):
    if startTime is None:
        startTime = time.time()
        
    def _log(success, length):
        loginfo=LogInfo()
        loginfo.bytesSent=length
        loginfo.responseCompleted=success
        loginfo.secondsTaken=time.time()-startTime
        
        tlog.msg(interface=iweb.IRequest, request=request, response=response,
                 loginfo=loginfo)
        # Or just...
        # ILogger(ctx).log(...) ?

    if response.stream:
        response.stream=_LogByteCounter(response.stream, _log)
    else:
        _log(True, 0)

    return response

logFilter.handleErrors = True


class LogWrapperResource(resource.WrapperResource):
    def hook(self, request):
        # Insert logger
        request.addResponseFilter(logFilter, atEnd=True)

monthname = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


class BaseCommonAccessLoggingObserver(object):
    """An abstract Twisted-based logger for creating access logs.

    Derived implementations of this class *must* implement the
    ``logMessage(message)`` method, which will send the message to an actual
    log/file or stream.
    """

    logFormat = '%s - %s [%s] "%s" %s %d "%s" "%s"'
    def logMessage(self, message):
        raise NotImplemented, 'You must provide an implementation.'

    def computeTimezoneForLog(self, tz):
        if tz > 0:
            neg = 1
        else:
            neg = 0
            tz = -tz
        h, rem = divmod(tz, 3600)
        m, rem = divmod(rem, 60)
        if neg:
            return '-%02d%02d' % (h, m)
        else:
            return '+%02d%02d' % (h, m)

    tzForLog = None
    tzForLogAlt = None

    def logDateString(self, when):
        logtime = time.localtime(when)
        Y, M, D, h, m, s = logtime[:6]
        
        if not time.daylight:
            tz = self.tzForLog
            if tz is None:
                tz = self.computeTimezoneForLog(time.timezone)
                self.tzForLog = tz
        else:
            tz = self.tzForLogAlt
            if tz is None:
                tz = self.computeTimezoneForLog(time.altzone)
                self.tzForLogAlt = tz

        return '%02d/%s/%02d:%02d:%02d:%02d %s' % (
            D, monthname[M], Y, h, m, s, tz)

    def emit(self, eventDict):
        if eventDict.get('interface') is not iweb.IRequest:
            return

        request = eventDict['request']
        response = eventDict['response']
        loginfo = eventDict['loginfo']
        firstLine = '%s %s HTTP/%s' %(
            request.method,
            request.uri,
            '.'.join([str(x) for x in request.clientproto]))
        
        self.logMessage(
            '%s - %s [%s] "%s" %s %d "%s" "%s"' %(
                request.remoteAddr.host,
                # XXX: Where to get user from?
                "-",
                self.logDateString(
                    response.headers.getHeader('date', 0)),
                firstLine,
                response.code,
                loginfo.bytesSent,
                request.headers.getHeader('referer', '-'),
                request.headers.getHeader('user-agent', '-')
                )
            )

    def start(self):
        """Start observing log events."""
        tlog.addObserver(self.emit)

    def stop(self):
        """Stop observing log events."""
        tlog.removeObserver(self.emit)


class FileAccessLoggingObserver(BaseCommonAccessLoggingObserver):
    """I log requests to a single logfile
    """
    
    def __init__(self, logpath):
        self.logpath = logpath
                
    def logMessage(self, message):
        self.f.write(message + '\n')

    def start(self):
        super(FileAccessLoggingObserver, self).start()
        self.f = open(self.logpath, 'a', 1)
        
    def stop(self):
        super(FileAccessLoggingObserver, self).stop()
        self.f.close()

                
class DefaultCommonAccessLoggingObserver(BaseCommonAccessLoggingObserver):
    """Log requests to default twisted logfile."""
    def logMessage(self, message):
        tlog.msg(message)
