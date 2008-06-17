import warnings
import socket
from cStringIO import StringIO
from zope.interface import implements

from twisted.python import log
from twisted.internet import interfaces, protocol, reactor
from twisted.protocols import policies, basic
from twisted.web2 import responsecode
from twisted.web2 import http_headers
from twisted.web2 import http

PERSIST_NO_PIPELINE, PERSIST_PIPELINE = (1,2)

_cachedHostNames = {}
def _cachedGetHostByAddr(hostaddr):
    hostname = _cachedHostNames.get(hostaddr)
    if hostname is None:
        try:
            hostname = socket.gethostbyaddr(hostaddr)[0]
        except socket.herror:
            hostname = hostaddr
        _cachedHostNames[hostaddr]=hostname
    return hostname

class StringTransport(object):
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

class AbortedException(Exception):
    pass


class HTTPParser(object):
    """This class handles the parsing side of HTTP processing. With a suitable
    subclass, it can parse either the client side or the server side of the
    connection.
    """
    
    # Class config:
    parseCloseAsEnd = False
    
    # Instance vars
    chunkedIn = False
    headerlen = 0
    length = None
    inHeaders = None
    partialHeader = ''
    connHeaders = None
    finishedReading = False

    channel = None

    # For subclassing...
    # Needs attributes:
    #  version

    # Needs functions:
    #  createRequest()
    #  processRequest()
    #  _abortWithError()
    #  handleContentChunk(data)
    #  handleContentComplete()

    # Needs functions to exist on .channel
    #  channel.maxHeaderLength
    #  channel.requestReadFinished(self)
    #  channel.setReadPersistent(self, persistent)
    # (from LineReceiver):
    #  channel.setRawMode()
    #  channel.setLineMode(extraneous)
    #  channel.pauseProducing()
    #  channel.resumeProducing()
    #  channel.stopProducing()
    
    
    def __init__(self, channel):
        self.inHeaders = http_headers.Headers()
        self.channel = channel
        
    def lineReceived(self, line):
        if self.chunkedIn:
            # Parsing a chunked input
            if self.chunkedIn == 1:
                # First we get a line like "chunk-size [';' chunk-extension]"
                # (where chunk extension is just random crap as far as we're concerned)
                # RFC says to ignore any extensions you don't recognize -- that's all of them.
                chunksize = line.split(';', 1)[0]
                try:
                    self.length = int(chunksize, 16)
                except:
                    self._abortWithError(responsecode.BAD_REQUEST, "Invalid chunk size, not a hex number: %s!" % chunksize)
                if self.length < 0:
                    self._abortWithError(responsecode.BAD_REQUEST, "Invalid chunk size, negative.")

                if self.length == 0:
                    # We're done, parse the trailers line
                    self.chunkedIn = 3
                else:
                    # Read self.length bytes of raw data
                    self.channel.setRawMode()
            elif self.chunkedIn == 2:
                # After we got data bytes of the appropriate length, we end up here,
                # waiting for the CRLF, then go back to get the next chunk size.
                if line != '':
                    self._abortWithError(responsecode.BAD_REQUEST, "Excess %d bytes sent in chunk transfer mode" % len(line))
                self.chunkedIn = 1
            elif self.chunkedIn == 3:
                # TODO: support Trailers (maybe! but maybe not!)
                
                # After getting the final "0" chunk we're here, and we *EAT MERCILESSLY*
                # any trailer headers sent, and wait for the blank line to terminate the
                # request.
                if line == '':
                    self.allContentReceived()
        # END of chunk handling
        elif line == '':
            # Empty line => End of headers
            if self.partialHeader:
                self.headerReceived(self.partialHeader)
            self.partialHeader = ''
            self.allHeadersReceived()    # can set chunkedIn
            self.createRequest()
            if self.chunkedIn:
                # stay in linemode waiting for chunk header
                pass
            elif self.length == 0:
                # no content expected
                self.allContentReceived()
            else:
                # await raw data as content
                self.channel.setRawMode()
                # Should I do self.pauseProducing() here?
            self.processRequest()
        else:
            self.headerlen += len(line)
            if self.headerlen > self.channel.maxHeaderLength:
                self._abortWithError(responsecode.BAD_REQUEST, 'Headers too long.')
            
            if line[0] in ' \t':
                # Append a header continuation
                self.partialHeader += line
            else:
                if self.partialHeader:
                    self.headerReceived(self.partialHeader)
                self.partialHeader = line

    def rawDataReceived(self, data):
        """Handle incoming content."""
        datalen = len(data)
        if datalen < self.length:
            self.handleContentChunk(data)
            self.length = self.length - datalen
        else:
            self.handleContentChunk(data[:self.length])
            extraneous = data[self.length:]
            channel = self.channel # could go away from allContentReceived.
            if not self.chunkedIn:
                self.allContentReceived()
            else:
                # NOTE: in chunked mode, self.length is the size of the current chunk,
                # so we still have more to read.
                self.chunkedIn = 2 # Read next chunksize
            
            channel.setLineMode(extraneous)

    def headerReceived(self, line):
        """Store this header away. Check for too much header data
           (> channel.maxHeaderLength) and abort the connection if so.
        """
        nameval = line.split(':', 1)
        if len(nameval) != 2:
            self._abortWithError(responsecode.BAD_REQUEST, "No ':' in header.")
        
        name, val = nameval
        val = val.lstrip(' \t')
        self.inHeaders.addRawHeader(name, val)
        

    def allHeadersReceived(self):
        # Split off connection-related headers
        connHeaders = self.splitConnectionHeaders()

        # Set connection parameters from headers
        self.setConnectionParams(connHeaders)
        self.connHeaders = connHeaders
        
    def allContentReceived(self):
        self.finishedReading = True
        self.channel.requestReadFinished(self)
        self.handleContentComplete()
        
        
    def splitConnectionHeaders(self):
        """
        Split off connection control headers from normal headers.

        The normal headers are then passed on to user-level code, while the
        connection headers are stashed in .connHeaders and used for things like
        request/response framing.

        This corresponds roughly with the HTTP RFC's description of 'hop-by-hop'
        vs 'end-to-end' headers in RFC2616 S13.5.1, with the following
        exceptions:

         - proxy-authenticate and proxy-authorization are not treated as
           connection headers.

         - content-length is, as it is intimately related with low-level HTTP
           parsing, and is made available to user-level code via the stream
           length, rather than a header value. (except for HEAD responses, in
           which case it is NOT used by low-level HTTP parsing, and IS kept in
           the normal headers.
        """

        def move(name):
            h = inHeaders.getRawHeaders(name, None)
            if h is not None:
                inHeaders.removeHeader(name)
                connHeaders.setRawHeaders(name, h)

        # NOTE: According to HTTP spec, we're supposed to eat the
        # 'Proxy-Authenticate' and 'Proxy-Authorization' headers also, but that
        # doesn't sound like a good idea to me, because it makes it impossible
        # to have a non-authenticating transparent proxy in front of an
        # authenticating proxy. An authenticating proxy can eat them itself.
        #
        # 'Proxy-Connection' is an undocumented HTTP 1.0 abomination.
        connHeaderNames = ['content-length', 'connection', 'keep-alive', 'te',
                           'trailers', 'transfer-encoding', 'upgrade',
                           'proxy-connection']
        inHeaders = self.inHeaders
        connHeaders = http_headers.Headers()

        move('connection')
        if self.version < (1,1):
            # Remove all headers mentioned in Connection, because a HTTP 1.0
            # proxy might have erroneously forwarded it from a 1.1 client.
            for name in connHeaders.getHeader('connection', ()):
                if inHeaders.hasHeader(name):
                    inHeaders.removeHeader(name)
        else:
            # Otherwise, just add the headers listed to the list of those to move
            connHeaderNames.extend(connHeaders.getHeader('connection', ()))

        # If the request was HEAD, self.length has been set to 0 by
        # HTTPClientRequest.submit; in this case, Content-Length should
        # be treated as a response header, not a connection header.

        # Note: this assumes the invariant that .length will always be None
        # coming into this function, unless this is a HEAD request.
        if self.length is not None:
            connHeaderNames.remove('content-length')

        for headername in connHeaderNames:
            move(headername)

        return connHeaders

    def setConnectionParams(self, connHeaders):
        # Figure out persistent connection stuff
        if self.version >= (1,1):
            if 'close' in connHeaders.getHeader('connection', ()):
                readPersistent = False
            else:
                readPersistent = PERSIST_PIPELINE
        elif 'keep-alive' in connHeaders.getHeader('connection', ()):
            readPersistent = PERSIST_NO_PIPELINE
        else:
            readPersistent = False


        # Okay, now implement section 4.4 Message Length to determine
        # how to find the end of the incoming HTTP message.
        transferEncoding = connHeaders.getHeader('transfer-encoding')
        
        if transferEncoding:
            if transferEncoding[-1] == 'chunked':
                # Chunked
                self.chunkedIn = 1
                # Cut off the chunked encoding (cause it's special)
                transferEncoding = transferEncoding[:-1]
            elif not self.parseCloseAsEnd:
                # Would close on end of connection, except this can't happen for
                # client->server data. (Well..it could actually, since TCP has half-close
                # but the HTTP spec says it can't, so we'll pretend it's right.)
                self._abortWithError(responsecode.BAD_REQUEST, "Transfer-Encoding received without chunked in last position.")
            
            # TODO: support gzip/etc encodings.
            # FOR NOW: report an error if the client uses any encodings.
            # They shouldn't, because we didn't send a TE: header saying it's okay.
            if transferEncoding:
                self._abortWithError(responsecode.NOT_IMPLEMENTED, "Transfer-Encoding %s not supported." % transferEncoding)
        else:
            # No transfer-coding.
            self.chunkedIn = 0
            if self.parseCloseAsEnd:
                # If no Content-Length, then it's indeterminate length data
                # (unless the responsecode was one of the special no body ones)
                # Also note that for HEAD requests, connHeaders won't have
                # content-length even if the response did.
                if self.code in http.NO_BODY_CODES:
                    self.length = 0
                else:
                    self.length = connHeaders.getHeader('content-length', self.length)

                # If it's an indeterminate stream without transfer encoding, it must be
                # the last request.
                if self.length is None:
                    readPersistent = False
            else:
                # If no Content-Length either, assume no content.
                self.length = connHeaders.getHeader('content-length', 0)

        # Set the calculated persistence
        self.channel.setReadPersistent(readPersistent)
        
    def abortParse(self):
        # If we're erroring out while still reading the request
        if not self.finishedReading:
            self.finishedReading = True
            self.channel.setReadPersistent(False)
            self.channel.requestReadFinished(self)
        
    # producer interface
    def pauseProducing(self):
        if not self.finishedReading:
            self.channel.pauseProducing()
        
    def resumeProducing(self):
        if not self.finishedReading:
            self.channel.resumeProducing()
       
    def stopProducing(self):
        if not self.finishedReading:
            self.channel.stopProducing()

