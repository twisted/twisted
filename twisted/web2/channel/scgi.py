from twisted.internet import protocol
from twisted.web2 import responsecode
from twisted.web2.channel import cgi as cgichannel


class SCGIChannelRequest(cgichannel.BaseCGIChannelRequest):
    scgi_vers = "1"
    _data = ""
    headerLen = None
    
    def __init__(self):
        pass
        
    def writeHeaders(self, code, headers):
        l = []
        code_message = responsecode.RESPONSES.get(code, "Unknown Status")
        
        l.append("Status: %s %s\r\n" % (code, code_message))
        if headers is not None:
            for name, valuelist in headers.getAllRawHeaders():
                for value in valuelist:
                    l.append("%s: %s\r\n" % (name, value))
        l.append('\r\n')
        self.transport.writeSequence(l)

    def makeRequest(self, vars):
        scgi_vers = vars['SCGI']
        if scgi_vers != self.scgi_vers:
            _abortWithError(responsecode.INTERNAL_SERVER_ERROR, "Twisted.web SCGITransport: Unknown SCGI version %s" % vars['SCGI'])
        cgichannel.BaseCGIChannelRequest.makeRequest(self, vars)

    def dataReceived(self, data):
        if self.request is None:
            # Reading headers
            self._data += data
            if self.headerLen is None:
                # Haven't gotten a length prefix yet
                datas = data.split(':', 1)
                if len(datas) == 1:
                    return
                self.headerLen = int(datas[0]) + 1 # +1 for the "," at the end
                self._data = datas[1]
                
            if len(self._data) >= self.headerLen:
                # Got all headers
                headerdata=self._data[:self.headerLen]
                data=self._data[self.headerLen:]
                items = headerdata.split('\0')
                assert (len(items) % 2) == 1, "malformed headers"
                assert items[-1]==','
                env = {}
                for i in range(0, len(items) - 1, 2):
                    env[items[i]] = items[i+1]
                    
                self.makeRequest(env)
                self.request.process()
                if self._dataRemaining == 0:
                    self.request.handleContentComplete()
                    return
                if not data:
                    return # no extra data in this packet
                # Fall through, self.request is now set, handle data
            else:
                return
            
        if self._dataRemaining <= 0:
            return
        
        if self._dataRemaining < len(data):
            data = data[:self._dataRemaining]
        self._dataRemaining -= len(data)
        self.request.handleContentChunk(data)
        if self._dataRemaining == 0:
            self.request.handleContentComplete()

    def connectionLost(self, reason):
        if self.request is not None:
            self.request.connectionLost(reason)

class SCGIFactory(protocol.ServerFactory):
    protocol = SCGIChannelRequest
    def __init__(self, requestFactory):
        self.requestFactory=requestFactory

    def buildProtocol(self, addr):
        p = protocol.ServerFactory.buildProtocol(self, addr)
        p.requestFactory=self.requestFactory
        return p
    
__all__ = ['SCGIFactory']
