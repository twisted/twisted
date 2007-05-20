from zope.interface import Interface

class IHTTPClientManager(Interface):
    """I coordinate between multiple L{HTTPClientProtocol} objects connected to a 
    single server to facilite request queuing and pipelining.
    """

    def clientBusy(proto):
        """Called when the L{HTTPClientProtocol} doesn't want to accept anymore
        requests.

        @param proto: The L{HTTPClientProtocol} that is changing state.
        @type proto: L{HTTPClientProtocol}        
        """
        pass
    
    def clientIdle(proto):
        """Called when an L{HTTPClientProtocol} is able to accept more requests.
    
        @param proto: The L{HTTPClientProtocol} that is changing state.
        @type proto: L{HTTPClientProtocol}
        """
        pass

    def clientPipelining(proto):
        """Called when the L{HTTPClientProtocol} determines that it is able to
        support request pipelining.
    
        @param proto: The L{HTTPClientProtocol} that is changing state.
        @type proto: L{HTTPClientProtocol}
        """
        pass
    
    def clientGone(proto):
        """Called when the L{HTTPClientProtocol} disconnects from the server.

        @param proto: The L{HTTPClientProtocol} that is changing state.
        @type proto: L{HTTPClientProtocol}
        """
        pass
