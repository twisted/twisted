# -*- test-case-name: twisted.web.test.test_http -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""HyperText Transfer Protocol implementation.

The second coming.

Maintainer: U{James Y Knight <mailto:foom@fuhm.net>}

"""
#        import traceback; log.msg(''.join(traceback.format_stack()))

# system imports
from cStringIO import StringIO
import base64, binascii
import socket
import math
import time
import calendar
import warnings
import os

# twisted imports
from twisted.internet import interfaces, protocol, address, reactor
from twisted.protocols import policies, basic
from twisted.python import log, components, util
from zope.interface import implements

# sibling imports
from twisted.web2 import responsecode
from twisted.web2 import http_headers
from twisted.web2 import iweb
from twisted.web2 import stream

PERSIST_NO_PIPELINE = 2


def toChunk(data):
    """Convert string to a chunk.
    
    @returns: a tuple of strings representing the chunked encoding of data"""
    return ("%X\r\n" % len(data), data, "\r\n")
    

def parseVersion(strversion):
    """Parse version strings of the form Protocol '/' Major '.' Minor. E.g. 'HTTP/1.1'.
    Returns (protocol, major, minor).
    Will raise ValueError on bad syntax."""

    proto, strversion = strversion.split('/')
    major, minor = strversion.split('.')
    major, minor = int(major), int(minor)
    if major < 0 or minor < 0:
        raise ValueError("negative number")
    return (proto.lower(), major, minor)

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

class HTTPError(Exception):
    def __init__(self, codeOrResponse):
        Exception.__init__(self)
        self.response = iweb.IResponse(codeOrResponse)
        
class Response(object):
    implements(iweb.IResponse)
    
    code = responsecode.OK
    headers = None
    stream = None
    
    def __init__(self, code=None, headers=None, stream=None):
        if code is not None:
            self.code=code
        if headers is not None:
            self.headers=headers
        else:
            self.headers = http_headers.Headers()
        self.stream = stream
        
def NotModifiedResponse(oldResponse=None):
    if oldResponse is not None:
        headers=http_headers.Headers()
        for header in (
            # Required from sec 10.3.5:
            'date', 'etag', 'content-location', 'expires',
            'cache-control', 'vary',
            # Others:
            'server', 'proxy-authenticate', 'www-authenticate', 'warning'):
            value = oldResponse.headers.getRawHeaders(header)
            if value is not None:
                headers.setRawHeaders(header, value)
    else:
        headers = None
    return Response(code=responsecode.NOT_MODIFIED, headers=headers)
    

def checkPreconditions(request, response, entityExists=True):
    """Check to see if this request passes the conditional checks specified
    by the client. As a side-effect, may modify my response code to
    L{NOT_MODIFIED} or L{PRECONDITION_FAILED}.

    Call this function after setting the ETag and Last-Modified
    output headers, but before actually proceeding with request
    processing.

    This examines the appropriate request headers for conditionals,
    (If-Modified-Since, If-Unmodified-Since, If-Match, If-None-Match,
    or If-Range), compares with the existing response headers and
    and then sets the response code as necessary.

    @param entityExists: Set to False if the entity in question doesn't
             yet exist. Necessary for PUT support with 'If-None-Match: *'.
    @raise: HTTPError: Raised when the preconditions fail, in order to
             abort processing and emit an error page.

    """
    # if the code is some sort of error code, don't do anything
    if not ((response.code >= 200 and response.code <= 299)
            or response.code == responsecode.PRECONDITION_FAILED):
        return False

    etag = response.headers.getHeader("etag")
    lastModified = response.headers.getHeader("last-modified")

    def matchETag(tags, allowWeak):
        if entityExists and '*' in tags:
            return True
        if etag is None:
            return False
        return ((allowWeak or not etag.weak) and
                ([etagmatch for etagmatch in tags if etag.match(etagmatch, strongCompare=not allowWeak)]))

    # First check if-match/if-unmodified-since
    # If either one fails, we return PRECONDITION_FAILED
    match = request.headers.getHeader("if-match")
    if match:
        if not matchETag(match, False):
            raise HTTPError(responsecode.PRECONDITION_FAILED)

    unmod_since = request.headers.getHeader("if-unmodified-since")
    if unmod_since:
        if not lastModified or lastModified > unmod_since:
            raise HTTPError(responsecode.PRECONDITION_FAILED)

    # Now check if-none-match/if-modified-since.
    # This bit is tricky, because of the requirements when both IMS and INM
    # are present. In that case, you can't return a failure code
    # unless *both* checks think it failed.
    # Also, if the INM check succeeds, ignore IMS, because INM is treated
    # as more reliable.

    # I hope I got the logic right here...the RFC is quite poorly written
    # in this area. Someone might want to verify the testcase against
    # RFC wording.

    # If IMS header is later than current time, ignore it.
    notModified = None
    ims = request.headers.getHeader('if-modified-since')
    if ims:
        notModified = (ims < time.time() and lastModified and lastModified <= ims)


    inm = request.headers.getHeader("if-none-match")
    if inm:
        if request.method in ("HEAD", "GET"):
            # If it's a range request, don't allow a weak ETag, as that
            # would break. 
            canBeWeak = not request.headers.hasHeader('Range')
            if notModified != False and matchETag(inm, canBeWeak):
                raise HTTPError(NotModifiedResponse(response))
        else:
            if notModified != False and matchETag(inm, False):
                raise HTTPError(responsecode.PRECONDITION_FAILED)
    else:
        if notModified == True:
            raise HTTPError(NotModifiedResponse(response))

def checkIfRange(request, response):
    """Checks for the If-Range header, and if it exists, checks if the
    test passes. Returns true if the server should return partial data."""

    ifrange = request.headers.getHeader("if-range")

    if ifrange is None:
        return True
    if isinstance(ifrange, http_headers.ETag):
        return ifrange.match(response.headers.getHeader("etag"), strongCompare=True)
    else:
        return ifrange == response.headers.getHeader("last-modified")

class _NotifyingProducerStream(stream.ProducerStream):
    doStartReading = None

    def __init__(self, length=None, doStartReading=None):
        stream.ProducerStream.__init__(self, length=length)
        self.doStartReading = doStartReading
    
    def read(self):
        if self.doStartReading is not None:
            doStartReading = self.doStartReading
            self.doStartReading = None
            doStartReading()
            
        return stream.ProducerStream.read(self)

    def write(self, data):
        self.doStartReading = None
        stream.ProducerStream.write(self, data)

    def finish(self):
        self.doStartReading = None
        stream.ProducerStream.finish(self)

# response codes that must have empty bodies
NO_BODY_CODES = (responsecode.NO_CONTENT, responsecode.NOT_MODIFIED)

class Request(object):
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

    implements(iweb.IRequest, interfaces.IConsumer)

    known_expects = ('100-continue',)
    
    def __init__(self, chanRequest, command, path, version, headers):
        """
        @param chanRequest: the channel request we're associated with.
        """
        self.chanRequest = chanRequest
        self.method = command
        self.uri = path
        self.clientproto = version
        
        self.headers = headers
        
        if '100-continue' in self.headers.getHeader('Expect', ()):
            doStartReading = self._sendContinue
        else:
            doStartReading = None
        self.stream = _NotifyingProducerStream(headers.getHeader('content-length', None), doStartReading)
        self.stream.registerProducer(self.chanRequest, True)
        
    def checkExpect(self):
        """Ensure there are no expectations that cannot be met.
        Checks Expect header against self.known_expects."""
        expects = self.headers.getHeader('Expect', ())
        for expect in expects:
            if expect not in self.known_expects:
                raise HTTPError(responsecode.EXPECTATION_FAILED)
    
    def process(self):
        """called by __init__ to let you process the request.
        
        Can be overridden by a subclass to do something useful."""
        pass
    
    def handleContentChunk(self, data):
        """Callback from channel when a piece of data has been received.
        Puts the data in .stream"""
        self.stream.write(data)
    
    def handleContentComplete(self):
        """Callback from channel when all data has been received. """
        self.stream.unregisterProducer()
        self.stream.finish()
        
    def connectionLost(self, reason):
        """connection was lost"""
        pass

    def __repr__(self):
        return '<%s %s %s>'% (self.method, self.uri, self.clientproto)

    def _sendContinue(self):
        self.chanRequest.writeIntermediateResponse(responsecode.CONTINUE)
            
    def _finished(self, x):
        """We are finished writing data."""
        # log request
        log.msg(type=iweb.IRequest, object=self)
        self.chanRequest.finish()

    def _error(self, reason):
        log.err(reason)
        self.chanRequest.abortConnection()
        
    def writeResponse(self, response):
        """
        Write a response.
        """
        if self.stream.doStartReading is not None:
            # Expect: 100-continue was requested, but 100 response has not been
            # sent, and there's a possibility that data is still waiting to be
            # sent.
            # 
            # Ideally this means the remote side will not send any data.
            # However, because of compatibility requirements, it might timeout,
            # and decide to do so anyways at the same time we're sending back 
            # this response. Thus, the read state is unknown after this.
            # We must close the connection.
            self.chanRequest.persistent = False
            # Nothing more will be read
            self.chanRequest.allContentReceived()

        if response.code != responsecode.NOT_MODIFIED:
            # Not modified response is *special* and doesn't get a content-length.
            if response.stream is None:
                response.headers.setHeader('content-length', 0)
            elif response.stream.length is not None:
                response.headers.setHeader('content-length', response.stream.length)
        self.chanRequest.writeHeaders(response.code, response.headers)
        
        # if this is a "HEAD" request, we shouldn't return any data
        if self.method == "HEAD":
            return
        
        # for certain result codes, we should never return any data
        if response.code in NO_BODY_CODES:
            return

        d = stream.StreamProducer(response.stream).beginProducing(self.chanRequest)
        d.addCallback(self._finished).addErrback(self._error)

class AbortedException(Exception):
    pass

class HTTPChannelRequest:
    """This class handles the state and parsing for one HTTP request.
    It is responsible for all the low-level connection oriented behavior.
    Thus, it takes care of keep-alive, de-chunking, etc., and passes
    the non-connection headers on to the user-level Request object."""
    
    headerlen = 0
    length = None
    chunkedIn = False
    reqHeaders = None
    command = path = version = None
    partialHeader = ''
    queued = 0
    finishedReading = False
    
    channel = None
    request = None
    
    out_version = "HTTP/1.1"
    
    def __init__(self, channel, initialLine, queued=0):
        self.reqHeaders = http_headers.Headers()
        self.channel = channel
        self.queued=queued

        # Buffer writes to a string until we're first in line
        # to write a response
        if queued:
            self.transport = StringTransport()
        else:
            self.transport = self.channel.transport


        parts = initialLine.split()
        # set the version to a fallback for error generation
        self.version = (1,0)

        # Parse the initial request line
        if len(parts) != 3:
            if len(parts) == 1:
                parts.append('/')
            if len(parts) == 2:
                parts.append('HTTP/0.9')
            else:
                self._abortWithError(responsecode.BAD_REQUEST, 'Bad request line: %s' % initialLine)

        self.command, self.path, strversion = parts
        try:
            protovers = parseVersion(strversion)
        except ValueError:
            self._abortWithError(responsecode.BAD_REQUEST, "Unknown protocol: %s" % strversion)
        
        if protovers[0] != 'http':
            self._abortWithError(responsecode.BAD_REQUEST, "Unknown protocol: %s" % strversion)
        
        self.version = protovers[1:3]
        
        # Ensure HTTP 0 or HTTP 1.
        if self.version[0] > 1:
            self._abortWithError(responsecode.HTTP_VERSION_NOT_SUPPORTED, 'Only HTTP 0.9 and HTTP 1.x are supported.')

        if self.version[0] == 0:
            # simulate end of headers, as HTTP 0 doesn't have headers.
            self.lineReceived('')

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
            self.request.process()

        elif line[0] in ' \t':
            # Append a header continuation
            self.partialHeader = self.partialHeader+line
        else:
            if self.partialHeader:
                self.headerReceived(self.partialHeader)
            self.partialHeader = line

    def rawDataReceived(self, data):
        """Handle incoming content."""
        datalen = len(data)
        if datalen < self.length:
            if not self.finished:
                self.request.handleContentChunk(data)
            self.length = self.length - datalen
        else:
            if not self.finished:
                self.request.handleContentChunk(data[:self.length])
            extraneous = data[self.length:]
            channel = self.channel # could go away from allContentReceived.
            if not self.chunkedIn:
                self.allContentReceived()
            else:
                # NOTE: in chunked mode, self.length is the size of the current chunk,
                # so we still have more to read.
                self.chunkedIn = 2 # Read next chunksize
            
            channel.setLineMode(extraneous)

    def lineLengthExceeded(self, line, wasFirst=False):
        code = wasFirst and responsecode.REQUEST_URI_TOO_LONG or responsecode.BAD_REQUEST
        self._abortWithError(code, 'Header line too long.')
        
    def headerReceived(self, line):
        """Store this header away. Check for too much header data
           (> channel.maxHeaderLength) and abort the connection if so.
        """
        nameval = line.split(':', 1)
        if len(nameval) != 2:
            self._abortWithError(responsecode.BAD_REQUEST, "No ':' in header.")
        
        name, val = nameval
        val = val.lstrip(' \t')
        self.reqHeaders._addHeader(name, val)
        
        self.headerlen = self.headerlen+ len(line)
        
        if self.headerlen > self.channel.maxHeaderLength:
            self._abortWithError(responsecode.BAD_REQUEST, 'Headers too long.')
            
    def allHeadersReceived(self):
        # Split off connection-related headers
        connHeaders = self.splitConnectionHeaders()

        # Set connection parameters from headers
        self.setConnectionParams(connHeaders)

        self.channel.queueRequest(self)
        request = self.channel.requestFactory(self, self.command, self.path, self.version, self.reqHeaders)
        
        # Reset header state variables
        del self.reqHeaders
        
        self.connHeaders = connHeaders
        self.request = request
        
    def allContentReceived(self):
        self.finishedReading = True
        self.channel.requestReadFinished(self, self.persistent)
        if not self.finished:
            self.request.handleContentComplete()
        
        
    def splitConnectionHeaders(self):
        # Split off headers for the connection from headers for the request.
        
        def move(name):
            h = reqHeaders.getRawHeaders(name, None)
            if h is not None:
                reqHeaders.removeHeader(name)
                connHeaders.setRawHeaders(name, h)

        # NOTE: According to HTTP spec, we're supposed to eat the
        # 'Proxy-Authenticate' and 'Proxy-Authorization' headers also, but that
        # doesn't sound like a good idea to me, because it makes it impossible
        # to have a non-authenticating transparent proxy in front of an
        # authenticating proxy. An authenticating proxy can eat them itself.
        # 'Proxy-Connection' is an undocumented HTTP 1.0 abomination.
        connHeaderNames = ['Connection', 'Keep-Alive', 'TE', 'Trailers',
                           'Transfer-Encoding', 'Upgrade', 'Proxy-Connection']
        reqHeaders = self.reqHeaders
        connHeaders = http_headers.Headers()
        
        move('Connection')
        if self.version < (1,1):
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
        h = reqHeaders.getRawHeaders('Content-Length', None)
        if h is not None:
            connHeaders.setRawHeaders('Content-Length', h)
        
        return connHeaders

    def setConnectionParams(self, connHeaders):
        # Figure out persistent connection stuff
        if self.version >= (1,1):
            self.persistent = not 'close' in connHeaders.getHeader('connection', ())
        elif 'keep-alive' in connHeaders.getHeader('connection', ()):
            self.persistent = PERSIST_NO_PIPELINE
        else:
            self.persistent = False


        # Okay, now implement section 4.4 Message Length to determine
        # how to find the end of the incoming HTTP message.
        transferEncoding = connHeaders.getHeader('Transfer-Encoding')
        
        if transferEncoding:
            if transferEncoding[-1] == 'chunked':
                # Chunked
                self.chunkedIn = 1
            else:
                # Would close on end of connection, except this can't happen for
                # client->server data. (Well..it could actually, since TCP has half-close
                # but the HTTP spec says it can't, so we'll pretend it's right.)
                self._abortWithError(responsecode.BAD_REQUEST, "Transfer-Encoding received without chunked in last position.")
            
            # Cut off the chunked encoding (cause it's special)
            transferEncoding = transferEncoding[:-1]
            # TODO: support gzip/etc encodings.
            # FOR NOW: report an error if the client uses any encodings.
            # They shouldn't, because we didn't send a TE: header saying it's okay.
            if transferEncoding:
                self._abortWithError(responsecode.NOT_IMPLEMENTED, "Transfer-Encoding %s not supported." % transferEncoding)
        else:
            # No transfer-coding.
            # If no Content-Length either, assume no content.
            self.length = connHeaders.getHeader('Content-Length', 0)
            self.chunkedIn = 0
    
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
            if (headers.getHeader('Content-Length') is None and
                not (code in NO_BODY_CODES)):
                if self.version >= (1,1):
                    l.append("%s: %s\r\n" % ('Transfer-Encoding', 'chunked'))
                    self.chunkedOut = True
                else:
                    # Cannot use persistent connections if we can't do chunking
                    self.persistent = False
            
            if not self.persistent:
                l.append("%s: %s\r\n" % ('Connection', 'close'))
            elif self.version < (1,1):
                l.append("%s: %s\r\n" % ('Connection', 'Keep-Alive'))
        
        l.append("\r\n")
        self.transport.writeSequence(l)
        
    
    def write(self, data):
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
        # If we're erroring out while still reading the request
        if not self.finishedReading:
            self.finishedReading = True
            # and if we haven't even gotten all the headers
            if not self.request:
                self.channel.queueRequest(self)
            self.persistent = False
            self.channel.requestReadFinished(self, self.persistent)
        
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

    ##### End Request Callbacks #####

    def _abortWithError(self, errorcode, text=''):
        """Handle low level protocol errors."""
        headers = http_headers.Headers()
        headers.setHeader('Content-Length', len(text)+1)
        
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
        self.channel.requestWriteFinished(self, self.persistent)
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
        if self.request:
            self.request.connectionLost(reason)

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

    # ChannelRequest
    chanRequestFactory = HTTPChannelRequest
    requestFactory = Request
    
    
    _first_line = 2
    persistent = True
    
    _readLost = False
    
    _lingerTimer = None
    chanRequest = None
    
    def __init__(self):
        # the request queue
        self.requests = []

    def connectionMade(self):
        self.setTimeout(self.inputTimeOut)
    
    def lineReceived(self, line):
        self.setTimeout(self.inputTimeOut)
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
            try:
                self.chanRequest = self.chanRequestFactory(self, line, len(self.requests))
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
            self.chanRequest = self.chanRequestFactory(self, "GET fake HTTP/1.0",
                                                       len(self.requests))
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

    def queueRequest(self, request):
        # create a new Request object
        self.requests.append(request)
        
    def requestReadFinished(self, request, persist):
        self.persistent = persist
        if(self.persistent == PERSIST_NO_PIPELINE or
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
        
        if self.requests:
            self.requests[0].noLongerQueued()
            
            # resume reading if allowed to
            if(self.persistent != PERSIST_NO_PIPELINE and
               len(self.requests) < self.maxPipeline):
                self.resumeProducing()
        elif self._readLost:
            # No more incoming data, they already closed!
            self.transport.loseConnection()
        else:
            # no requests in queue, resume reading
            self.setTimeout(self.betweenRequestsTimeOut)
            self.resumeProducing()

    def requestWriteFinished(self, request, persistent):
        """Called by first request in queue when it is done."""
        if request != self.requests[0]: raise TypeError

        # Don't del because we haven't finished cleanup, so,
        # don't want queue len to be 0 yet.
        self.requests[0] = None
        
        if persistent:
            # Do this in the next reactor loop so as to
            # not cause huge call stacks with fast
            # incoming requests.
            reactor.callLater(0, self._startNextRequest)
        else:
            self.lingeringClose()

    def timeoutConnection(self):
        log.msg("Timing out client: %s" % str(self.transport.getPeer()))
        policies.TimeoutMixin.timeoutConnection(self)

    def lingeringClose(self):
        """This is a bit complicated. This process is necessary to ensure
        proper workingness when HTTP pipelining is in use.
        
        Here is what it wants to do:
        1)  Finish writing any buffered data, then close our write side.
        
            While doing so, read and discard any incoming data.
            (On linux we could call halfCloseConnection(read=True)
            instead, but on other OSes I think that'll also cause the RST
            we're trying to avoid.)
        2)  When that happens (writeConnectionLost called), wait up to 20
            seconds for the remote end to close their write side (our read
            side).
        3a) If they do (readConnectionLost called), close the socket,
            and cancel the timeout.
        3b) If that doesn't happen, the timer fires, and makes the socket
            close anyways.
        """
        
        # Close write half
        self.transport.halfCloseConnection(write=True)
        
        # Throw out any incoming data
        self.dataReceived = self.lineReceived = lambda *args: None
        # (this has to be a callLater because current processing might
        #  cause input to be paused after this returns)
        reactor.callLater(0, self.transport.resumeProducing)

    def writeConnectionLost(self):
        # Okay, all data has been written
        # In 20 seconds, actually close the socket
        self._lingerTimer = reactor.callLater(20, self._lingerClose)

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
        self.readConnectionLost()
        self.setTimeout(None)
        # Tell all requests to abort.
        for request in self.requests:
            if request is not None:
                request.connectionLost(reason)


class HTTPFactory(protocol.ServerFactory):
    """Factory for HTTP server."""

    protocol = HTTPChannel
    
    protocolArgs = None
    
    def __init__(self, **kwargs):
        self.protocolArgs = kwargs

    def buildProtocol(self, addr):
        p = protocol.ServerFactory.buildProtocol(self, addr)

        for arg,value in self.protocolArgs.iteritems():
            setattr(p, arg, value)
        return p
    


# import cgi
# import tempfile
# try: # try importing the fast, C version
#     from twisted.protocols._c_urlarg import unquote
# except ImportError:
#     from urllib import unquote

# def parse_qs(qs, keep_blank_values=0, strict_parsing=0, unquote=unquote):
#     """like cgi.parse_qs, only with custom unquote function"""
#     d = {}
#     items = [s2 for s1 in qs.split("&") for s2 in s1.split(";")]
#     for item in items:
#         try:
#             k, v = item.split("=", 1)
#         except ValueError:
#             if strict_parsing:
#                 raise
#             continue
#         if v or keep_blank_values:
#             k = unquote(k.replace("+", " "))
#             v = unquote(v.replace("+", " "))
#             if k in d:
#                 d[k].append(v)
#             else:
#                 d[k] = [v]
#     return d


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


#     def log(self, request):
#         line = '%s - - %s "%s" %d %s "%s" "%s"\n' % (
#             "foo", #request.getClientIP(),
#             # request.getUser() or "-", # the remote user is almost never important
#             time.time(), #_logDateTime,
#             '%s %s %s' % (request.method, request.uri, request.clientproto),
#             request.code,
#             request.sentLength or "-",
#             request.in_headers.getHeader("referer") or "-",
#             request.in_headers.getHeader("user-agent") or "-")
#         self.logFile.write(line)


#     def _authorize(self):
#         # Authorization, (mostly) per the RFC
#         try:
#             authh = self.in_headers.getHeaderRaw("Authorization")
#             if not authh:
#                 self.user = self.password = ''
#                 return
                
#             bas, upw = authh.split()
#             if bas.lower() != "basic":
#                 raise ValueError
#             upw = base64.decodestring(upw)
#             self.user, self.password = upw.split(':', 1)
#         except (binascii.Error, ValueError):
#             self.user = self.password = ""
#         except:
#             log.err()
#             self.user = self.password = ""
    
#     def getUser(self):
#         try:
#             return self.user
#         except:
#             pass
#         self._authorize()
#         return self.user

#     def getPassword(self):
#         try:
#             return self.password
#         except:
#             pass
#         self._authorize()
#         return self.password

#     def redirect(self, url):
#         """Utility function that does a redirect.

