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

The second coming.

Future Plans:
 - HTTP client support will at some point be refactored to support HTTP/1.1.
 - Accept chunked data from clients in server.
 - Other missing HTTP features from the RFC.

Maintainer: U{James Y Knight <mailto:foom@fuhm.net>}

"""

# system imports
from cStringIO import StringIO
import tempfile
import base64, binascii
import cgi
import socket
import math
import time
import calendar
import warnings
import os

# twisted imports
from twisted.internet import interfaces, reactor, protocol, address
from twisted.protocols import policies, basic
from twisted.python import log, components
try: # try importing the fast, C version
    from twisted.protocols._c_urlarg import unquote
except ImportError:
    from urllib import unquote

# sibling imports
import responsecode
import http_headers

protocol_version = "HTTP/1.1"


def parse_qs(qs, keep_blank_values=0, strict_parsing=0, unquote=unquote):
    """like cgi.parse_qs, only with custom unquote function"""
    d = {}
    items = [s2 for s1 in qs.split("&") for s2 in s1.split(";")]
    for item in items:
        try:
            k, v = item.split("=", 1)
        except ValueError:
            if strict_parsing:
                raise
            continue
        if v or keep_blank_values:
            k = unquote(k.replace("+", " "))
            v = unquote(v.replace("+", " "))
            if k in d:
                d[k].append(v)
            else:
                d[k] = [v]
    return d

def toChunk(data):
    """Convert string to a chunk.
    
    @returns: a tuple of strings representing the chunked encoding of data"""
    return ("%X\r\n" % len(data), data, "\r\n")
    

class StringTransport:
    """
    I am a StringIO wrapper that conforms for the transport API. I support
    the 'writeSequence' method.
    """
    def __init__(self):
        self.s = StringIO()
    def writeSequence(self, seq):
        self.s.write(''.join(seq))
    def __getattr__(self, attr):
        return getattr(self.__dict__['s'], attr)

# response codes that must have empty bodies
NO_BODY_CODES = (204, 304, 100, 101)

class Request:
    """A HTTP request.

    Subclasses should override the process() method to determine how
    the request will be processed.
    
    @ivar method: The HTTP method that was used.
    @ivar uri: The full URI that was requested (includes arguments).
    @ivar path: The path only (arguments not included).
    @ivar args: All of the arguments, including URL and POST arguments.
    @type args: A mapping of strings (the argument names) to lists of values.
                i.e., ?foo=bar&foo=baz&quux=spam results in
                {'foo': ['bar', 'baz'], 'quux': ['spam']}.
    @ivar received_headers: All received headers
    """

    __implements__ = interfaces.IConsumer,

    code = responsecode.OK
    code_message = None
    startedWriting = 0
    sentLength = 0 # content bytes sent to client

    _foreceSSL = False
    
    
    def __init__(self, chanRequest, command, path, version, in_headers):
        """
        @param chanRequest: the channel request we're associated with.
        """
        self.chanRequest = chanRequest
        self.method = command
        self.uri = path
        self.clientproto = version

        self.out_headers = http_headers.Headers()
        self.in_headers = in_headers
        self.process()

    def process(self):
        """Called by __init__ to let you process the request.

        Can be overridden by a subclass to do something useful."""
        pass
    
    def handleContentChunk(self, data):
        """Called by channel when a piece of data has been received.

        Should be overridden by a subclass to do something appropriate."""
        pass
    
    def handleContentComplete(self):
        """Called by channel when all data has been received.

        Should be overridden by a subclass to do something appropriate."""
        
    def connectionLost(self, reason):
        """connection was lost"""
        pass


    def __repr__(self):
        return '<%s %s %s>'% (self.method, self.uri, self.clientproto)

    # private http response methods

    def _sendError(self, code, resp=''):
        self.transport.write('%s %s %s\r\n\r\n' % (self.clientproto, code, resp))
    
    # The following is the public interface that people should be
    # writing to.

    def finish(self):
        """We are finished writing data."""
        print "Request.finish, startedWriting=", self.startedWriting
        if not self.startedWriting:
            # write headers
            self.write('')
        
        # log request
        if hasattr(self.chanRequest.channel, "factory"):
            self.chanRequest.channel.factory.log(self)

        self.chanRequest.finish()

    def write(self, data):
        """
        Write some data as a result of an HTTP request.  The first
        time this is called, it writes out response headers.
        """
        if not self.startedWriting:
            self.startedWriting = 1
            self.chanRequest.writeHeaders(self.code, self.out_headers, code_message=self.code_message)
        
        # if this is a "HEAD" request, we shouldn't return any data
        if self.method == "HEAD":
            self.write = lambda data: None
            return False

        # for certain result codes, we should never return any data
        if self.code in NO_BODY_CODES:
            self.write = lambda data: None
            return False
        
        self.sentLength = self.sentLength + len(data)
        if data:
            self.chanRequest.writeData(data)

    # FIXME: usefulize this
    def writeFile(self, file):
        """
        Write data from a file, possibly more efficiently than write(data)
        would do. Otherwise identical to write(file.read()).
