# -*- test-case-name: twisted.test.test_http -*-

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

API Stability: Server HTTP support is semi-stable, client HTTP is unstable.

Future Plans:
 - HTTP client support will at some point be refactored to support HTTP/1.1.
 - Accept chunked data from clients in server.
 - Other missing HTTP features from the RFC.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# system imports
from cStringIO import StringIO
import tempfile
import base64
import cgi
import socket
import math
import time
import calendar

# sibling imports
import basic

# twisted imports
from twisted.internet import interfaces, reactor, protocol
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

CACHED = """Magic constant returned by http.Request methods to set cache
validation headers when the request is conditional and the value fails
the condition."""

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


# a  hack so we don't need to recalculate log datetime every hit,
# at the price of a small, unimportant, inaccuracy.
logDateTime = None

def _resetLogDateTime():
    global logDateTime
    logDateTime = datetimeToLogString()
    reactor.callLater(1, _resetLogDateTime)

_resetLogDateTime()


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
    parts = dateString.split(' ')
    day = int(parts[1])
    month = int(monthname.index(parts[2]))
    year = int(parts[3])
    hour, min, sec = map(int, parts[4].split(':'))
    return int(timegm(year, month, day, hour, min, sec))

def toChunk(data):
    """Convert string to a chunk."""
    return "%x\r\n%s\r\n" % (len(data), data)

def fromChunk(data):
    """Convert chunk to string.

    Returns tuple (result, remaining), may raise ValueError.
    """
    prefix, rest = data.split('\r\n', 1)
    length = int(prefix, 16)
    if not rest[length:length+2] == '\r\n':
        raise ValueError, "chunk must end with CRLF"
    return rest[:length], rest[length+2:]



class StringTransport:
    """
    I am a StringIO wrapper that conforms for the transport API. I support
    the `writeSequence' method.
    """
    def __init__(self):
        self.s = StringIO()
    def writeSequence(self, seq):
        self.s.write(''.join(seq))
    def __getattr__(self, attr):
        return getattr(self.__dict__['s'], attr)