#         The request should have finish() called after this.
#         """
#         self.setResponseCode(FOUND)
#         self.out_headers.setHeader("location", url)
    
#     def setLastModified(self, when):
#         """Set the X{Last-Modified} time for the response to this request.

#         If I am called more than once, I ignore attempts to set
#         Last-Modified earlier, only replacing the Last-Modified time
#         if it is to a later value.

#         @param when: The last time the resource being returned was
#             modified, in seconds since the epoch.
#         @type when: number
#         """
#         # time.time() may be a float, but the HTTP-date strings are
#         # only good for whole seconds.
#         when = long(math.ceil(when))
#         lastModified = self.out_headers.getHeader('Last-Modified')
#         if not lastModified or (lastModified < when):
#             self.out_headers.setHeader('Last-Modified', when)





# # FIXME: these last 3 methods don't belong here.

#     def setHost(self, host, port, ssl=0):
#         """Change the host and port the request thinks it's using.

#         This method is useful for working with reverse HTTP proxies (e.g.
#         both Squid and Apache's mod_proxy can do this), when the address
#         the HTTP client is using is different than the one we're listening on.

#         For example, Apache may be listening on https://www.example.com, and then
#         forwarding requests to http://localhost:8080, but we don't want HTML produced
#         by Twisted to say 'http://localhost:8080', they should say 'https://www.example.com',
#         so we do::

#            request.setHost('www.example.com', 443, ssl=1)

#         This method is experimental.
#         """
#         self._forceSSL = ssl
#         self.in_headers.setHeader("host", host)
#         self.host = address.IPv4Address("TCP", host, port)

#     def getClientIP(self):
#         if isinstance(self.client, address.IPv4Address):
#             return self.client.host
#         else:
#             return None

#     def isSecure(self):
#         return self._forceSSL or components.implements(self.chanRequest.transport, interfaces.ISSLTransport)