v        """
        self.write(file.read())
        
    def setResponseCode(self, code, message=None):
        """Set the HTTP response code.
        """
        self.code = code
        self.code_message = message

    def redirect(self, url):
        """Utility function that does a redirect.

        The request should have finish() called after this.
        """
        self.setResponseCode(FOUND)
        self.out_headers.setHeader("location", url)
    
    def setLastModified(self, when):
        """Set the X{Last-Modified} time for the response to this request.

        If I am called more than once, I ignore attempts to set
        Last-Modified earlier, only replacing the Last-Modified time
        if it is to a later value.

        @param when: The last time the resource being returned was
            modified, in seconds since the epoch.
        @type when: number
        """
        # time.time() may be a float, but the HTTP-date strings are
        # only good for whole seconds.
        when = long(math.ceil(when))
        lastModified = self.out_headers.getHeader('Last-Modified')
        if not lastModified or (lastModified < when):
            self.out_headers.setHeader('Last-Modified', when)
        
    def checkBody(self):
        """Check to see if this request should have a body. As a side-effect
        may modify my response code to L{NOT_MODIFIED} or L{PRECONDITION_FAILED},
        if appropriate.
        
        Call this function after setting the ETag and Last-Modified
        output headers, but before actually proceeding with request
        processing.
        
        This examines the appropriate request headers for conditionals,
        the existing response headers and sets the response code as necessary.
        
        @return: True if you should write a body, False if you should
                 not.
        """
        tags = self.in_headers.getHeader("if-none-match")
        etag = self.out_headers.getHeader("etag")
        if tags:
            if (etag in tags) or ('*' in tags):
                self.setResponseCode(((self.method in ("HEAD", "GET"))
                                      and NOT_MODIFIED)
                                     or PRECONDITION_FAILED)
                return False

        modified_since = self.in_headers.getHeader('if-modified-since')
        if modified_since:
            if modified_since >= self.lastModified:
                self.setResponseCode(NOT_MODIFIED)
                return False

        # if this is a "HEAD" request, we shouldn't return any data
        if self.method == "HEAD":
            return False
        
        return True
        
    def getRequestHostname(self):
        """Get the hostname that the user passed in to the request.

        This will either use the Host: header (if it is available) or the
        host we are listening on if the header is unavailable.
        """
        return (self.in_headers.getHeader('host') or
                socket.gethostbyaddr(self.getHost()[1])[0]
                ).split(':')[0]

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
        self._forceSSL = ssl
        self.received_headers["host"] = host
        self.host = address.IPv4Address("TCP", host, port)

    def getClientIP(self):
        if isinstance(self.client, address.IPv4Address):
            return self.client.host
        else:
            return None

    def isSecure(self):
        return self._forceSSL or components.implements(self.channel.transport, interfaces.ISSLTransport)

    def _authorize(self):
        # Authorization, (mostly) per the RFC
        try:
            authh = self.in_headers.getHeaderRaw("Authorization")
            if not authh:
                self.user = self.password = ''
                return
                
            bas, upw = authh.split()
            if bas.lower() != "basic":
                raise ValueError
            upw = base64.decodestring(upw)
            self.user, self.password = upw.split(':', 1)
        except (binascii.Error, ValueError):
            self.user = self.password = ""
        except:
            log.err()
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

class ChannelRequest:
    headerlen = 0
    length = None
    chunkedIn = False
    reqHeaders = None
    command = path = version = None
    partialHeader = ''
    queued = 0
    
    channel = None
    request = None
    
    def __init__(self, channel, initialLine, queued=0):
        self.reqHeaders = http_headers.Headers()
        self.channel = channel
        self.queued=queued

        print "New ChannelRequest, %s, queued=%s" %(initialLine, queued)
        if queued:
            self.transport = StringTransport()
        else:
            self.transport = self.channel.transport


        parts = initialLine.split()
        if len(parts) != 3:
            self.transport.write("HTTP/1.1 400 Bad Request\r\n\r\n")
            self.transport.loseConnection()
            return
        self.command, self.path, self.version = parts
        
    def lineReceived(self, line):
        if self.chunkedIn:
            # Parsing a chunked input
            if self.chunkedIn == 1:
                # First we get a line like "chunk-size [';' chunk-extension]"
                # (where chunk extension is just random crap as far as we're concerned)
                chunksize = line.split(';', 1)[0]
                try:
                    self.length = int(chunksize, 16)
                except:
                    raise BadRequest("Invalid chunk size, not a hex number: %s!" % chunksize)

                if self.length == 0:
                    self.chunkedIn = 3
                else:
                    self.channel.setRawMode()
            elif self.chunkedIn == 2:
                # After we got data bytes of the appropriate length, we end up here,
                # waiting for the CRLF, then go back to get the next chunk size.
                if line != '':
                    raise BadRequest("Excess %d bytes sent in chunk transfer mode" % len(line))
                self.chunkedIn = 1
            elif self.chunkedIn == 3:
                # TODO: support Trailers (maybe! but maybe not!)
                
                # After getting the final "0" chunk we're here, and we *EAT MERCILESSLY*
                # any trailer headers sent, and wait for the blank line to terminate the
                # request.
                if line == '':
                    self.allContentReceived()
        elif line == '':
            if self.partialHeader:
                self.headerReceived(self.partialHeader)
            self.partialHeader = ''
            self.allHeadersReceived()
            if self.chunkedIn:
                pass
            elif self.length == 0:
                self.allContentReceived()
            else:
                self.channel.setRawMode()
        elif line[0] in ' \t':
            self.partialHeader = self.partialHeader+line
        else:
            if self.partialHeader:
                self.headerReceived(self.partialHeader)
            self.partialHeader = line

    def rawDataReceived(self, data):
        datalen = len(data)
        if datalen < self.length:
            self.request.handleContentChunk(data)
            self.length = self.length - datalen
        else:
            self.request.handleContentChunk(data[:self.length])
            extraneous = data[self.length:]
            channel = self.channel # could go away from allContentReceived.
            # NOTE: in chunked mode, size is the size of the current chunk.
            if self.chunkedIn == 0:
                self.allContentReceived()
            else:
                self.chunkedIn = 2 # Read next chunksize
            
            channel.setLineMode(extraneous)

    def headerReceived(self, line):
        """Store this header away. Check for too much header data
           (> channel.maxHeaderLength) and abort the connection if so.
        """
        nameval = line.split(':', 1)
        if len(nameval) != 2:
            self.FIXME.transport.write("HTTP/1.1 400 Bad Request\r\n\r\n")
            self.FIXME.transport.loseConnection()
        
        name, val = nameval
        val.lstrip(' \t')
        self.reqHeaders._addHeader(name, val)
        
        self.headerlen = self.headerlen+ len(line)
        
        if self.headerlen > self.channel.maxHeaderLength:
            self.FIXME.transport.write("HTTP/1.1 400 Bad Request\r\n\r\n")
            self.FIXME.transport.loseConnection()
            
    def allHeadersReceived(self):
        print "allHeadersReceived"
        # Split off connection-related headers
        connHeaders = self.splitConnectionHeaders()

        print "ConnHeaders: ",connHeaders
        # Set connection parameters from headers
        self.setConnectionParams(connHeaders)

        request = self.channel.requestFactory(self, self.command, self.path, self.version, self.reqHeaders)
        self.channel.queueRequest(self)
        
        # Reset header state variables
        del self.reqHeaders
        
        self.connHeaders = connHeaders
        self.request = request
        
    def allContentReceived(self):
        self.channel.requestReadFinished(self, self.persistent)
        
        self.request.handleContentComplete()
        
        
    def splitConnectionHeaders(self):
        # Split off headers for the connection from headers for the request.
        
        def move(name):
            h = reqHeaders.getRawHeader(name, None)
            if h is not None:
                reqHeaders.removeHeader(name)
                connHeaders.setRawHeader(name, h)

        # NOTE: According to HTTP spec, we're supposed to eat the
        # 'Proxy-Authenticate' and 'Proxy-Authorization' headers also, but that
        # doesn't sound like a good idea to me, because it makes it impossible
        # to have a non-authenticating transparent proxy in front of an
        # authenticating proxy. An authenticating proxy can eat them itself.
        
        connHeaderNames = ['Connection', 'Keep-Alive', 'TE', 'Trailers',
                           'Transfer-Encoding', 'Upgrade']
        reqHeaders = self.reqHeaders
        connHeaders = http_headers.Headers()
        
        move('Connection')
        if self.version != "HTTP/1.1":
            # Remove all headers mentioned in Connection, because a HTTP 1.0
            # proxy might have erroneously forwarded it from a 1.1 client.
            for name in connHeaders.getHeader('Connection', ()):
                if reqHeaders.hasHeader(name):
                    reqHeaders.removeHeader(name)
        else:
            # Otherwise, just add the headers listed to the list of those to move
            connHeaderNames.extend(connHeaders.getHeader('Connection', ()))
        
        for headername in connHeaderNames:
            move(headername)
        
        # Content-Length is both a connection header (defining length of
        # transmission, and a content header (defining length of content).
        h = reqHeaders.getRawHeader('Content-Length', None)
        if h is not None:
            connHeaders.setRawHeader('Content-Length', h)
        
        return connHeaders

    def setConnectionParams(self, connHeaders):
        # HTTP 1.0 persistent connection support is unimplemented:
        # we need a way to disable pipelining. HTTP 1.0 can't do
        # pipelining since we can't know in advance if we'll have a
        # outgoing content-length header. If we don't have the header
        # we need to close the connection. In HTTP 1.1 this is not an
        # issue since we use chunked encoding if content-length is
        # not available.

        # Also, who really cares about extra features for HTTP/1.0; nearly
        # everything supports 1.1 these days, so as long as 1.0 *works*, that's
        # fine. (Hrm just noticed, Squid only supports HTTP 1.0 so far, so this
        # might be an issue worth thinking about after all)
        
        if (self.version == "HTTP/1.1"
            and not 'close' in connHeaders.getHeader('connection', ())):
            self.persistent = True
        else:
            self.persistent = False


        # Okay, now implement section 4.4 Message Length to determine
        # how to find the end of the incoming HTTP message.
        print connHeaders
        transferEncoding = connHeaders.getHeader('Transfer-Encoding')
        
        print "TransferEncoding:", transferEncoding
        if transferEncoding:
            try: # Why doesn't list have a .find? stupid python.
                i = transferEncoding.index('chunked')
            except:
                i = -1
            
            if i != -1:
                # Chunked
                self.chunkedIn = 1
                if i != len(transferEncoding) - 1:
                    # Not last element.
                    raise BadRequest("Transfer-Encoding sent with chunked encoding in a non-final position.")
            else:
                # Would close on end of connection, except this can't happen for
                # client->server data.
                raise BadRequest("Transfer-Encoding sent without chunked encoding.")
            
            # Cut off the chunked encoding (cause it's special)
            transferEncoding = transferEncoding[:-1]
            # TODO: support gzip/etc encodings.
            # FOR NOW: report an error if the client uses any encodings.
            # They shouldn't, because we didn't send a TE: header saying it's okay.
            if transferEncoding:
                raise BadRequest("Transfer-Encoding %s not supported." % transferEncoding)
        else:
            # No transfer-coding.
            # If no Content-Length either, assume no content.
            self.length = connHeaders.getHeader('Content-Length', 0)
            self.chunkedIn = 0
        print "ChunkedIn: ", self.chunkedIn
    
############## ChannelRequest *RESPONSE* methods #############
    producer = None
    chunkedOut = False
    finished = 0
    
    ##### Request Callbacks #####
    def writeHeaders(self, code, headers, outversion="HTTP/1.1", code_message=None):
        l = []
        if code_message is None:
            code_message = responsecode.RESPONSES.get(code, "Unknown Status")
        
        l.append('%s %s %s\r\n' % (outversion, code,
                                   code_message))
        for name, valuelist in headers._raw_headers.items():
            for value in valuelist:
                l.append("%s: %s\r\n" % (name, value))
        # if we don't have a content length, we send data in
        # chunked mode, so that we can support pipelining in
        # persistent connections.
        if ((self.version == "HTTP/1.1") and
            (headers.getHeader('Content-Length') is None) and
            not (code in NO_BODY_CODES)):
            l.append("%s: %s\r\n" % ('Transfer-encoding', 'chunked'))
            self.chunkedOut = 1
        l.append("\r\n")
        self.transport.writeSequence(l)
        
    
    def writeData(self, data):
        if self.chunkedOut:
            self.transport.writeSequence(toChunk(data))
        else:
            self.transport.write(data)
        
    def finish(self):
        """We are finished writing data."""
        if self.finished:
            warnings.warn("Warning! request.finish called twice.", stacklevel=2)
            return
        
        if self.chunkedOut:
            # write last chunk and closing CRLF
            self.transport.write("0\r\n\r\n")
        
        self.finished = 1
        if not self.queued:
            self._cleanup()

    ##### End Request Callbacks #####

    def _cleanup(self):
        """Called when have finished responding and are no longer queued."""
        if self.producer:
            log.err(RuntimeError("Producer was not unregistered for %s" % self.uri))
            self.unregisterProducer()
        self.channel.requestWriteFinished(self, self.persistent)
        del self.channel
        del self.transport
        
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
        if (self.producer is not None) and not self.finished:
            self.transport.registerProducer(self.producer, True)

        # if we're finished, clean up
        if self.finished:
            self._cleanup()


    # consumer interface
    def registerProducer(self, producer, streaming):
        """Register a producer.
        """
        
        if self.producer:
            raise ValueError, "registering producer %s before previous one (%s) was unregistered" % (producer, self.producer)
        
        self.producer = producer
        
        if self.queued:
            producer.pauseProducing()
        else:
            self.transport.registerProducer(producer, streaming)

    def unregisterProducer(self):
        """Unregister the producer."""
        if not self.queued:        
            self.transport.unregisterProducer()
        self.producer = None

    def connectionLost(self, reason):
        """connection was lost"""
        self.request.connectionLost(reason)

    
class HTTPChannel(basic.LineReceiver, policies.TimeoutMixin):
    """A receiver for HTTP requests. Handles the hop-by-hop behavior."""

    # set in instances or subclasses
    maxHeaderLength = 10240 # maximum length of headers (10KiB)
    chanRequestFactory = ChannelRequest
    
    _first_line = 1
    _savedTimeOut = None
    persistent = True

    def __init__(self):
        # the request queue
        self.requests = []
        
    def connectionMade(self):
        self.setTimeout(self.timeOut)
    
    def lineReceived(self, line):
        self.resetTimeout()
        if self._first_line:
            # if this connection is not persistent, drop any data which
            # the client (illegally) sent after the last request.
            if not self.persistent:
                self.dataReceived = self.lineReceived = lambda *args: None
                return

            # IE sends an extraneous empty line (\r\n) after a POST request;
            # eat up such a line, but only ONCE
            if not line and self._first_line == 1:
                self._first_line = 2
                return
            
            self._first_line = 0
            self.chanRequest = self.chanRequestFactory(self, line, len(self.requests))
        else:
            self.chanRequest.lineReceived(line)
        
    def rawDataReceived(self, data):
        self.resetTimeout()
        self.chanRequest.rawDataReceived(data)

    def queueRequest(self, request):
        # create a new Request object
        self.requests.append(request)
        
    def requestReadFinished(self, request, persist):
        # reset state variables
        self.persistent = persist
        self._first_line = 1
        self.chanRequest = None
        
        # Disable the idle timeout, in case this request takes a long
        # time to finish generating output.
        if self.timeOut:
            self._savedTimeOut = self.setTimeout(None)
        
        
    def requestWriteFinished(self, request, persistent):
        """Called by first request in queue when it is done."""
        if request != self.requests[0]: raise TypeError
        del self.requests[0]
        
        if persistent:
            # notify next request it can start writing
            if self.requests:
                self.requests[0].noLongerQueued()
            else:
                if self._savedTimeOut:
                    self.setTimeout(self._savedTimeOut)
        else:
            self.transport.loseConnection()

    def timeoutConnection(self):
        log.msg("Timing out client: %s" % str(self.transport.getPeer()))
        policies.TimeoutMixin.timeoutConnection(self)

    def connectionLost(self, reason):
        self.setTimeout(None)
        for request in self.requests:
            request.connectionLost(reason)

    

class HTTPFactory(protocol.ServerFactory):
    """Factory for HTTP server."""

    protocol = HTTPChannel
    requestFactory = Request
    
    logPath = None
    
    timeOut = 60 * 60 * 12

    def __init__(self, logPath=None, timeout=60*60*12):
        if logPath is not None:
            logPath = os.path.abspath(logPath)
        self.logPath = logPath
        self.timeOut = timeout

    def buildProtocol(self, addr):
        p = protocol.ServerFactory.buildProtocol(self, addr)

        p.requestFactory = self.requestFactory
        # timeOut needs to be on the Protocol instance cause
        # TimeoutMixin expects it there
        p.timeOut = self.timeOut
        return p

    def startFactory(self):
#        _logDateTimeStart()
        if self.logPath:
            self.logFile = self._openLogFile(self.logPath)
        else:
            self.logFile = log.logfile

    def stopFactory(self):
        if hasattr(self, "logFile"):
            if self.logFile != log.logfile:
                self.logFile.close()
            del self.logFile
#        _logDateTimeStop()

    def _openLogFile(self, path):
        """Override in subclasses, e.g. to use twisted.python.logfile."""
        f = open(path, "a", 1)
        f.seek(2, 0)
        return f

    def log(self, request):
        """Log a request's result to the logfile, by default in combined log format."""
        line = '%s - - %s "%s" %d %s "%s" "%s"\n' % (
            "foo", #request.getClientIP(),
            # request.getUser() or "-", # the remote user is almost never important
            time.time(), #_logDateTime,
            '%s %s %s' % (request.method, request.uri, request.clientproto),
            request.code,
            request.sentLength or "-",
            request.in_headers.getHeader("referer") or "-",
            request.in_headers.getHeader("user-agent") or "-")
        self.logFile.write(line)




