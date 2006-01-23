import warnings
import os
import urllib
from zope.interface import implements

from twisted.internet import protocol, address
from twisted.internet import reactor, interfaces
from twisted.web2 import http, http_headers, server, responsecode

class BaseCGIChannelRequest(protocol.Protocol):
    implements(interfaces.IHalfCloseableProtocol)
    
    finished = False
    requestFactory = http.Request
    request = None
    
    def makeRequest(self, vars):
        headers = http_headers.Headers()
        http_vers = http.parseVersion(vars['SERVER_PROTOCOL'])
        if http_vers[0] != 'http' or http_vers[1] > 1:
            _abortWithError(responsecode.INTERNAL_SERVER_ERROR, "Twisted.web CGITransport: Unknown HTTP version: " % vars['SERVER_PROTOCOL'])

        secure = vars.get("HTTPS") in ("1", "on") # apache extension?
        port = vars.get('SERVER_PORT') or 80
        server_host = vars.get('SERVER_NAME') or vars.get('SERVER_ADDR') or 'localhost'
        
        self.hostinfo = address.IPv4Address('TCP', server_host, port), bool(secure)
        self.remoteinfo = address.IPv4Address(
            'TCP', vars.get('REMOTE_ADDR', ''), vars.get('REMOTE_PORT', 0))
        
        uri = vars.get('REQUEST_URI') # apache extension?
        if not uri:
            qstr = vars.get('QUERY_STRING', '')
            if qstr:
                qstr = "?"+urllib.quote(qstr, safe="")
            uri = urllib.quote(vars['SCRIPT_NAME'])+urllib.quote(vars.get('PATH_INFO',  ''))+qstr
            
        for name,val in vars.iteritems():
            if name.startswith('HTTP_'):
                name = name[5:].replace('_', '-')
            elif name == 'CONTENT_TYPE':
                name = 'content-type'
            else:
                continue
            headers.setRawHeaders(name, (val,))
            
        self._dataRemaining = int(vars.get('CONTENT_LENGTH', '0'))
        self.request = self.requestFactory(self, vars['REQUEST_METHOD'], uri, http_vers[1:3], self._dataRemaining, headers, prepathuri=vars['SCRIPT_NAME'])
        
    def writeIntermediateResponse(self, code, headers=None):
        """Ignore, CGI doesn't support."""
        pass
    
    def write(self, data):
        self.transport.write(data)
    
    def finish(self):
        if self.finished:
            warnings.warn("Warning! request.finish called twice.", stacklevel=2)
            return
        self.finished = True
        self.transport.loseConnection()

    def getHostInfo(self):
        return self.hostinfo

    def getRemoteHost(self):
        return self.remoteinfo
        
    def abortConnection(self, closeWrite=True):
        self.transport.loseConnection()
    
    def registerProducer(self, producer, streaming):
        self.transport.registerProducer(producer, streaming)
    
    def unregisterProducer(self):
        self.transport.unregisterProducer()

    def writeConnectionLost(self):
        self.loseConnection()
        
    def readConnectionLost(self):
        if self._dataRemaining > 0:
            # content-length was wrong, abort
            self.loseConnection()
    
class CGIChannelRequest(BaseCGIChannelRequest):
    cgi_vers = (1, 0)
    
    def __init__(self, requestFactory, vars):
        self.requestFactory=requestFactory
        cgi_vers = http.parseVersion(vars['GATEWAY_INTERFACE'])
        if cgi_vers[0] != 'cgi' or cgi_vers[1] != 1:
            _abortWithError(responsecode.INTERNAL_SERVER_ERROR, "Twisted.web CGITransport: Unknown CGI version %s" % vars['GATEWAY_INTERFACE'])
        self.makeRequest(vars)
        
    def writeHeaders(self, code, headers):
        l = []
        code_message = responsecode.RESPONSES.get(code, "Unknown Status")
        
        l.append("Status: %s %s\n" % (code, code_message))
        if headers is not None:
            for name, valuelist in headers.getAllRawHeaders():
                for value in valuelist:
                    l.append("%s: %s\n" % (name, value))
        l.append('\n')
        self.transport.writeSequence(l)
    
    def dataReceived(self, data):
        if self._dataRemaining <= 0:
            return
        
        if self._dataRemaining < len(data):
            data = data[:self._dataRemaining]
        self._dataRemaining -= len(data)
        self.request.handleContentChunk(data)
        if self._dataRemaining == 0:
            self.request.handleContentComplete()

    def connectionMade(self):
        self.request.process()
        if self._dataRemaining == 0:
            self.request.handleContentComplete()
        
    def connectionLost(self, reason):
        if reactor.running:
            reactor.stop()

def startCGI(site):
    """Call this as the last thing in your CGI python script in order to
    hook up your site object with the incoming request.

    E.g.:
    >>> from twisted.web2 import channel, server
    >>> if __name__ == '__main__':
    ...     channel.startCGI(server.Site(myToplevelResource))
    
    """
    from twisted.internet.stdio import StandardIO
    StandardIO(CGIChannelRequest(site, os.environ))
    reactor.run()

__all__ = ['startCGI']
