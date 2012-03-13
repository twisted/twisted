# -*- test-case-name: twisted.test.test_strports -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Construct listening port services from a simple string description.

@see: L{twisted.internet.endpoints.serverFromString}
@see: L{twisted.internet.endpoints.clientFromString}
"""

from zope.interface import implements

from twisted.internet.interfaces import IListeningPort, IAddress
from twisted.internet import endpoints
from twisted.application.internet import StreamServerEndpointService



def service(description, factory, reactor=None):
    """
    Return the service corresponding to a description.

    @param description: The description of the listening port, in the syntax
        described by L{twisted.internet.endpoints.server}.

    @type description: C{str}

    @param factory: The protocol factory which will build protocols for
        connections to this service.

    @type factory: L{twisted.internet.interfaces.IProtocolFactory}

    @rtype: C{twisted.application.service.IService}

    @return: the service corresponding to a description of a reliable
        stream server.

    @see: L{twisted.internet.endpoints.serverFromString}
    """
    if reactor is None:
        from twisted.internet import reactor
    svc = StreamServerEndpointService(
        endpoints.serverFromString(reactor, description), factory)
    svc._raiseSynchronously = True
    return svc



class _NullAddress(object):
    """
    An L{twisted.internet.interfaces.IAddress} provider which represents no
    address.
    """
    implements(IAddress)



class _ListeningPortAdapter(object):
    """
    An adapter to make a L{StreamServerEndpointService} look like a listening
    port.

    @ivar service: The L{StreamServerEndpointService} being wrapped.

    @ivar _wrappedPort: The L{twisted.internet.interfaces.IListeningPort}
        provider that came from the underlying endpoint, or C{None} if there is
        no current port.
    """
    implements(IListeningPort)

    def __init__(self, service):
        self.service = service
        self._wrappedPort = None


    def startListening(self):
        """
        Start listening by starting the wrapped endpoint.
        """
        self.service.startService()
        # Eventually, we'll have the actual listening port.
        @self.service._waitingForPort.addCallback
        def _cb(port):
            self._wrappedPort = port
            return port


    def stopListening(self):
        """
        Stop listening by stopping the wrapped endpoint.
        """
        self._wrappedPort = None
        return self.service.stopService()


    def getHost(self):
        """
        Get the host the wrapped endpoint is listening on, if we're listening.
        """
        # In _most_ cases, listens are immediate and we'll have _wrappedPort as
        # soon as startListening is called. Otherwise, we got nothin'.
        if self._wrappedPort is None:
            return _NullAddress()
        return self._wrappedPort.getHost()



def listen(description, factory, reactor=None):
    """Listen on a port corresponding to a description

    @type description: C{str}
    @type factory: L{twisted.internet.interfaces.IProtocolFactory}
    @rtype: C{twisted.internet.interfaces.IListeningPort}
    @return: the port corresponding to a description of a reliable
    virtual circuit server.

    See the documentation of the C{parse} function for description
    of the semantics of the arguments.
    """
    port = _ListeningPortAdapter(service(description, factory, reactor))
    port.startListening()
    return port



__all__ = ['service', 'listen']