#     def gotLength(self, length):
#         """Called when HTTP channel got length of content in this request.

#         This method is not intended for users.
#         """
#         if length < 100000:
#             self.content = StringIO()
#         else:
#             self.content = tempfile.TemporaryFile()

#     def handleContentChunk(self, data):
#         """Write a chunk of data.

#         This method is not intended for users.
#         """
#         self.content.write(data)


#         # Argument processing
#         args = self.args
#         ctype = self.getHeader('content-type')
#         if self.method == "POST" and ctype:
#             mfd = 'multipart/form-data'
#             key, pdict = cgi.parse_header(ctype)
#             if key == 'application/x-www-form-urlencoded':
#                 args.update(
#                     parse_qs(self.content.read(), 1))
#             elif key == mfd:
#                 args.update(
#                     cgi.parse_multipart(self.content, pdict))
#             else:
#                 pass


#     def handleContentComplete(self):
#         """Called by channel when all data has been received.

#         This method is not intended for users.
#         """
#         self.args = {}
#         self.stack = []

#         x = self.uri.split('?')

#         if len(x) == 1:
#             self.path = self.uri
#         else:
#             if len(x) != 2:
#                 log.msg("May ignore parts of this invalid URI: %s"
#                         % repr(self.uri))
#             self.path, argstring = x[0], x[1]
#             self.args = parse_qs(argstring, 1)

#         # cache the client and server information, we'll need this later to be
#         # serialized and sent with the request so CGIs will work remotely
#         self.client = self.channel.transport.getPeer()
#         self.host = self.channel.transport.getHost()