class HTTPChannelRequest(HTTPParser):
    """This class handles the state and parsing for one HTTP request.
    It is responsible for all the low-level connection oriented behavior.
    Thus, it takes care of keep-alive, de-chunking, etc., and passes
    the non-connection headers on to the user-level Request object."""
    
    command = path = version = None
    queued = 0
    request = None
    
    out_version = "HTTP/1.1"
    
    def __init__(self, channel, queued=0):
        HTTPParser.__init__(self, channel)
        self.queued=queued

        # Buffer writes to a string until we're first in line
        # to write a response
        if queued:
            self.transport = StringTransport()
        else:
            self.transport = self.channel.transport
        
        # set the version to a fallback for error generation
        self.version = (1,0)


    def gotInitialLine(self, initialLine):
        parts = initialLine.split()
        
        # Parse the initial request line
        if len(parts) != 3:
            if len(parts) == 1:
                parts.append('/')
            if len(parts) == 2 and parts[1][0] == '/':
                parts.append('HTTP/0.9')
            else:
                self._abortWithError(responsecode.BAD_REQUEST, 'Bad request line: %s' % initialLine)

        self.command, self.path, strversion = parts
        try:
            protovers = http.parseVersion(strversion)
            if protovers[0] != 'http':
                raise ValueError()
        except ValueError:
            self._abortWithError(responsecode.BAD_REQUEST, "Unknown protocol: %s" % strversion)
        
        self.version = protovers[1:3]
        
        # Ensure HTTP 0 or HTTP 1.
        if self.version[0] > 1:
            self._abortWithError(responsecode.HTTP_VERSION_NOT_SUPPORTED, 'Only HTTP 0.9 and HTTP 1.x are supported.')

        if self.version[0] == 0:
            # simulate end of headers, as HTTP 0 doesn't have headers.
            self.lineReceived('')

    def lineLengthExceeded(self, line, wasFirst=False):
        code = wasFirst and responsecode.REQUEST_URI_TOO_LONG or responsecode.BAD_REQUEST
        self._abortWithError(code, 'Header line too long.')

    def createRequest(self):
        self.request = self.channel.requestFactory(self, self.command, self.path, self.version, self.length, self.inHeaders)
        del self.inHeaders

    def processRequest(self):
        self.request.process()
        
    def handleContentChunk(self, data):
        self.request.handleContentChunk(data)
        
    def handleContentComplete(self):
        self.request.handleContentComplete()
        
