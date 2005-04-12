# -*- test-case-name: twisted.words.test.test_jabbercomponent -*-
#
# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.


from zope.interface import implements

from twisted.xish import domish, xpath, utility, xmlstream
from twisted.words.protocols.jabber import jstrports

def componentFactory(componentid, password):
    a = ConnectComponentAuthenticator(componentid, password)
    return xmlstream.XmlStreamFactory(a)

class ConnectComponentAuthenticator(xmlstream.ConnectAuthenticator):
    """ Authenticator to permit an XmlStream to authenticate against a Jabber
    Server as a Component (where the Authenticator is initiating the stream).

    This implements the basic component authentication. Unfortunately this
    protocol is not formally described anywhere. Fortunately, all the Jabber
    servers I know of use this mechanism in exactly the same way.

    """
    namespace = 'jabber:component:accept'

    def __init__(self, componentjid, password):
        """
        @type componentjid: L{str}
        @param componentjid: Jabber ID that this component wishes to bind to.

        @type password: L{str}
        @param password: Password/secret this component uses to authenticate.
        """
        xmlstream.ConnectAuthenticator.__init__(self, componentjid)
        self.password = password

    def streamStarted(self, rootelem):
        # Create handshake
        hs = domish.Element(("jabber:component:accept", "handshake"))
        hs.addContent(xmlstream.hashPassword(self.xmlstream.sid, self.password))

        # Setup observer to watch for handshake result
        self.xmlstream.addOnetimeObserver("/handshake", self._handshakeEvent)
        self.xmlstream.send(hs)

    def _handshakeEvent(self, elem):
        self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)

class ListenComponentAuthenticator(xmlstream.Authenticator):
    """ Placeholder for listening components """
    pass


from twisted.application import service
from twisted.python import components

class IService(components.Interface):
    def componentConnected(self, xmlstream):
        """ Parent component has established a connection
        """

    def componentDisconnected(self):
        """ Parent component has lost a connection to the Jabber system
        """

    def transportConnected(self, xmlstream):
        """ Parent component has established a connection over the underlying transport
        """

class Service(service.Service):
    implements(IService)

    def componentConnected(self, xmlstream):
        pass

    def componentDisconnected(self):
        pass

    def transportConnected(self, xmlstream):
        pass

    def send(self, obj):
        self.parent.send(obj)
components.backwardsCompatImplements(Service)

class ServiceManager(service.MultiService):
    """ Business logic representing a managed component connection to a Jabber router

    This Service maintains a single connection to a Jabber router and
    provides facilities for packet routing and transmission. Business
    logic modules can 
    subclasses, and added as sub-service.
    """
    def __init__(self, jid, password):
        service.MultiService.__init__(self)

        # Setup defaults
        self.jabberId = jid
        self.xmlstream = None

        # Internal buffer of packets
        self._packetQueue = []

        # Setup the xmlstream factory
        self._xsFactory = componentFactory(self.jabberId, password)

        # Register some lambda functions to keep the self.xmlstream var up to date
        self._xsFactory.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self._connected)
        self._xsFactory.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self._authd)
        self._xsFactory.addBootstrap(xmlstream.STREAM_END_EVENT, self._disconnected)

        # Map addBootstrap and removeBootstrap to the underlying factory -- is this
        # right? I have no clue...but it'll work for now, until i can think about it
        # more.
        self.addBootstrap = self._xsFactory.addBootstrap
        self.removeBootstrap = self._xsFactory.removeBootstrap

    def getFactory(self):
        return self._xsFactory

    def _connected(self, xs):
        self.xmlstream = xs
        for c in self:
            if IService.providedBy(c):
                c.transportConnected(xs)

    def _authd(self, xs):
        # Flush all pending packets
        for p in self._packetQueue:
            self.xmlstream.send(p)
        self._packetQueue = []

        # Notify all child services which implement
        # the IService interface
        for c in self:
            if IService.providedBy(c):
                c.componentConnected(xs)

    def _disconnected(self, _):
        self.xmlstream = None

        # Notify all child services which implement
        # the IService interface
        for c in self:
            if IService.providedBy(c):
                c.componentDisconnected()

    def send(self, obj):
        if self.xmlstream != None:
            self.xmlstream.send(obj)
        else:
            self._packetQueue.append(obj)




def buildServiceManager(jid, password, strport):
    """ Constructs a pre-built L{ServiceManager}, using the specified strport
        string.    
    """
    svc = ServiceManager(jid, password)
    client_svc = jstrports.client(strport, svc.getFactory())
    client_svc.setServiceParent(svc)
    return svc
