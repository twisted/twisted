import time, sys
from twisted.internet import protocol
from twisted.internet import reactor, stdio
from twisted.web2 import http, http_headers, server, responsecode
import os

class CGIChannelRequest(protocol.Protocol):
    finished = False
    cgi_vers = (1, 0)
    
    def __init__(self, vars, site):
        headers = http_headers.Headers()
        cgi_vers = http.parseVersion(vars['GATEWAY_INTERFACE'])
        if cgi_vers[0] != 'cgi' or cgi_vers[1] != 1:
            _abortWithError(responsecode.INTERNAL_SERVER_ERROR, "Twisted.web CGITransport: Unknown CGI version %s" % vars['GATEWAY_INTERFACE'])

        http_vers = http.parseVersion(vars['SERVER_PROTOCOL'])
        if http_vers[0] != 'http' or http_vers[1] > 1:
            _abortWithError(responsecode.INTERNAL_SERVER_ERROR, "Twisted.web CGITransport: Unknown HTTP version: " % vars['SERVER_PROTOCOL'])

        if vars.get("HTTPS"): # apache extension?
            protocol = "https"
        else:
            protocol = "http"
            
        port = vars['SERVER_PORT']
        if ((protocol == "http" and port == 80) or
            (protocol == "https" and port == 443)):
            optport = ''
        else:
            optport = ':%s' % port

        uri = vars.get('REQUEST_URI') # apache extension?
        if not uri:
            qstr = vars.get('QUERY_STRING', '')
            if qstr:
                qstr = "?"+urllib.quote(qstr, safe="")
            uri = urllib.quote(vars['SCRIPT_NAME'])+urllib.quote(vars.get('PATH_INFO',  ''))+qstr
            
        for name,val in vars.iteritems():
            if name.startswith('HTTP_'):
                name = name[5:].replace('_', '-')
            elif name == 'CONTENT_LENGTH':
                name = 'Content-Length'
            elif name == 'CONTENT_TYPE':
                name = 'Content-Type'
            headers.setRawHeaders(name, val)
            
        self.request = server.Request(self, vars['REQUEST_METHOD'], uri, http_vers[1:2], headers, site=site, prepathuri=vars['SCRIPT_NAME'])

        self._dataRemaining = int(vars.get('CONTENT_LENGTH', '0'))
            
    def writeIntermediateResponse(self, code, headers=None):
        """Ignore, CGI doesn't support."""
        pass
    
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

    def writeData(self, data):
        self.transport.write(data)
    
    def finish(self):
        if self.finished:
            warnings.warn("Warning! request.finish called twice.", stacklevel=2)
            return
        self.finished = True
#        self.transport.loseConnection()
        self.transport.closeStdin()

    def abortConnection(self, closeWrite=True):
#        self.transport.loseConnection()
        self.transport.closeStdin()
    
    def registerProducer(self, producer, streaming):
        self.transport.registerProducer(producer, streaming)
    
    def unregisterProducer(self):
        self.transport.unregisterProducer()


    
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
        if self._dataRemaining == 0:
            self.request.handleContentComplete()
        
    def connectionLost(self, reason):
        if reactor.running:
            reactor.stop()

def startCGI(site):
    """Call this as the last thing in your CGI python script in order to
    hook up your site object with the incoming request."""
    stdio.StandardIO(CGIChannnelRequest(os.environ, site))
    reactor.run()

if __name__ == '__main__':
    import pdb, signal, sys
    from twisted.python import util
#    sys.settrace(util.spewer)
    signal.signal(signal.SIGQUIT, lambda *args: pdb.set_trace())
    
    from twisted.web2 import static
    site = server.Site(static.Data('foobar', 'text/plain'))
    startCGI(site)