############## HTTPChannelRequest *RESPONSE* methods #############
    producer = None
    chunkedOut = False
    finished = False
    
    ##### Request Callbacks #####
    def writeIntermediateResponse(self, code, headers=None):
        if self.version >= (1,1):
            self._writeHeaders(code, headers, False)

    def writeHeaders(self, code, headers):
        self._writeHeaders(code, headers, True)
        
    def _writeHeaders(self, code, headers, addConnectionHeaders):
        # HTTP 0.9 doesn't have headers.
        if self.version[0] == 0:
            return
        
        l = []
        code_message = responsecode.RESPONSES.get(code, "Unknown Status")
        
        l.append('%s %s %s\r\n' % (self.out_version, code,
                                   code_message))
        if headers is not None:
            for name, valuelist in headers.getAllRawHeaders():
                for value in valuelist:
                    l.append("%s: %s\r\n" % (name, value))

        if addConnectionHeaders:
            # if we don't have a content length, we send data in
            # chunked mode, so that we can support persistent connections.
            if (headers.getHeader('content-length') is None and
                self.command != "HEAD" and code not in http.NO_BODY_CODES):
                if self.version >= (1,1):
                    l.append("%s: %s\r\n" % ('Transfer-Encoding', 'chunked'))
                    self.chunkedOut = True
                else:
                    # Cannot use persistent connections if we can't do chunking
                    self.channel.dropQueuedRequests()
            
            if self.channel.isLastRequest(self):
                l.append("%s: %s\r\n" % ('Connection', 'close'))
            elif self.version < (1,1):
                l.append("%s: %s\r\n" % ('Connection', 'Keep-Alive'))
        
        l.append("\r\n")
        self.transport.writeSequence(l)
        
    
    def write(self, data):
        if not data:
            return
        elif self.chunkedOut:
            self.transport.writeSequence(("%X\r\n" % len(data), data, "\r\n"))
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
        
        self.finished = True
        if not self.queued:
            self._cleanup()


    def abortConnection(self, closeWrite=True):
        """Abort the HTTP connection because of some kind of unrecoverable
        error. If closeWrite=False, then only abort reading, but leave
        the writing side alone. This is mostly for internal use by
        the HTTP request parsing logic, so that it can call an error
        page generator.
        
        Otherwise, completely shut down the connection.
        """
        self.abortParse()
        if closeWrite:
            if self.producer:
                self.producer.stopProducing()
                self.unregisterProducer()
            
            self.finished = True
            if self.queued:
                self.transport.reset()
                self.transport.truncate()
            else:
                self._cleanup()

    def getHostInfo(self):
        t=self.channel.transport
        secure = interfaces.ISSLTransport(t, None) is not None
        host = t.getHost()
        host.host = _cachedGetHostByAddr(host.host)
        return host, secure

    def getRemoteHost(self):
        return self.channel.transport.getPeer()
    
    ##### End Request Callbacks #####

    def _abortWithError(self, errorcode, text=''):
        """Handle low level protocol errors."""
        headers = http_headers.Headers()
        headers.setHeader('content-length', len(text)+1)
        
        self.abortConnection(closeWrite=False)
        self.writeHeaders(errorcode, headers)
        self.write(text)
        self.write("\n")
        self.finish()
        raise AbortedException
    
    def _cleanup(self):
        """Called when have finished responding and are no longer queued."""
        if self.producer:
            log.err(RuntimeError("Producer was not unregistered for %s" % self))
            self.unregisterProducer()
        self.channel.requestWriteFinished(self)
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
        if self.queued and self.producer:
            self.producer.stopProducing()
            self.producer = None
        if self.request:
            self.request.connectionLost(reason)
    