class HTTPClient(basic.LineReceiver):
    """A client for HTTP 1.0

    Notes:
    You probably want to send a 'Host' header with the name of
    the site you're connecting to, in order to not break name
    based virtual hosting.
    """
    length = None
    firstLine = 1
    __buffer = ''

    def sendCommand(self, command, path):
        self.transport.write('%s %s HTTP/1.0\r\n' % (command, path))

    def sendHeader(self, name, value):
        self.transport.write('%s: %s\r\n' % (name, value))

    def endHeaders(self):
        self.transport.write('\r\n')

    def lineReceived(self, line):
        if self.firstLine:
            self.firstLine = 0
            version, status, message = line.split(None, 2)
            self.handleStatus(version, status, message)
            return
        if line:
            key, val = line.split(': ', 1)
            self.handleHeader(key, val)
            if key.lower() == 'content-length':
                self.length = int(val)
        else:
            self.handleEndHeaders()
            self.setRawMode()

    def connectionLost(self, reason):
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
    code_message = RESPONSES[OK]
    method = "(no method yet)"
    clientproto = "(no clientproto yet)"
    uri = "(no uri yet)"
    startedWriting = 0
    chunked = 0
    sentLength = 0 # content-length of response, or total bytes sent via chunking
    etag = None
    lastModified = None

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
        self.headers = {} # outgoing headers
        self.cookies = [] # outgoing cookies

        if queued:
            self.transport = StringTransport()
        else:
            self.transport = self.channel.transport

    def _cleanup(self):
        """Called when have finished responding and are no longer queued."""
        self.channel.requestDone(self)
        del self.channel
        try:
            self.content.close()
        except OSError:
            # win32 suckiness, no idea why it does this
            pass
        del self.content

    # methods for channel - end users should not use these

    def noLongerQueued(self):
        """Notify the object that it is no longer queued.

        We start writing whatever data we have to the transport, etc.

        This method is not intended for users.
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
        """Called when HTTP channel got length of content in this request.

        This method is not intended for users.
        """
        if length < 100000:
            self.content = StringIO()
        else:
            self.content = tempfile.TemporaryFile()

    def parseCookies(self):
        """Parse cookie headers.

        This method is not intended for users."""
        cookietxt = self.getHeader("cookie")
        if cookietxt:
            for cook in cookietxt.split('; '):
                try:
                    k, v = cook.split('=')
                    self.received_cookies[k] = v
                except ValueError:
                    pass

    def handleContentChunk(self, data):
        """Write a chunk of data.

        This method is not intended for users.
        """
        self.content.write(data)

    def requestReceived(self, command, path, version):
        """Called by channel when all data has been received.

        This method is not intended for users.
        """
        self.content.seek(0,0)
        self.args = {}
        self.stack = []

        self.method, self.uri = command, path
        self.clientproto = version
        x = self.uri.split('?')

        if len(x) == 1:
            self.path = self.uri
        else:
            if len(x) != 2:
                log.msg("May ignore parts of this invalid URI: %s"
                        % repr(self.uri))
            self.path, argstring = x[0], x[1]
            self.args = cgi.parse_qs(argstring, 1)

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
                    cgi.parse_qs(self.content.read(), 1))
            elif key == mfd:
                args.update(
                    cgi.parse_multipart(self.content, pdict))
            else:
                pass

        self.process()

    def __repr__(self):
        return '<%s %s %s>'% (self.method, self.uri, self.clientproto)

    def process(self):
        """Override in subclasses.

        This method is not intended for users.
        """
        pass


    # consumer interface

    def registerProducer(self, producer, streaming):
        """Register a producer."""

        self.streamingProducer = streaming

        if self.queued:
            self.producer = producer
            producer.pauseProducing()
        else:
            self.transport.registerProducer(producer, streaming)

    def unregisterProducer(self):
        """Unregister the producer."""
        if self.queued:
            del self.producer
        else:
            self.transport.unregisterProducer()


    # private http response methods

    def _sendError(self, code, resp=''):
        self.transport.write('%s %s %s\r\n\r\n' % (self.clientproto, code, resp))


    # http request methods

    def getHeader(self, key):
        """Get a header that was sent from the network.
        """
        return self.received_headers.get(key.lower())

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
        elif not self.startedWriting:
            # write headers
            self.write('')

        # log request
        if hasattr(self.channel, "factory"):
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
            version = self.clientproto
            if version != "HTTP/0.9":
                l = []
                l.append('%s %s %s\r\n' % (version, self.code,
                                           self.code_message))
                # if we don't have a content length, we send data in
                # chunked mode, so that we can support pipelining in
                # persistent connections.
                if ((version == "HTTP/1.1") and
                    (self.headers.get('content-length', None) is None)):
                    l.append("%s: %s\r\n" %
                             ('Transfer-encoding', 'chunked'))
                    self.chunked = 1
                if self.lastModified is not None:
                    if self.headers.has_key('last-modified'):
                        log.msg("Warning: last-modified specified both in"
                                " header list and lastModified attribute.")
                    else:
                        self.setHeader('last-modified',
                                       datetimeToString(self.lastModified))
                if self.etag is not None:
                    self.setHeader('ETag', self.etag)
                for name, value in self.headers.items():
                    l.append("%s: %s\r\n" % (name.capitalize(), value))
                for cookie in self.cookies:
                    l.append('%s: %s\r\n' % ("Set-Cookie", cookie))
                l.append("\r\n")

                self.transport.writeSequence(l)

            # if this is a "HEAD" request, we shouldn't return any data
            if self.method == "HEAD":
                self.write = lambda data: None
                return

        self.sentLength = self.sentLength + len(data)
        if data:
            if self.chunked:
                self.transport.write(toChunk(data))
            else:
                self.transport.write(data)
        else:
            log.msg("(harmless warning): discarding zero-length data for request %s" % self)

    def addCookie(self, k, v, expires=None, domain=None, path=None, max_age=None, comment=None, secure=None):
        """Set an outgoing HTTP cookie.

        In general, you should consider using sessions instead of cookies, see
        twisted.web.server.Resource.getSession and the
        twisted.web.server.Session class for details.
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

    def setResponseCode(self, code, message=None):
        """Set the HTTP response code.
        """
        self.code = code
        if message:
            self.code_message = message
        else:
            self.code_message = RESPONSES.get(code, "Unknown Status")

    def setHeader(self, k, v):
        """Set an outgoing HTTP header.
        """
        self.headers[k.lower()] = v

    def redirect(self, url):
        """Utility function that does a redirect.

        The request should have finish() called after this.
        """
        self.setResponseCode(FOUND)
        self.setHeader("location", url)

    def setLastModified(self, when):
        """Set the X{Last-Modified} time for the response to this request.

        If I am called more than once, I ignore attempts to set
        Last-Modified earlier, only replacing the Last-Modified time
        if it is to a later value.

        If I am a conditional request, I may modify my response code
        to L{NOT_MODIFIED} if appropriate for the time given.

        @param when: The last time the resource being returned was
            modified, in seconds since the epoch.
        @type when: number
        @return: If I am a X{If-Modified-Since} conditional request and
            the time given is not newer than the condition, I return
            L{http.CACHED<CACHED>} to indicate that you should write no
            body.  Otherwise, I return a false value.
        """
        # time.time() may be a float, but the HTTP-date strings are
        # only good for whole seconds.
        when = long(math.ceil(when))
        if (not self.lastModified) or (self.lastModified < when):
            self.lastModified = when

        modified_since = self.getHeader('if-modified-since')
        if modified_since:
            modified_since = stringToDatetime(modified_since)
            if modified_since >= when:
                self.setResponseCode(NOT_MODIFIED)
                return CACHED
        return None

    def setETag(self, etag):
        """Set an X{entity tag} for the outgoing response.

        That's \"entity tag\" as in the HTTP/1.1 X{ETag} header, \"used
        for comparing two or more entities from the same requested
        resource.\"

        If I am a conditional request, I may modify my response code
        to L{NOT_MODIFIED} or L{PRECONDITION_FAILED}, if appropriate
        for the tag given.

        @param etag: The entity tag for the resource being returned.
        @type etag: string
        @return: If I am a X{If-None-Match} conditional request and
            the tag matches one in the request, I return
            L{http.CACHED<CACHED>} to indicate that you should write
            no body.  Otherwise, I return a false value.
        """
        if etag:
            self.etag = etag

        tags = self.getHeader("if-none-match")
        if tags:
            tags = tags.split()
            if (etag in tags) or ('*' in tags):
                self.setResponseCode(((self.method in ("HEAD", "GET"))
                                      and NOT_MODIFIED)
                                     or PRECONDITION_FAILED)
                return CACHED
        return None

    def getAllHeaders(self):
        """Return dictionary of all headers the request received."""
        return self.received_headers

    def getRequestHostname(self):
        """Get the hostname that the user passed in to the request.

        This will either use the Host: header (if it is available) or the
        host we are listening on if the header is unavailable.
        """
        return (self.getHeader('host') or socket.gethostbyaddr(self.getHost()[1])).split(':')[0]

    def getHost(self):
        """Get my originally requesting transport's host.

        Don't rely on the 'transport' attribute, since Request objects may be
        copied remotely.  For information on this method's return value, see
        twisted.internet.tcp.Port.
        """
        return self.host

    def setHost(self, host, port, ssl=0):
        """Change the host and port the request thinks it's using.

        This method is useful for working with reverse HTTP proxies (e.g.
        both Squid and Apache's mod_proxy can do this), when the address
        the HTTP client is using is different than the one we're listening on.

        For example, Apache may be listening on https://www.example.com, and then
        forwarding requests to http://localhost:8080, but we don't want HTML produced
        by Twisted to say 'http://localhost:8080', they should say 'https://www.example.com',
        so we do::

           request.setHost('www.example.com', 443, ssl=1)

        This method is experimental.
        """
        if ssl:
            method = 'SSL'
        else:
            method = 'INET'
        self.received_headers["host"] = host
        self.host = (method, host, port)

    def getClientIP(self):
        if self.client[0] in ('INET', 'SSL'):
            return self.client[1]
        else:
            return None

    def isSecure(self):
        return (self.host[0] == 'SSL')

    def _authorize(self):
        # Authorization, (mostly) per the RFC
        try:
            authh = self.getHeader("Authorization")
            bas, upw = authh.split()
            upw = base64.decodestring(upw)
            self.user, self.password = upw.split(':')
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
        if self.client[0] not in ('INET', 'SSL'):
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
            parts = line.split()
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
        header, data = line.split(':', 1)
        header = header.lower()
        data = data.strip()
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
            tokens = map(lambda x: x.lower(), connection.split(' '))
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

    protocol = HTTPChannel

    logPath = None

    def __init__(self, logPath=None):
        self.logPath = logPath

    def startFactory(self):
        if self.logPath:
            self.logFile = self._openLogFile(self.logPath)
        else:
            self.logFile = log.logfile

    def stopFactory(self):
        if hasattr(self, "logFile"):
            if self.logFile != log.logfile:
                self.logFile.close()
            del self.logFile

    def _openLogFile(self, path):
        """Override in subclasses, e.g. to use lumberjack."""
        f = open(path, "a")
        f.seek(2, 0)
        return f

    def log(self, request):
        """Log a request's result to the logfile, by default in combined log format."""
        line = '%s - - %s "%s" %d %s "%s" "%s"\n' % (
            request.getClientIP(),
            # request.getUser() or "-", # the remote user is almost never important
            logDateTime,
            repr(request),
            request.code,
            request.sentLength or "-",
            request.getHeader("referer") or "-",
            request.getHeader("user-agent") or "-")
        self.logFile.write(line)
        self.logFile.flush()
