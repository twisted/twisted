# Copyright (c) 2005 Open Source Applications Foundation.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions: 
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software. 
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
from twisted.web2 import http, responsecode, http_headers, stream
from twisted.web2.stream import IByteStream
from twisted.protocols import basic
from twisted.internet import defer, protocol, reactor
from twisted.python.failure import Failure
from twisted.internet.error import TimeoutError

import urllib

def _doLog(entry):
    from twisted.python import log
    log.debug(entry)
            
# class Response(object):
#     """
#     C{Response} objects encapsulate a server response to a single
#     http request.
    
#         @type status: int
#         @ivar status: The HTTP status code returned by the server.
        
#         @type version: str
#         @ivar version: The version the server reported in the status line
        
#         @type message: str
#         @ivar message: The message the server reported in the status line
        
#         @type headers: C{Headers}
#         @ivar headers: The headers sent back from the server

#         @type body: str
#         @ivar body: The content of the HTTP response 
#     """
    
#     def __init__(self, status, version, message, stream=None):
#         self.status = status
#         self.version = version
#         self.message = message
        
#         self.headers = http_headers.Headers()
        
#         self.body = None

#         if stream:
#             self.stream = IByteStream(stream)
#         else:
#             self.stream = None


INITIALIZED      = 0
CONNECTED        = 1
WAITING          = 2
READING_HEADERS  = 3
READING_BODY     = 4
DISCONNECTED     = -1

class Request(object):
    """
    Mostly, a simple class to encapsulate an HTTP request
    
    @type method: str
    @ivar method: The HTTP method (PUT, GET, OPTIONS, etc)
    
    @type path: str
    @ivar path: The path part of the URL we want to fetch.
    
    @type extraHeaders: dict
    @ivar extraHeaders: Additional headers you want sent as part of the
        http request

    @type body: str
    @ivar body: The data associated with this request. This value can be None.
    
    @type deferred: Deferred
    @ivar deferred: The C{Deferred} that will fire when this
                     request is done
    @type state: int
    @ivar state: One of the constants INITIALIZED, CONNECTED, WAITING
          or DISCONNECTED
                     
    @ivar response: The C{Response} to this request. This only
        becomes non-None once the status line comes back from the
        server.

    @ivar timeout: The timeout value, in seconds for this request from
        the time it is enqueued.
    @type timeout: int or float
    """
    timeout = 30
    responseClass = http.Response
    clientproto = "HTTP/1.1"

    _timeoutCall = None
    
    def __init__(self, method, uri, args=None, headers=None, stream=None):

        self.method = method
        self.uri = uri
        self.args = args or {}
        
        if isinstance(headers, http_headers.Headers):
            self.headers = headers
        else:
            self.headers = http_headers.Headers(headers or {})
            
        if stream is not None:
            self.stream = IByteStream(stream)
        else:
            self.stream = None

        self.retries = None

#         if isinstance(self.body, unicode):
#             # @@@ [grant] Need to change charset for text/ types
#             self.body = self.body.encode('utf-8')
        
        self.deferred = defer.Deferred()
        
        # This little trick prevents our deferred from firing
        # twice in the case of, say, a user cancellation or
        # a timeout
        def clearDeferred(self, result):
            self.reset()
            return result

        deferredFn = lambda result: clearDeferred(self, result)
        
        self.deferred.addBoth(deferredFn)
        
    def reset(self):
        self.cancelTimeout()
        self.deferred = None

    def cancelTimeout(self):
        if self._timeoutCall is not None:
            self._timeoutCall.cancel()
            self._timeoutCall = None

    def setTimeout(self, callback, *args, **kwargs):
        """Resests the timeout each time it's called
        """
        self.cancelTimeout()
        self._timeoutCall = reactor.callLater(self.timeout, callback, *args, **kwargs)
            
class RawDecoder(object):

    def start(self, client):
        cl = client.response.headers.getHeader("Content-Length")
        
        if cl is not None:
            try:
                self.length = int(cl)
            except:
                client._protocolError("Invalid Content-Length, not a number: %s!" % cl)
                return
            
            if cl < 0:
                client._protocolError("Invalid Content-Length, cannot be negative: %s!" % cl)
                return
            
        else:
            self.length = None
        
        self.bytesRead = 0
        client.setRawMode()

    def dataReceived(self, client, data):
        datalen = len(data)
        
        if self.length is None or datalen + self.bytesRead < self.length:
            responsePart = data
            extraBytes = None
        else:
            responsePart = data[:self.length - self.bytesRead]
            extraBytes = data[self.length - self.bytesRead:]
            
        self.bytesRead += len(responsePart)
        client.handleResponsePart(responsePart)
        
        if extraBytes is not None:
            client.setLineMode(extraBytes)
        
    def finished(self):
        return self.length is not None and self.bytesRead == self.length
        
    def receivedAllData(self):
        return self.length is None or self.bytesRead == self.length

