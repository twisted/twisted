# -*- test-case-name: twisted.words.test.test_jabbercomponent -*-
#
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
External server-side components.

Most Jabber server implementations allow for add-on components that act as a
seperate entity on the Jabber network, but use the server-to-server
functionality of a regular Jabber IM server. These so-called 'external
components' are connected to the Jabber server using the Jabber Component
Protocol as defined in U{JEP-0114<http://www.jabber.org/jeps/jep-0114.html>}.

This module allows for writing external server-side component by assigning one
or more services implementing L{ijabber.IService} up to L{ServiceManager}. The
ServiceManager connects to the Jabber server and is responsible for the
corresponding XML stream.
"""

from zope.interface import implements

from twisted.application import service
from twisted.internet import defer
from twisted.words.xish import domish
from twisted.words.protocols.jabber import ijabber, jstrports, xmlstream

def componentFactory(componentid, password):
    """
    XML stream factory for external server-side components.

    @param componentid: JID of the component.
    @type componentid: L{unicode}
    @param password: password used to authenticate to the server.
    @type password: L{str}
    """
    a = ConnectComponentAuthenticator(componentid, password)
    return xmlstream.XmlStreamFactory(a)

class ComponentInitiatingInitializer(object):
    """
    External server-side component authentication initializer for the
    initiating entity.

    @ivar xmlstream: XML stream between server and component.
    @type xmlstream: L{xmlstream.XmlStream}
    """

    def __init__(self, xs):
        self.xmlstream = xs
        self._deferred = None

    def initialize(self):
        xs = self.xmlstream
        hs = domish.Element((self.xmlstream.namespace, "handshake"))
        hs.addContent(xmlstream.hashPassword(xs.sid,
                                             xs.authenticator.password))

        # Setup observer to watch for handshake result
        xs.addOnetimeObserver("/handshake", self._cbHandshake)
        xs.send(hs)
        self._deferred = defer.Deferred()
        return self._deferred

    def _cbHandshake(self, _):
        # we have successfully shaken hands and can now consider this
        # entity to represent the component JID.
        self.xmlstream.thisEntity = self.xmlstream.otherEntity
        self._deferred.callback(None)

class ConnectComponentAuthenticator(xmlstream.ConnectAuthenticator):
    """
    Authenticator to permit an XmlStream to authenticate against a Jabber
    server as an external component (where the Authenticator is initiating the
    stream).
    """
    namespace = 'jabber:component:accept'

    def __init__(self, componentjid, password):
        """
        @type componentjid: L{str}
        @param componentjid: Jabber ID that this component wishes to bind to.

        @type password: L{str}
        @param password: Password/secret this component uses to authenticate.
        """
        # Note that we are sending 'to' our desired component JID.
        xmlstream.ConnectAuthenticator.__init__(self, componentjid)
        self.password = password

    def associateWithStream(self, xs):
        xs.version = (0, 0)
        xmlstream.ConnectAuthenticator.associateWithStream(self, xs)

        xs.initializers = [ComponentInitiatingInitializer(xs)]

class ListenComponentAuthenticator(xmlstream.Authenticator):
    """
    Placeholder for listening components.
    """

class Service(service.Service):
    """
    External server-side component service.
    """

    implements(ijabber.IService)

    def componentConnected(self, xs):
        pass

    def componentDisconnected(self):
        pass

    def transportConnected(self, xs):
        pass

    def send(self, obj):
        """
        Send data over service parent's XML stream.

        @note: L{ServiceManager} maintains a queue for data sent using this
        method when there is no current established XML stream. This data is
        then sent as soon as a new stream has been established and initialized.
        Subsequently, L{componentConnected} will be called again. If this
        queueing is not desired, use C{send} on the XmlStream object (passed to
        L{componentConnected}) directly.

        @param obj: data to be sent over the XML stream. This is usually an
        object providing L{domish.IElement}, or serialized XML. See
        L{xmlstream.XmlStream} for details.
        """

        self.parent.send(obj)

class ServiceManager(service.MultiService):
    """
    Business logic representing a managed component connection to a Jabber
    router.

    This service maintains a single connection to a Jabber router and provides
    facilities for packet routing and transmission. Business logic modules are
    services implementing L{ijabber.IService} (like subclasses of L{Service}), and
    added as sub-service.
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

        # Register some lambda functions to keep the self.xmlstream var up to
        # date
        self._xsFactory.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT,
                                     self._connected)
        self._xsFactory.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self._authd)
        self._xsFactory.addBootstrap(xmlstream.STREAM_END_EVENT,
                                     self._disconnected)

        # Map addBootstrap and removeBootstrap to the underlying factory -- is
        # this right? I have no clue...but it'll work for now, until i can
        # think about it more.
        self.addBootstrap = self._xsFactory.addBootstrap
        self.removeBootstrap = self._xsFactory.removeBootstrap

    def getFactory(self):
        return self._xsFactory

    def _connected(self, xs):
        self.xmlstream = xs
        for c in self:
            if ijabber.IService.providedBy(c):
                c.transportConnected(xs)

    def _authd(self, xs):
        # Flush all pending packets
        for p in self._packetQueue:
            self.xmlstream.send(p)
        self._packetQueue = []

        # Notify all child services which implement the IService interface
        for c in self:
            if ijabber.IService.providedBy(c):
                c.componentConnected(xs)

    def _disconnected(self, _):
        self.xmlstream = None

        # Notify all child services which implement
        # the IService interface
        for c in self:
            if ijabber.IService.providedBy(c):
                c.componentDisconnected()

    def send(self, obj):
        """
        Send data over the XML stream.

        When there is no established XML stream, the data is queued and sent
        out when a new XML stream has been established and initialized.

        @param obj: data to be sent over the XML stream. This is usually an
        object providing L{domish.IElement}, or serialized XML. See
        L{xmlstream.XmlStream} for details.
        """

        if self.xmlstream != None:
            self.xmlstream.send(obj)
        else:
            self._packetQueue.append(obj)

def buildServiceManager(jid, password, strport):
    """
    Constructs a pre-built L{ServiceManager}, using the specified strport
    string.
    """

    svc = ServiceManager(jid, password)
    client_svc = jstrports.client(strport, svc.getFactory())
    client_svc.setServiceParent(svc)
    return svc
