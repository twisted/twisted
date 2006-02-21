# Copyright (c) 2006 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Client connection pools, request queuing, etc.
"""
from twisted.internet import protocol
from twisted.web2.client import http
class TrivialConnectionPool:
    """Simple connection pool with keepalive but without pipelineing support."""
    
    def __init__(self):
        self.connectionAddrs = {}
        self.idleConnections = {}
        
    def clientBusy(self, proto):
        print "Busy:", proto
        assert proto not in self.idleConnections.get(self.connectionAddrs[proto], ())
        
    def clientIdle(self, proto):
        print "Idle:", proto
        self.idleConnections.setdefault(self.connectionAddrs[proto], []).append(proto)
        
    def clientPipelining(self, proto):
        print "Pipelining:", proto
    
    def clientGone(self, proto):
        print "Gone:", proto
        addr = self.connectionAddrs.pop(proto)
        try:
            self.idleConnections[addr].remove(proto)
        except KeyError, ValueError:
            pass
        

    def _gotNewConnection(self, proto, addr, req):
        self.connectionAddrs[proto]=addr
        return proto.submitRequest(req, closeAfter=False)
        
    def submitRequest(self, req, addr):
        from twisted.internet import reactor
        d_addr = reactor.resolve(addr)
        
        def _submitRequest(addr):
            pool = self.idleConnections.get(addr)
            if pool:
                proto = pool.pop(0)
                return proto.submitRequest(req, closeAfter=False)
            else:
                d = protocol.ClientCreator(reactor, http.HTTPClientProtocol, manager=self).connectTCP(addr, 80)
                return d.addCallback(self._gotNewConnection, addr, req)
        
        return d_addr.addCallback(_submitRequest)
        
            
        
        

#from twisted.web2.http.client import pool
#p=pool.TrivialConnectionPool()
#p.submitRequest(ClientRequest("GET", "/", {'Host':'localhost'}, None), 'localhost')