class ChunkedDecoder(object):

    def start(self, client):
        self.remainingChunkLength = -1
        self.wantBlank = False

    def dataReceived(self, client, data):
        if self.wantBlank:
            # Expecting the blank line after a chunk of data
            if len(data) != 0:
                client._protocolError("Blank line expected after chunk")
                return
            client.setLineMode()
            self.wantBlank = False
        elif self.remainingChunkLength < 0:
            # Waiting for a line with the next chunk size

            chunksize = data.split(';', 1)[0]
            try:
                self.remainingChunkLength = int(chunksize, 16)
            except:
                client._protocolError("Invalid chunk size, not a hex number: %s!" % chunksize)
                return

            if self.remainingChunkLength < 0:
                client._protocolError("Invalid chunk size, negative.")
                return
                
            if self.remainingChunkLength > 0:
                client.setRawMode()
            else:
                self.wantBlank = True
            
        else:
            datalen = len(data)
            
            if datalen < self.remainingChunkLength:
                self.remainingChunkLength -= datalen
                client.handleResponsePart(data)
                extraData = ""
            else:
                client.handleResponsePart(data[:self.remainingChunkLength])
                extraData = data[self.remainingChunkLength:]
                self.remainingChunkLength = -1

                self.wantBlank = True
                client.setLineMode(extraData)
    
    def finished(self):
        return self.remainingChunkLength == 0 and not self.wantBlank
        
    receivedAllData = finished


class HTTPClient(basic.LineReceiver):
    """
    @ivar request: The C{Request} object currently being
        handled by this client. None until we receive
        the connectionMade() or connectionLost() callbacks.

    @ivar response: The C{Response} object corresponding to
        self.request. None until we receive the status line
        back from the server.
    
    """

    request = None
    response = None
    state    = INITIALIZED
    
    def sendRequest(self, request):

        factory = self.factory
        
        self.request = request

        # Now, send the data. Start with the method...

        path = self.request.uri

        if request.args:
            path += "?%s" % urllib.urlencode(request.args)
        
        self.sendCommand(self.request.method, path, self.request.clientproto)
        
        # Automatically generated headers:
        #
        # Host...
        if factory.host is not None and not self.request.headers.hasHeader('host'):
            host = factory.host
            if factory.port is not None:
                host = "%s:%s" % (host, factory.port)
            self.request.headers.setHeader('host', host)
        
        # Authorization... (only Basic is supported for now)
#         if factory.username:
#             # i.e. if it's None, or empty
#             password = factory.password
#             if password is None: password = ""
            
#             encodedAuth = base64.encodestring(
#                             factory.username +
#                             ':' +
#                             password).strip()
            