class HTTPChannel(basic.LineReceiver, policies.TimeoutMixin, object):
    """A receiver for HTTP requests. Handles splitting up the connection
    for the multiple HTTPChannelRequests that may be in progress on this
    channel.

    @ivar timeOut: number of seconds to wait before terminating an
    idle connection.

    @ivar maxPipeline: number of outstanding in-progress requests
    to allow before pausing the input.

    @ivar maxHeaderLength: number of bytes of header to accept from
    the client.

    """
    
    implements(interfaces.IHalfCloseableProtocol)
    
    ## Configuration parameters. Set in instances or subclasses.
    
    # How many simultaneous requests to handle.
    maxPipeline = 4

    # Timeout when between two requests
    betweenRequestsTimeOut = 15
    # Timeout between lines or bytes while reading a request
    inputTimeOut = 60 * 4

    # maximum length of headers (10KiB)
    maxHeaderLength = 10240

    # Allow persistent connections?
    allowPersistentConnections = True
    
    # ChannelRequest
    chanRequestFactory = HTTPChannelRequest
    requestFactory = http.Request
    
    
    _first_line = 2
    readPersistent = PERSIST_PIPELINE
    
    _readLost = False
    _writeLost = False
    
    _lingerTimer = None
    chanRequest = None

    def _callLater(self, secs, fun):
        reactor.callLater(secs, fun)
    
    def __init__(self):
        # the request queue
        self.requests = []
        
    def connectionMade(self):
        self.setTimeout(self.inputTimeOut)
        self.factory.outstandingRequests+=1
    
    def lineReceived(self, line):
        if self._first_line:
            self.setTimeout(self.inputTimeOut)
            # if this connection is not persistent, drop any data which
            # the client (illegally) sent after the last request.
            if not self.readPersistent:
                self.dataReceived = self.lineReceived = lambda *args: None
                return

            # IE sends an extraneous empty line (\r\n) after a POST request;
            # eat up such a line, but only ONCE
            if not line and self._first_line == 1:
                self._first_line = 2
                return
            
            self._first_line = 0
            
            if not self.allowPersistentConnections:
                # Don't allow a second request
                self.readPersistent = False
                
            try:
                self.chanRequest = self.chanRequestFactory(self, len(self.requests))
                self.requests.append(self.chanRequest)
                self.chanRequest.gotInitialLine(line)
            except AbortedException:
                pass
        else:
            try:
                self.chanRequest.lineReceived(line)
            except AbortedException:
                pass

    def lineLengthExceeded(self, line):
        if self._first_line:
            # Fabricate a request object to respond to the line length violation.
            self.chanRequest = self.chanRequestFactory(self, 
                                                       len(self.requests))
            self.requests.append(self.chanRequest)
            self.chanRequest.gotInitialLine("GET fake HTTP/1.0")
        try:
            self.chanRequest.lineLengthExceeded(line, self._first_line)
        except AbortedException:
            pass
            
    def rawDataReceived(self, data):
        self.setTimeout(self.inputTimeOut)
        try:
            self.chanRequest.rawDataReceived(data)
        except AbortedException:
            pass

    def requestReadFinished(self, request):
        if(self.readPersistent is PERSIST_NO_PIPELINE or
           len(self.requests) >= self.maxPipeline):
            self.pauseProducing()
        
        # reset state variables
        self._first_line = 1
        self.chanRequest = None
        self.setLineMode()
        
        # Disable the idle timeout, in case this request takes a long
        # time to finish generating output.
        if len(self.requests) > 0:
            self.setTimeout(None)
        
    def _startNextRequest(self):
        # notify next request, if present, it can start writing
        del self.requests[0]

        if self._writeLost:
            self.transport.loseConnection()
        elif self.requests:
            self.requests[0].noLongerQueued()
            
            # resume reading if allowed to
            if(not self._readLost and
               self.readPersistent is not PERSIST_NO_PIPELINE and
               len(self.requests) < self.maxPipeline):
                self.resumeProducing()
        elif self._readLost:
            # No more incoming data, they already closed!
            self.transport.loseConnection()
        else:
            # no requests in queue, resume reading
            self.setTimeout(self.betweenRequestsTimeOut)
            self.resumeProducing()

    def setReadPersistent(self, persistent):
        if self.readPersistent:
            # only allow it to be set if it's not currently False
            self.readPersistent = persistent

    def dropQueuedRequests(self):
        """Called when a response is written that forces a connection close."""
        self.readPersistent = False
        # Tell all requests but first to abort.
        for request in self.requests[1:]:
            request.connectionLost(None)
        del self.requests[1:]
    
    def isLastRequest(self, request):
        # Is this channel handling the last possible request
        return not self.readPersistent and self.requests[-1] == request
    
    def requestWriteFinished(self, request):
        """Called by first request in queue when it is done."""
        if request != self.requests[0]: raise TypeError

        # Don't del because we haven't finished cleanup, so,
        # don't want queue len to be 0 yet.
        self.requests[0] = None
        
        if self.readPersistent or len(self.requests) > 1:
            # Do this in the next reactor loop so as to
            # not cause huge call stacks with fast
            # incoming requests.
            self._callLater(0, self._startNextRequest)
        else:
            self.lingeringClose()

    def timeoutConnection(self):
        #log.msg("Timing out client: %s" % str(self.transport.getPeer()))
        policies.TimeoutMixin.timeoutConnection(self)

    def lingeringClose(self):
        """
        This is a bit complicated. This process is necessary to ensure proper
        workingness when HTTP pipelining is in use.

        Here is what it wants to do:

            1.  Finish writing any buffered data, then close our write side.
                While doing so, read and discard any incoming data.

            2.  When that happens (writeConnectionLost called), wait up to 20
                seconds for the remote end to close their write side (our read
                side).

            3.
                - If they do (readConnectionLost called), close the socket,
                  and cancel the timeout.

                - If that doesn't happen, the timer fires, and makes the
                  socket close anyways.
        """
        
        # Close write half
        self.transport.loseWriteConnection()
        
        # Throw out any incoming data
        self.dataReceived = self.lineReceived = lambda *args: None
        self.transport.resumeProducing()

    def writeConnectionLost(self):
        # Okay, all data has been written
        # In 20 seconds, actually close the socket
        self._lingerTimer = reactor.callLater(20, self._lingerClose)
        self._writeLost = True
        
    def _lingerClose(self):
        self._lingerTimer = None
        self.transport.loseConnection()
        
    def readConnectionLost(self):
        """Read connection lost"""
        # If in the lingering-close state, lose the socket.
        if self._lingerTimer:
            self._lingerTimer.cancel()
            self._lingerTimer = None
            self.transport.loseConnection()
            return
        
        # If between requests, drop connection
        # when all current requests have written their data.
        self._readLost = True
        if not self.requests:
            # No requests in progress, lose now.
            self.transport.loseConnection()
            
        # If currently in the process of reading a request, this is
        # probably a client abort, so lose the connection.
        if self.chanRequest:
            self.transport.loseConnection()
        
    def connectionLost(self, reason):
        self.factory.outstandingRequests-=1

        self._writeLost = True
        self.readConnectionLost()
        self.setTimeout(None)
        
        # Tell all requests to abort.
        for request in self.requests:
            if request is not None:
                request.connectionLost(reason)

class OverloadedServerProtocol(protocol.Protocol):
    def connectionMade(self):
        self.transport.write("HTTP/1.0 503 Service Unavailable\r\n"
                             "Content-Type: text/html\r\n"
                             "Connection: close\r\n\r\n"
                             "<html><head><title>503 Service Unavailable</title></head>"
                             "<body><h1>Service Unavailable</h1>"
                             "The server is currently overloaded, "
                             "please try again later.</body></html>")
        self.transport.loseConnection()

class HTTPFactory(protocol.ServerFactory):
    """Factory for HTTP server."""

    protocol = HTTPChannel
    
    protocolArgs = None

    outstandingRequests = 0
    
    def __init__(self, requestFactory, maxRequests=600, **kwargs):
        self.maxRequests=maxRequests
        self.protocolArgs = kwargs
        self.protocolArgs['requestFactory']=requestFactory
        
    def buildProtocol(self, addr):
        if self.outstandingRequests >= self.maxRequests:
            return OverloadedServerProtocol()
        
        p = protocol.ServerFactory.buildProtocol(self, addr)
        
        for arg,value in self.protocolArgs.iteritems():
            setattr(p, arg, value)
        return p

__all__ = ['HTTPFactory', ]
