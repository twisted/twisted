"""SCGI client resource and protocols.
"""

# TODO:
#   * Handle scgi server death, half way through a resonse.


from zope.interface import implements
from twisted.internet import defer, protocol, reactor
from twisted.protocols import basic
from twisted.web2 import http, iweb, resource, responsecode, stream, twcgi


class SCGIClientResource(resource.LeafResource):
    """A resource that connects to an SCGI server and relays the server's
    response to the browser.
    
    This resource connects to a SCGI server on a known host ('localhost', by
    default) and port. It has no responsibility for starting the SCGI server.
    
    If the server is not running when a client connects then a BAD_GATEWAY
    response will be returned immediately.
    """
    
    def __init__(self, port, host='localhost'):
        """Initialise a SCGI client resource
        """
        resource.LeafResource.__init__(self)
        self.host = host
        self.port = port
    
    def renderHTTP(self, request):
        return doSCGI(request, self.host, self.port)

def doSCGI(request, host, port):
    if request.stream.length is None:
        return http.Response(responsecode.LENGTH_REQUIRED)
    factory = SCGIClientProtocolFactory(request)
    reactor.connectTCP(host, port, factory)
    return factory.deferred
    
class SCGIClientProtocol(basic.LineReceiver):
    """Protocol for talking to a SCGI server.
    """
    
    def __init__(self, request, deferred):
        self.request = request
        self.deferred = deferred
        self.stream = stream.ProducerStream()
        self.response = http.Response(stream=self.stream)

    def connectionMade(self):
        # Ooh, look someone did all the hard work for me :).
        env = twcgi.createCGIEnvironment(self.request)
        # Send the headers. The Content-Length header should always be sent
        # first and must be 0 if not present.
        # The whole lot is sent as one big netstring with each name and value
        # separated by a '\0'.
        contentLength = str(env.pop('CONTENT_LENGTH', 0))
        env['SCGI'] = '1'
        scgiHeaders = []
        scgiHeaders.append('%s\x00%s\x00'%('CONTENT_LENGTH', str(contentLength)))
        scgiHeaders.append('SCGI\x001\x00')
        for name, value in env.iteritems():
            if name in ('CONTENT_LENGTH', 'SCGI'):
                continue
            scgiHeaders.append('%s\x00%s\x00'%(name,value))
        scgiHeaders = ''.join(scgiHeaders)
        self.transport.write('%d:%s,' % (len(scgiHeaders), scgiHeaders))
        stream.StreamProducer(self.request.stream).beginProducing(self.transport)
        
    def lineReceived(self, line):
        # Look for end of headers
        if line == '':
            # Switch into raw mode to recieve data and callback the deferred
            # with the response instance. The data will be streamed as it
            # arrives.  Callback the deferred and set self.response to None,
            # because there are no promises that the response will not be
            # mutated by a resource higher in the tree, such as 
            # log.LogWrapperResource
            self.setRawMode()
            self.deferred.callback(self.response)
            self.response = None
            return

        # Split the header into name and value. The 'Status' header is handled
        # specially; all other headers are simply passed onto the response I'm
        # building.
        name, value = line.split(':',1)
        value = value.strip()
        if name.lower() == 'status':
            value = value.split(None,1)[0]
            self.response.code = int(value)
        else:
            self.response.headers.addRawHeader(name, value)
        
    def rawDataReceived(self, data):
        self.stream.write(data)
        
    def connectionLost(self, reason):
        # The connection is closed and all data has been streamed via the
        # response. Tell the response stream it's over.
        self.stream.finish()
    
    
class SCGIClientProtocolFactory(protocol.ClientFactory):
    """SCGI client protocol factory.
    
    I am created by a SCGIClientResource to connect to an SCGI server. When I
    connect I create a SCGIClientProtocol instance to do all the talking with
    the server.
    
    The ``deferred`` attribute is passed on to the protocol and is fired with
    the HTTP response from the server once it has been recieved.
    """
    protocol = SCGIClientProtocol
    noisy = False # Make Factory shut up
    
    def __init__(self, request):
        self.request = request
        self.deferred = defer.Deferred()
        
    def buildProtocol(self, addr):
        return self.protocol(self.request, self.deferred)
        
    def clientConnectionFailed(self, connector, reason):
        self.sendFailureResponse(reason)
        
    def sendFailureResponse(self, reason):
        response = http.Response(code=responsecode.BAD_GATEWAY, stream=str(reason.value))
        self.deferred.callback(response)
        
__all__ = ['SCGIClientResource']