#             self.sendHeader("Authorization", "Basic " + encodedAuth)
        
        # Content-Length    
        if self.request.stream:
            contentLength = self.request.stream.length
        else:
            contentLength = 0

        self.request.headers.setHeader('content-length', contentLength)
        
        # Send custom headers, if any
        for (key, valueList) in self.request.headers.getAllRawHeaders():
            for value in valueList:
                self.sendHeader(key, value)
            
        for (key, valueList) in self.factory.headers.getAllRawHeaders():
            for value in valueList:
                self.sendHeader(key, value)
        
        self.endHeaders()
        
        # Lastly, if there's a body, send that.
        if self.request.stream:
            if self.factory.logging: _doLog("[Sent] body (%d byte(s))" % len(self.request.body))

            d = stream.StreamProducer(self.request.stream).beginProducing(self.transport)
            d.addCallback(self._endSendRequest)

    def _endSendRequest(self, result):
        #self.state = WAITING # is this the right place to do this?
        if self.factory.logging: _doLog("[Finished Sending Body]")
            
    def _dealWithFailure(self, failure):
        #
        # Depending on timing, some servers may close the connection
        # while we're busy sending the next request. In this case,
        # we don't want to ding the current request's retry count.
        #
        lastRequestClosed = (self.state > INITIALIZED and \
           self.state <= WAITING and \
           hasattr(self, "_numProcessed") and \
           self._numProcessed > 0) 
           
        if not lastRequestClosed: self.request.retries -= 1
       
        if lastRequestClosed and self.request.retries > 0:
             # Put this request back in the front of the queue
             self.factory.waitingRequests[:0] = [self.request]
        else:
            # OK, buddy, you're outta here!
            if self.request.deferred is not None:
                # @@@ [grant] What about IncompleteResponse()?
                self.request.deferred.errback(failure)
    
    def _protocolError(self, msg):
        self._dealWithFailure(Failure(exc_value=ProtocolError(msg)))
        self.transport.loseConnection()

    def connectionLost(self, failure):
        if self.factory.logging:
            _doLog("[Disconnected] %s" % failure.getTraceback())

        # Were we still dealing with a request? If so,
        # we need to figure out whether or not we processed
        # a complete response or not.

        requestCompleted = False

        if self.request is not None:
            
            requestCompleted = self.response is not None and \
                               self._decoder is not None and \
                               self._decoder.receivedAllData()

            # The server closed the connection, but we have 
            # a request still being processed.
            if not requestCompleted:
                self._dealWithFailure(failure)

        # Set our state to disconnected
        self.state = DISCONNECTED
        
        if requestCompleted:
            self._endResponse()


    def connectionMade(self):
        if self.factory.logging: _doLog("[Connected]")

        self.state = CONNECTED
        self._decoder = None

        if self.request is None:
            # No pending requests, so disconnect
            self.state = DISCONNECTED
            self.transport.loseConnection()
        else:
            self.sendRequest(self.request)


    def sendHeader(self, key, value):
        if self.factory.logging:
            _doLog("[Sent] %s: %s" % (key, value))
        
        key = str(key)     # Must be ASCII
        value = str(value) # ?
        self.sendLine('%s: %s' % (key, value))

    def endHeaders(self):
        if self.factory.logging: _doLog("[Sent]")
        
        self.sendLine('')

        self.state = WAITING

    def handleResponsePart(self, data):
        if self.factory.logging: _doLog("[Received Bytes] (%d byte(s))" % len(data))
        
        self.response.stream.write(data)
    
    def _handleResponseData(self, data):
        self.resetRequestTimeout() # we got data so the connection must still be alive

        if self._decoder is not None:
            self._decoder.dataReceived(self, data)
            
        if self._decoder is not None and self._decoder.finished():
            self._endResponse()
    
    def _headerReceived(self, line):
        if self.factory.logging:
            _doLog("[Received] %s" % line)

        keyValueTuple = line.split(':', 1)
        
        if len(keyValueTuple) != 2:
            self._protocolError("Invalid header line '%s'" % line)
            return
        key, value = keyValueTuple
        value = value.lstrip(' \t')

        self.response.headers.addRawHeader(key, value)
        
    def _endHeaders(self):
        # Make sure we process the last header
        if self.partialHeader:
            self._headerReceived(self.partialHeader)
        self.partialHeader = ''
        
        self.state = READING_BODY
        
        if self.response is not None and self.request is not None:
            if self.response.code in http.NO_BODY_CODES or \
               self.request.method == 'HEAD':
               
                self._decoder = None
                # We will fall through to the self._decoder is None
                # case below
                
            else:
                if self.response.stream is None:
                    self.response.stream = stream.ProducerStream(self.response.headers.getHeader('content-length'))
                    self.response.stream.registerProducer(self, True)

                    if self.request is not None and self.request.deferred is not None:
                        self.request.deferred.callback(self.response)
                                                   
                te = self.response.headers.getHeader('Transfer-Encoding')
                
                # Set up a chunked Transfer-Encoding reader if necessary
                if te and te[-1] == "chunked":
                    self._decoder = ChunkedDecoder()
                else:
                    # @@@ [grant] Should fail if it's an unknown T-E
                    self._decoder = RawDecoder()
    
                self._decoder.start(self)
                    
            if self._decoder is None or self._decoder.finished():
                self._decoder = None
                self._endResponse()
        
    def _endResponse(self):
        # @@@ [grant]: Need to make sure the following work:
        #
        #    (1) No Content-Length or Transfer-Encoding, server just closes
        #        the connection when done.
        #
        #    (2) Content-Length: 0
        #
        #    (3) Transfer-Encoding: chunked (no trailers)
        #    
        #    (4) Transfer-Encoding: chunked (with trailers)

        if self.factory.logging:
            _doLog("[End Response]")

        if self.state != DISCONNECTED:
            self.state = CONNECTED
        self._decoder = None
        
        connection = None
        if self.response is not None:
            if self.response.stream is not None:
                self.response.stream.unregisterProducer()
                self.response.stream.finish()
                
        # assert(self.connection is not None)
