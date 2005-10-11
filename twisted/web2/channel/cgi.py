import warnings
from twisted.internet import protocol, address
from twisted.internet import reactor
from twisted.web2 import http, http_headers, server, responsecode
import os
import urllib

# Move this to twisted core soonish
from twisted.internet import error, interfaces
from twisted.python import log, failure
from zope.interface import implements

class StdIOThatDoesntSuckAsBad(object):
    implements(interfaces.ITransport, interfaces.IProducer, interfaces.IConsumer, interfaces.IHalfCloseableDescriptor)
    _reader = None
    _writer = None
    disconnected = False

    def __init__(self, proto, stdin=0, stdout=1):
        from twisted.internet import fdesc, process
        
        self.protocol = proto
        
        fdesc.setNonBlocking(stdin)
        fdesc.setNonBlocking(stdout)
        self._reader=process.ProcessReader(reactor, self, 'read', stdin)
        self._reader.proto=self
        self._reader.startReading()
        self._writer=process.ProcessWriter(reactor, self, 'write', stdout)
        self._writer.proto=self
        self._writer.startReading()
        self.protocol.makeConnection(self)

    # ITransport
    def loseWriteConnection(self):
        if self._writer is not None:
            self._writer.loseConnection()
        
    def write(self, data):
        if self._writer is not None:
            self._writer.write(data)
            
    def writeSequence(self, data):
        if self._writer is not None:
            self._writer.writeSequence(data)
            
    def loseConnection(self):
        self.disconnecting = True
        
        if self._writer is not None:
            self._writer.loseConnection()
        if self._reader is not None:
            # Don't loseConnection, because we don't want to SIGPIPE it.
            self._reader.stopReading()
        
    def getPeer(self):
        return 'i wonder what goes here'
    
    def getHost(self):
        return 'i wonder what goes here'


    # Callbacks from process.ProcessReader/ProcessWriter
    def childDataReceived(self, fd, data):
        self.protocol.dataReceived(data)

    def childConnectionLost(self, fd, reason):
        if self.disconnected:
            return
        
        if reason.value.__class__ == error.ConnectionDone:
            # Normal close
            if fd == 'read':
                self._readConnectionLost(reason)
            else:
                self._writeConnectionLost(reason)
        else:
            self.connectionLost(reason)

    def connectionLost(self, reason):
        self.disconnected = True
        
        # Make sure to cleanup the other half
        _reader = self._reader
        _writer = self._writer
        protocol = self.protocol
        self._reader = self._writer = None
        self.protocol = None
        
        if _writer is not None and not _writer.disconnected:
            _writer.connectionLost(reason)
        
        if _reader is not None and not _reader.disconnected:
            _reader.connectionLost(reason)
        
        try:
            protocol.connectionLost(reason)
        except:
            log.err()
        
    def _writeConnectionLost(self, reason):
        self._writer=None
        if self.disconnecting:
            self.connectionLost(reason)
            return
        
        p = interfaces.IHalfCloseableProtocol(self.protocol, None)
        if p:
            try:
                p.writeConnectionLost()
            except:
                log.err()
                self.connectionLost(failure.Failure())

    def _readConnectionLost(self, reason):
        self._reader=None
        p = interfaces.IHalfCloseableProtocol(self.protocol, None)
        if p:
            try:
                p.readConnectionLost()
            except:
                log.err()
                self.connectionLost(failure.Failure())
        else:
            self.connectionLost(reason)

    # IConsumer
    def registerProducer(self, producer, streaming):
        if self._writer is None:
            producer.stopProducing()
        else:
            self._writer.registerProducer(producer, streaming)
            
    def unregisterProducer(self):
        if self._writer is not None:
            self._writer.unregisterProducer()

    # IProducer
    def stopProducing(self):
        self.loseConnection()

    def pauseProducing(self):
        if self._reader is not None:
            self._reader.pauseProducing()

    def resumeProducing(self):
        if self._reader is not None:
            self._reader.resumeProducing()

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
        headers.setHeader('content-length', self._dataRemaining)
        self.request = self.requestFactory(self, vars['REQUEST_METHOD'], uri, http_vers[1:3], headers, prepathuri=vars['SCRIPT_NAME'])
        
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
    StdIOThatDoesntSuckAsBad(CGIChannelRequest(site, os.environ))
    reactor.run()

__all__ = ['startCGI']
