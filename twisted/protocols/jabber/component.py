# -*- test-case-name: twisted.test.test_jabbercomponent -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from twisted.xish import domish, xpath
from twisted.protocols import xmlstream

def componentFactory(componentid, password, ip, port):
    a = ComponentAuthenticator(componentid, password)
    return xmlstream.XmlStreamFactory(a, port, ip)

class ComponentAuthenticator(xmlstream.Authenticator):
    """ Authenticator to permit an XmlStream to authenticate against a Jabber
    Server as a Component

    This implements the basic component authentication. Unfortunately this
    protocol is not formally described anywhere. Fortunately, all the Jabber
    servers I know of use this mechanism in exactly the same way.

    """
    namespace = 'jabber:component:accept'

    def __init__(self, componentjid, password):
        """
        @type componentjid: C{str}
        @param componentjid: Jabber ID that this component wishes to bind to.

        @type password: C{str}
        @param password: Password/secret this component uses to authenticate.
        """
        xmlstream.Authenticator.__init__(self, componentjid)
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


from twisted.application import service

class Service(service.Service):
    """ Business logic superclass for external/connect components

    This class provides the necessary functionality to create a new piece
    of business logic that needs a connection a Jabber router via a connecting
    TCP socket. Subclass key methods such as (L{componentConnected}, L{componentDisconnected})
    to be notified when the component connection comes up and goes down.

    @type xmlstream: L{XmlStream}
    @ivar xmlstream: Accessor for the current XmlStream which connects this object to the router

    """
    def __init__(self, jabberId, serviceParent):
        """
        @type  jabberId: L{str}
        @param jabberId: Jabber ID of this component (used to login to router)

        """
        # Setup defaults
        self.jabberId = jabberId
        self.jabberPassword = None
        self.jabberRouterHost = None
        self.jabberRouterPort = -1
        self.xmlstream = None

        # Internal vars
        self._xsFactory = None
        self._xsConnector = None

    def associateWithRouter(self, password, host, port):
        """
        Bind this service to a particular password, host, and port on a router. The
        component ID used to connect to the router is determined by the jabberId passed
        in the constructor.

        @param password: Password to use for logging into the router
        @param host: DNS or IP address of the router
        @param port: TCP port on the router to connect to
        
        """
        self.jabberPassword = password
        self.jabberRouterHost = host
        self.jabberRouterPort = port

        # Setup the factory
        self._xsFactory = componentFactory(self.jabberId, self.jabberPassword,
                                           self.jabberRouterHost, self.jabberRouterPort)

        # Register some lambda functions to keep the self.xmlstream var up to date
        self._xsFactory.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self._connected)
        self._xsFactory.addBootstrap(xmlstream.STREAM_END_EVENT, self._disconnected)

        # Notify subclass that it should register for bootstrap events
        self.configureEvents(self._xsFactory)

    def _connected(self, xs):
        self.xmlstream = xs
        self.componentConnected()

    def _disconnected(self, obj):
        self.xmlstream = None
        self.componentDisconnected()


    def configureEvents(self, factory):
        """ Register bootstrap events here """
        pass

    def componentConnected(self):
        """ Fired when the component is auth'd with the router """
        pass

    def componentDisconnected(self):
        """ Fired when the component has lost the connection to the router """
        pass

    def startService(self):
        """ If you subclass me, you MUST call me """
        assert self._xsFactory != None
        # Start the connections
        from twisted.internet import reactor
        self._xsConnector = reactor.connectTCP(self._xsFactory.host,
                                               self._xsFactory.port,
                                               self._xsFactory)

    def stopService(self):
        """ If you subclass me, you MUST call me """
        self._xsFactory.stopTrying()
        self._xsConnector.transport.loseConnection()