#             if self.request is not None and self.request.deferred is not None:
#                 self.request.deferred.callback(self.response)
            if not hasattr(self, "_numProcessed"):
                self._numProcessed = 1
            else:
                self._numProcessed += 1
            
            connection = self.response.headers.getHeader("Connection")
        
        # Reset state so we can send the next response
        # as needed.
        self.request = None
        self.response = None

        # ... if it's a Connection:close response, obey and close.
        if connection and connection[0].strip().lower() == "close":
            self.transport.loseConnection()
            self.state = DISCONNECTED
        else:
            self.setLineMode()
            self.factory.clientCompleted(self)

    def resetRequestTimeout(self):
        if self.request.timeout:
            self.request.setTimeout(self.factory._timeoutRequest, self.request)
            
    def lineReceived(self, line):
        lineLen = len(line)

        if self.state == WAITING:

            statusTuple = line.split(None, 2)
            statusTupleLen = len(statusTuple)
            
            if statusTupleLen == 3 or statusTupleLen == 2:
                version = statusTuple[0]
                try:
                    status = int(statusTuple[1])
                except ValueError:
                    self._protocolError("Unrecognized status '%s'" % statusTuple[1])
                    return
                
                if statusTupleLen > 2:
                    message = statusTuple[2]
                else:
                    message = ""

                if self.factory.logging:
                    _doLog("[Status] %s %s %s" % (status, version, message))

                self.state = READING_HEADERS
                self.partialHeader = ''
                self.response = self.request.responseClass(code=status)
                                                           
            else:
                self._protocolError("Invalid status line '%s'" % line)
        elif self.state == READING_HEADERS:
            if lineLen == 0:
                # Empty line => End of headers
                self._endHeaders()
            elif line[0] in ' \t':
                self.partialHeader += line
            else:
                if self.partialHeader:
                    self._headerReceived(self.partialHeader)
                self.partialHeader = line
        
        elif self.state == READING_BODY:
            self._handleResponseData(line)
        else:
            self._protocolError("Received line unexpectedly (state %d)" % self.state)

    def rawDataReceived(self, data):
        # if self.factory.logging: _doLog("<<<data: %d byte(s)>>> %s" % (len(data), data[:20]))

        if self.state == READING_BODY:
            self._handleResponseData(data)


    def sendCommand(self, command, path, proto):
        command = str(command)
        path = path.encode('utf-8') # URL escape? ascii?
        
        if self.factory.logging:
            _doLog("[Sent] %s %s %s" % (command, path, proto))

        # Override HTTPClient by making sure the version is 1.1
        self.sendLine("%s %s %s" % (command, path, proto))


