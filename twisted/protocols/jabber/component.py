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

from twisted.xish import domish, xpath, utility
from twisted.protocols import xmlstream

def componentFactory(componentid, password):
    a = ComponentAuthenticator(componentid, password)
    return xmlstream.XmlStreamFactory(a)

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

class Service(service.MultiService):
    """ Business logic representing a managed component connection to a Jabber router

    This Service maintains a single connection to a Jabber router and
    provides facilities for packet routing and transmission. Business
    logic modules should be written as standard C{service.Service}
    subclasses, and added as sub-service.
    """
    def __init__(self, jid, password):
        service.MultiService.__init__(self)

        # Setup defaults
        self.jabberId = jid
        self.xmlstream = None

        # Internal buffer of packets
        self._packetQueue = []

        # Internal events for being (dis)connected
        self.connectedEvent = utility.CallbackList()
        self.disconnectedEvent = utility.CallbackList()

        # Setup the xmlstream factory
        self._xsFactory = componentFactory(self.jabberId, password)

        # Register some lambda functions to keep the self.xmlstream var up to date
        self._xsFactory.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self._connected)
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
        for p in self._packetQueue:
            self.xmlstream.send(p)
        self._packetQueue = []
        self.connectedEvent.callback(self.xmlstream)

    def _disconnected(self, _):
        self.xmlstream = None
        self.disconnectedEvent.callback()

    def send(self, obj):
        if self.xmlstream != None:
            self.xmlstream.send(obj)
        else:
            self._packetQueue.append(obj)


import jstrports

def buildService(jid, password, strport):
    """ Constructs a pre-built C{component.Service}, using the specified strport string.    
    """
    svc = Service(jid, password)
    client_svc = jstrports.client(strport, svc.getFactory())
    client_svc.setServiceParent(svc)
    return svc
