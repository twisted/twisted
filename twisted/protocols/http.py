
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""HyperText Transfer Protocol implementation.

This is used by twisted.web.
"""

# system imports
import string
from cStringIO import StringIO
import tempfile
import base64
import cgi
import urllib
import socket
import time
import calendar
import sys

# sibling imports
import basic, protocol

# twisted imports
from twisted.internet import interfaces
from twisted.python import log


protocol_version = "HTTP/1.1"

_CONTINUE = 100
SWITCHING = 101

OK                              = 200
CREATED                         = 201
ACCEPTED                        = 202
NON_AUTHORITATIVE_INFORMATION   = 203
NO_CONTENT                      = 204
RESET_CONTENT                   = 205
PARTIAL_CONTENT                 = 206

MULTIPLE_CHOICE                 = 300
MOVED_PERMANENTLY               = 301
FOUND                           = 302
SEE_OTHER                       = 303
NOT_MODIFIED                    = 304
USE_PROXY                       = 305
TEMPORARY_REDIRECT              = 307

BAD_REQUEST                     = 400
UNAUTHORIZED                    = 401
PAYMENT_REQUIRED                = 402
FORBIDDEN                       = 403
NOT_FOUND                       = 404
NOT_ALLOWED                     = 405
NOT_ACCEPTABLE                  = 406
PROXY_AUTH_REQUIRED             = 407
REQUEST_TIMEOUT                 = 408
CONFLICT                        = 409
GONE                            = 410
LENGTH_REQUIRED                 = 411
PRECONDITION_FAILED             = 412
REQUEST_ENTITY_TOO_LARGE        = 413
REQUEST_URI_TOO_LONG            = 414
UNSUPPORTED_MEDIA_TYPE          = 415
REQUESTED_RANGE_NOT_SATISFIABLE = 416
EXPECTATION_FAILED              = 417

INTERNAL_SERVER_ERROR           = 500
NOT_IMPLEMENTED                 = 501
BAD_GATEWAY                     = 502
SERVICE_UNAVAILABLE             = 503
GATEWAY_TIMEOUT                 = 504
HTTP_VERSION_NOT_SUPPORTED      = 505
NOT_EXTENDED                    = 510

RESPONSES = {
    # 100
    _CONTINUE: "Continue",
    SWITCHING: "Switching Protocols",

    # 200
    OK: "OK",
    CREATED: "Created",
    ACCEPTED: "Accepted",
    NON_AUTHORITATIVE_INFORMATION: "Non-Authoritative Information",
    NO_CONTENT: "No Content",
    RESET_CONTENT: "Reset Content.",
    PARTIAL_CONTENT: "Partial Content",

    # 300
    MULTIPLE_CHOICE: "Multiple Choices",
    MOVED_PERMANENTLY: "Moved Permanently",
    FOUND: "Found",
    SEE_OTHER: "See Other",
    NOT_MODIFIED: "Not Modified",
    USE_PROXY: "Use Proxy",
    # 306 not defined??
    TEMPORARY_REDIRECT: "Temporary Redirect",

    # 400
    BAD_REQUEST: "Bad Request",
    UNAUTHORIZED: "Unauthorized",
    PAYMENT_REQUIRED: "Payment Required",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    NOT_ALLOWED: "Method Not Allowed",
    NOT_ACCEPTABLE: "Not Acceptable",
    PROXY_AUTH_REQUIRED: "Proxy Authentication Required",
    REQUEST_TIMEOUT: "Request Time-out",
    CONFLICT: "Conflict",
    GONE: "Gone",
    LENGTH_REQUIRED: "Length Required",
    PRECONDITION_FAILED: "Precondition Failed",
    REQUEST_ENTITY_TOO_LARGE: "Request Entity Too Large",
    REQUEST_URI_TOO_LONG: "Request-URI Too Long",
    UNSUPPORTED_MEDIA_TYPE: "Unsupported Media Type",
    REQUESTED_RANGE_NOT_SATISFIABLE: "Requested Range not satisfiable",
    EXPECTATION_FAILED: "Expectation Failed",

    # 500
    INTERNAL_SERVER_ERROR: "Internal Server Error",
    NOT_IMPLEMENTED: "Not Implemented",
    BAD_GATEWAY: "Bad Gateway",
    SERVICE_UNAVAILABLE: "Service Unavailable",
    GATEWAY_TIMEOUT: "Gateway Time-out",
    HTTP_VERSION_NOT_SUPPORTED: "HTTP Version not supported",

    NOT_EXTENDED: "Not Extended"}

# backwards compatability
responses = RESPONSES


# datetime parsing and formatting
weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
monthname = [None,
             'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def datetimeToString(msSinceEpoch=None):
    """Convert seconds since epoch to HTTP datetime string."""
    if msSinceEpoch == None:
        msSinceEpoch = time.time()
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(msSinceEpoch)
    s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
        weekdayname[wd],
        day, monthname[month], year,
        hh, mm, ss)
    return s

def datetimeToLogString(msSinceEpoch=None):
    """Convert seconds since epoch to log datetime string."""
    if msSinceEpoch == None:
        msSinceEpoch = time.time()
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(msSinceEpoch)
    s = "[%02d/%3s/%4d:%02d:%02d:%02d +0000]" % (
        day, monthname[month], year,
        hh, mm, ss)
    return s

def timegm(year, month, day, hour, minute, second):
    """Convert time tuple in GMT to seconds since epoch, GMT"""
    EPOCH = 1970
    assert year >= EPOCH
    assert 1 <= month <= 12
    days = 365*(year-EPOCH) + calendar.leapdays(EPOCH, year)
    for i in range(1, month):
        days = days + calendar.mdays[i]
    if month > 2 and calendar.isleap(year):
        days = days + 1
    days = days + day - 1
    hours = days*24 + hour
    minutes = hours*60 + minute
    seconds = minutes*60 + second
    return seconds

def stringToDatetime(dateString):
    """Convert an HTTP date string to seconds since epoch."""
    parts = string.split(dateString, ' ')
    day = int(parts[1])
    month = int(monthname.index(parts[2]))
    year = int(parts[3])
    hour, min, sec = map(int, string.split(parts[4], ':'))
    return int(timegm(year, month, day, hour, min, sec))

def toChunk(data):
    """Convert string to a chunk."""
    return "%x\r\n%s\r\n" % (len(data), data)

def fromChunk(data):
    """Convert chunk to string."""
    raise NotImplementedError


class HTTPClient(basic.LineReceiver):
    """A client for HTTP 1.0

    Notes:
    You probably want to send a 'Host' header with the name of
    the site you're connecting to, in order to not break name
    based virtual hosting.
    """

    firstLine = 0
    __buffer = ''
    length = None
    
    def sendCommand(self, command, path):
        self.transport.write('%s %s HTTP/1.0\r\n' % (command, path))

    def sendHeader(self, name, value):
        self.transport.write('%s: %s\r\n' % (name, value))

    def endHeaders(self):
        self.transport.write('\r\n')

    def lineReceived(self, line):
        if self.firstLine:
            self.firstLine = 0
            version, status, message = string.split(line, None, 2)
            self.handleStatus(version, status, message)
            return
        if line:
            key, val = string.split(line, ': ', 1)
            self.handleHeader(key, val)
            if string.lower(key) == 'content-length':
                self.length = int(val)
        else:
            self.handleEndHeaders()
            self.setRawMode()

    def connectionLost(self):
        if self.__buffer:
            b = self.__buffer
            self.__buffer = ''
            self.handleResponse(b)

    def connectionMade(self):
        pass

    handleStatus = handleHeader = handleEndHeaders = lambda *args: None

    def rawDataReceived(self, data):
        if self.length is not None:
            data, rest = data[:self.length], data[self.length:]
            self.length = self.length - len(data)
        else:
            rest = ''
        self.__buffer = self.__buffer + data
        if self.length == 0:
            b = self.__buffer
            self.__buffer = ''
            self.handleResponse(b)
            self.setLineMode(rest)


class Request:
    """A HTTP request."""
    
    __implements__ = interfaces.IConsumer
    
    producer = None
    finished = 0
    code = OK
    method = "(no method yet)"
    clientproto = "(no clientproto yet)"
    uri = "(no uri yet)"
    startedWriting = 0
    chunked = 0
    sentLength = 0 # content-length of response, or total bytes sent via chunking
    
    def __init__(self, channel, queued):
        """
        channel -- the channel we're connected to.
        queued -- are we in the request queue, or can we start writing to
                  the transport?
        """
        self.channel = channel
        self.queued = queued
        self.received_headers = {}
        self.received_cookies = {}
        if queued:
            self.transport = StringIO()
        else:
            self.transport = self.channel.transport
    
    def _cleanup(self):
        """Called when have finished responding and are no longer queued."""
        self.channel.requestDone(self)
        del self.channel
        self.content.close()
        del self.content
    
    # methods for channel - end users should not use these
    
    def noLongerQueued(self):
        """Notify the object that it is no longer queued.
        
        We start writing whatever data we have to the transport, etc.
        """
        if not self.queued:
            raise RuntimeError, "noLongerQueued() got called unnecessarily."
    
        self.queued = 0
        
        # set transport to real one and send any buffer data
        data = self.transport.getvalue()
        self.transport = self.channel.transport
        if data:
            self.transport.write(data)
        
        # if we have producer, register it with transport
        if self.producer is not None:
            self.transport.registerProducer(self.producer, self.streamingProducer)
        
        # if we're finished, clean up
        if self.finished:
            self._cleanup()
    
    def gotLength(self, length):
        if length < 100000:
            self.content = StringIO()
        else:
            self.content = tempfile.TemporaryFile()

    def parseCookies(self):
        cookietxt = self.getHeader("cookie")
        if cookietxt:
            for cook in string.split(cookietxt,'; '):
                try:
                    k, v = string.split(cook, '=')
                    self.received_cookies[k] = v
                except ValueError:
                    pass
    
    def handleContentChunk(self, data):
        """Write a chunk of data."""
        self.content.write(data)

    def requestReceived(self, command, path, version):
        """Called by channel when all data has been received."""
        self.content.seek(0,0)
        from string import split
        self.args = {}
        self.stack = []
        self.headers = {}
        self.cookies = [] # outgoing cookies
        
        self.method, self.uri = command, path
        self.clientproto = version
        x = split(self.uri,'?')

        if len(x) == 1:
            self.path = urllib.unquote(self.uri)
        else:
            if len(x) != 2:
                log.msg("May ignore parts of this invalid URI:",
                        repr(self.uri))
            self.path, argstring = urllib.unquote(x[0]), x[1]
            # parse the argument string
            for kvp in string.split(argstring, '&'):
                keyval = map(urllib.unquote, string.split(kvp, '='))
                if len(keyval) != 2:
                    continue
                key, value = keyval
                arg = self.args[key] = self.args.get(key, [])
                arg.append(value)

        # cache the client and server information, we'll need this later to be
        # serialized and sent with the request so CGIs will work remotely
        self.client = self.channel.transport.getPeer()
        self.host = self.channel.transport.getHost()

        # Argument processing
        args = self.args
        ctype = self.getHeader('content-type')
        if self.method == "POST" and ctype:
            mfd = 'multipart/form-data'
            key, pdict = cgi.parse_header(ctype)
            if key == 'application/x-www-form-urlencoded':
                args.update(
                    cgi.parse_qs(self.content.read()))
            elif key == mfd:
                args.update(
                    cgi.parse_multipart(self.content, pdict))
            else:
                pass
        
        self.process()

    def __repr__(self):
        return '<%s %s %s>'% (self.method, self.uri, self.clientproto)

    def process(self):
        """Override in subclasses."""
        pass

    
    # consumer interface
    
    def registerProducer(self, producer, streaming):
        """Register a producer."""
        self.producer = producer
        self.streamingProducer = streaming
        
        if self.queued:
            producer.pauseProducing()
        else:
            self.transport.registerProducer(producer, streaming)
    
    def unregisterProducer(self):
        """Unregister the producer."""
        if self.queued:
            del self.producer
        else:
            self.transport.unregisterProducer()
    
    
    # http response methods
    
    def _sendStatus(self, code, resp=''):
        """Send a status code."""
        self.transport.write('%s %s %s\r\n' % (self.clientproto, code, resp))

    def _sendHeader(self, name, value):
        """Send a header."""
        self.transport.write('%s: %s\r\n' % (name, value))

    def _endHeaders(self):
        """Finished sending headers."""
        self.transport.write('\r\n')

    def _sendError(self, code, resp=''):
        self._sendStatus(code, resp)
        self._endHeaders()

    
    # http request methods

    def getHeader(self, key):
        """Get a header that was sent from the network.
        """
        return self.received_headers.get(string.lower(key))

    def getCookie(self, key):
        """Get a cookie that was sent from the network.
        """
        return self.received_cookies.get(key)


    # The following is the public interface that people should be
    # writing to.

    def finish(self):
        """We are finished writing data."""
        if self.chunked:
            # write last chunk and closing CRLF
            self.transport.write("0\r\n\r\n")

        # log request
        self.channel.factory.log(self)
        
        self.finished = 1
        if not self.queued:
            self._cleanup()
    
    def write(self, data):
        """
        Write some data as a result of an HTTP request.  The first
        time this is called, it writes out response data.
        """
        if not self.startedWriting:
            self.startedWriting = 1
            if self.clientproto != "HTTP/0.9":
                message = RESPONSES.get(self.code, "Unknown Status")
                self._sendStatus(self.code, message)
                # if we don't have a content length, we sent data in chunked mode,
                # so that we can support pipelining in persistent connections.
                if self.clientproto == "HTTP/1.1" and self.headers.get('content-length', None) is None:
                    self._sendHeader('Transfer-encoding', 'chunked')
                    self.chunked = 1
                for name, value in self.headers.items():
                    self._sendHeader(string.capitalize(name), value)
                for cookie in self.cookies:
                    self._sendHeader("Set-Cookie", cookie)
                self._endHeaders()
            
            # if this is a "HEAD" request, we shouldn't return any data
            if self.method == "HEAD":
                self.write = lambda data: None
                return

        self.sentLength = self.sentLength + len(data)
        if self.chunked:
            self.transport.write(toChunk(data))
        else:
            self.transport.write(data)

    def addCookie(self, k, v, expires=None, domain=None, path=None, max_age=None, comment=None, secure=None):
        """Set an outgoing HTTP cookie.
        
        In general, you should consider using sessions instead of cookies,
        see self.getSession and the Session class for details.
        """
        cookie = '%s=%s' % (k, v)
        if expires != None:
            cookie = cookie +"; Expires=%s" % expires
        if domain != None:
            cookie = cookie +"; Domain=%s" % domain
        if path != None:
            cookie = cookie +"; Path=%s" % path
        if max_age != None:
            cookie = cookie +"; Max-Age=%s" % max_age
        if comment != None:
            cookie = cookie +"; Comment=%s" % comment
        if secure:
            cookie = cookie +"; Secure"
        self.cookies.append(cookie)

    def setResponseCode(self, code):
        """Set the HTTP response code.
        """
        self.code = code
    
    def setHeader(self, k, v):
        """Set an outgoing HTTP header.
        """
        self.headers[string.lower(k)] = v

    def getAllHeaders(self):
        return self.received_headers

    def getRequestHostname(self):
        """Get the hostname that the user passed in to the request.

        This will either use the Host: header (if it is available) or the 
        """
        return string.split(self.getHeader('host') or
                            socket.gethostbyaddr(self.getHost()[1]),
                            ':')[0]

    def getHost(self):
        """Get my originally requesting transport's host.

        Don't rely on the 'transport' attribute, since Request objects may be
        copied remotely.  For information on this method's return value, see
        twisted.internet.tcp.Port.
        """
        return self.host

    def getClientIP(self):
        if self.client[0] == 'INET':
            return self.client[1]
        else:
            return None

    def _authorize(self):
        # Authorization, (mostly) per the RFC
        try:
            authh = self.getHeader("Authorization")
            bas, upw = string.split(authh)
            upw = base64.decodestring(upw)
            self.user, self.password = string.split(upw,':')
        except:
            self.user = self.password = ""

    def getUser(self):
        try:
            return self.user
        except:
            pass
        self._authorize()
        return self.user

    def getPassword(self):
        try:
            return self.password
        except:
            pass
        self._authorize()
        return self.password

    def getClient(self):
        if self.client[0] != 'INET':
            return None
        host = self.client[1]
        try:
            name, names, addresses = socket.gethostbyaddr(host)
        except socket.error:
            return host
        names.insert(0, name)
        for name in names:
            if '.' in name:
                return name
        return names[0]


class HTTPChannel(basic.LineReceiver):
    """A receiver for HTTP requests."""
    
    length = 0
    persistent = 1
    __header = ''
    __first_line = 1
    __content = None
    
    # set in instances or subclasses
    requestFactory = Request

    
    def __init__(self):
        # the request queue
        self.requests = []

    def lineReceived(self, line):
        if self.__first_line:
            # if this connection is not persistent, drop any data which
            # the client (illegally) sent after the last request.
            if not self.persistent:
                self.dataReceived = self.lineReceived = lambda *args: None
                return
            
            # create a new Request object
            request = self.requestFactory(self, len(self.requests))
            self.requests.append(request)

            # IE sends an extraneous empty line (\r\n) after a POST request;
            # eat up such a line, but only ONCE
            if not line and self.__first_line == 1:
                self.__first_line = 2
                return
            self.__first_line = 0
            parts = string.split(line)
            if len(parts)<3:
                parts.append('HTTP/0.9') # isn't backwards compat great!
            if len(parts) != 3:
                self.transport.write("HTTP/1.1 400 Bad Request\r\n\r\n")
                self.transport.loseConnection()
                return
            command, request, version = parts
            self.__command = command
            self.__path = request
            self.__version = version
            if version == 'HTTP/0.9':
                self.allHeadersReceived()
                self.allContentReceived()
        elif line == '':
            if self.__header:
                self.headerReceived(self.__header)
            self.__header = ''
            self.allHeadersReceived()
            if self.length == 0:
                self.allContentReceived()
            else:
                self.setRawMode()
        elif line[0] in ' \t':
            self.__header = self.__header+'\n'+line
        else:
            if self.__header:
                self.headerReceived(self.__header)
            self.__header = line

    def headerReceived(self, line):
        """Do pre-processing (for content-length) and store this header away.
        """
        header, data = string.split(line, ':', 1)
        header = string.lower(header)
        data = string.strip(data)
        if header == 'content-length':
            self.length = int(data)
        self.requests[-1].received_headers[header] = data

    def allContentReceived(self):
        command = self.__command
        path = self.__path
        version = self.__version
        
        # reset ALL state variables, so we don't interfere with next request
        self.length = 0
        self.__header = ''
        self.__first_line = 1
        del self.__command, self.__path, self.__version

        req = self.requests[-1]
        req.requestReceived(command, path, version)

    def rawDataReceived(self, data):
        if len(data) < self.length:
            self.requests[-1].handleContentChunk(data)
            self.length = self.length - len(data)
        else:
            self.requests[-1].handleContentChunk(data[:self.length])
            extraneous = data[self.length:]
            self.allContentReceived()
            self.setLineMode(extraneous)

    def allHeadersReceived(self):
        req = self.requests[-1]
        req.parseCookies()
        self.persistent = self.checkPersistence(req, self.__version)
        req.gotLength(self.length)
    
    def checkPersistence(self, request, version):
        """Check if the channel should close or not."""
        connection = request.getHeader('connection')
        if connection:
            tokens = map(string.lower, string.split(connection, ' '))
        else:
            tokens = []

        # HTTP 1.0 persistent connection support is currently disabled,
        # since we need a way to disable pipelining. HTTP 1.0 can't do
        # pipelining since we can't know in advance if we'll have a
        # content-length header, if we don't have the header we need to close the
        # connection. In HTTP 1.1 this is not an issue since we use chunked
        # encoding if content-length is not available.
        
        #if version == "HTTP/1.0":
        #    if 'keep-alive' in tokens:
        #        request.setHeader('connection', 'Keep-Alive')
        #        return 1
        #    else:
        #        return 0
        if version == "HTTP/1.1":
            if 'close' in tokens:
                request.setHeader('connection', 'close')
                return 0
            else:
                return 1
        else:
            return 0
    
    def requestDone(self, request):
        """Called by first request in queue when it is done."""
        if request != self.requests[0]: raise TypeError
        del self.requests[0]

        if self.persistent:
            # notify next request it can start writing
            if self.requests:
                self.requests[0].noLongerQueued()
        else:
            self.transport.loseConnection()


class HTTPFactory(protocol.ServerFactory):
    """Factory for HTTP server."""

    logPath = None
    
    def __init__(self, logPath=None):
        self.logPath = logPath

    def startFactory(self):
        if self.logPath:
            self.logFile = self._openLogFile(self.logPath)
        else:
            self.logFile = sys.stdout

    def stopFactory(self):
        if hasattr(self, "logFile"):
            self.logFile.close()
            del self.logFile

    def _openLogFile(self, path):
        """Override in subclasses, e.g. to use lumberjack."""
        f = open(path, "a")
        f.seek(2, 0)
        return f
    
    def log(self, request):
        """Log a request's result to the logfile, by default in combined log format."""
        line = '%s - %s %s "%s" %d %s "%s" "%s"\n' % (
            request.getClientIP(),
            request.getUser() or "-",
            datetimeToLogString(),
            repr(request),
            request.code,
            request.sentLength or "-",
            request.getHeader("referer") or "-",
            request.getHeader("user-agent") or "-")
        self.logFile.write(line)