class HTTPClientFactory(protocol.ClientFactory):
    """
    C{HTTPClientFactory} supports maintains a queue of C{Request} objects,
    and handles retries for any given request.
    """
    protocol = HTTPClient
    logging = False
    sslContextFactory = None
    headers = http_headers.Headers()
    retries = 3
    
    # Other ivars: self._active tracks the current Port or Request
    # object.
    
    def buildProtocol(self, addr):
        result = protocol.ClientFactory.buildProtocol(self, addr)
        
        if result is not None and len(self.waitingRequests) > 0:
            result.request = self.waitingRequests.pop(0)
        
        self._active = result
        return result

    def clientConnectionFailed(self, connector, failure):
        self._active = None
        
        _doLog("[Connection failed]: %s" % failure)

        protocol.ClientFactory.clientConnectionFailed(self, connector, failure)
        
        if len(self.waitingRequests) > 0:
            request = self.waitingRequests.pop(0)
            
            request.retries -= 1
            
            # if we're done retrying, errback this request
            if request.retries <= 0:
                connectionError = error.ConnectionError(
                    failure.getErrorMessage())
                request.deferred.errback(Failure(exc_value=connectionError))
            else:
                # otherwise, try again by inserting
                # this request back in the queue
                self.waitingRequests[:0] = [request]
                
        
        if self._active is None and len(self.waitingRequests) > 0:
            self._makeConnection()

    def clientConnectionLost(self, connector, failure):
        # In this case, there is a protocol object associated
        # with the request. By calling super, the protocol will
        # either errback the request, or insert it back in our waiting
        # queue.
        
        self._active = None
        
        protocol.ClientFactory.clientConnectionLost(self, connector, failure)

        if self._active is None and len(self.waitingRequests) > 0:
            self._makeConnection()

    def __init__(self, host, port=80, authHandlers=None):
        self.host = host
        self.port = port

        self.authHandlers = authHandlers or {}
        
        self.waitingRequests = []
        self._active = None
    
    def _makeConnection(self):
        if self.logging:
            _doLog("[Connecting to %s:%s]" % (self.host, self.port))
            
        if hasattr(self, "wrappingFactory"):
            result = reactor.connectTCP(self.host, self.port, self.wrappingFactory)
        elif self.sslContextFactory is not None:
            result = reactor.connectSSL(self.host, self.port, self.sslContextFactory, self)
        else:
            result = reactor.connectTCP(self.host, self.port, self)
            
        self._active = result
        
        return result


    def addRequest(self, request):
        """
        Adds the given request to our queue of waiting requests, and
        returns a C{deferred} to a C{Reponse} object that will fire when
        the C{Response} is ready.
        """
        if request.retries is None:
            request.retries = self.retries
            
        if request.timeout is not None:
            request.setTimeout(self._timeoutRequest, request)
            
        if len(self.waitingRequests) == 0:
            self.waitingRequests = [request]
        else:
            self.waitingRequests.append(request)

        if self._active is None:
            self._makeConnection()
        else:
            _doLog("[Deferring request %s]" % request.method)
        
        return request.deferred.addCallback(self.handleStatus, request)

    def handleStatus(self, response, request):
        handler = getattr(self, 'handleStatus_%d' % response.code, None)
        if handler:
            return handler(response, request)

        return response

    def handleStatus_401(self, response, request):
        if request.retries <= 0:
            return response

        authHeader = response.headers.getHeader('www-authenticate')
        if authHeader and self.authHandlers:
            creds = self.authHandlers[authHeader[0].lower()].getCredentials(authHeader[1], request)
            if creds:
                req = Request(request.method, request.uri, request.args,
                              request.headers, request.stream)
                
                self.headers.setHeader('authorization', creds)
                req.retries = request.retries - 1
                return self.addRequest(req)
                
        return response

    def registerAuthenticator(self, scheme, authenticator):
        self.authHandlers[scheme] = authenticator
    
    def _timeoutRequest(self, request):

        if request.deferred is not None:
            request._timeoutCall = None
            request.deferred.errback(Failure(exc_value=TimeoutError()))
            
    def clientCompleted(self, client):
        if len(self.waitingRequests) > 0 and client.state == CONNECTED:
            client.sendRequest(self.waitingRequests.pop(0))
        elif client.state != DISCONNECTED:
            # No pending requests, so disconnect
            client.state = DISCONNECTED
            client.transport.loseConnection()
        elif len(self.waitingRequests) > 0 and self._active is None:
            self._makeConnection()
            
    def shutdown(self):
        if len(self.waitingRequests) > 0:
            requests = self.waitingRequests
            self.waitingRequests = []
            
            # @@@ [grant] Should be more specific
        #    map(lambda r: r.errback(Failure()), requests)
        
        if isinstance(self._active, self.protocol):
            client = self._active
            self._active = None
            return defer.maybeDeferred(client.transport.loseConnection)
        elif self._active is not None:
            port = self._active
            self._active = None
            return defer.maybeDeferred(port.disconnect)
        else:
            return None

class HTTPError(Exception):
    """
    An error associated with an HTTP response code
    """
    def __init__(self, status=None, message=None):
        self.status = status
        self.message = message
        
    def __str__(self):
        result = "<" + str(self.__class__)
        
        if self.status != None: result += " (%d)" % self.status
        if self.message != None: result += " " + self.message
        result += ">"
        
        return result
        
class IncompleteResponse(Exception):
    def __init__(self, response):
        super(self, IncompleteResponse).__init__()
        
        self.response = response

class ConnectionError(Exception):
    pass

class ProtocolError(Exception):
    pass
