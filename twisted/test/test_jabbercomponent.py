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

import sys, os, sha
from twisted.trial import unittest

from twisted.protocols.jabber.component import ConnectComponentAuthenticator
from twisted.protocols import jabber
from twisted.protocols import xmlstream

class ComponentAuthTest(unittest.TestCase):
    def authPassed(self, stream):
        self.authComplete = True
        
    def testAuth(self):
        self.authComplete = False
        outlist = []

        ca = ConnectComponentAuthenticator("cjid", "secret")
        xs = xmlstream.XmlStream(ca)

        xs.addObserver(xmlstream.STREAM_AUTHD_EVENT,
                       self.authPassed)
        xs.send = outlist.append

        # Go...
        xs.connectionMade()
        xs.dataReceived("<stream:stream xmlns='jabber:component:accept' xmlns:stream='http://etherx.jabber.org/streams' from='cjid' id='12345'>")

        # Calculate what we expect the handshake value to be
        hv = sha.new("%s%s" % ("12345", "secret")).hexdigest()

        self.assertEquals(outlist[1].toXml(),
                          "<handshake>%s</handshake>" % (hv))

        xs.dataReceived("<handshake/>")

        self.assertEquals(self.authComplete, True)
        

class JabberServiceHarness(jabber.component.Service):
    def __init__(self):
        self.componentConnectedFlag = False
        self.componentDisconnectedFlag = False
        self.transportConnectedFlag = False
        
    def componentConnected(self, xmlstream):
        self.componentConnectedFlag = True

    def componentDisconnected(self):
        self.componentDisconnectedFlag = True
        
    def transportConnected(self, xmlstream):
        self.transportConnectedFlag = True


class TestJabberServiceManager(unittest.TestCase):
    def testSM(self):
        # Setup service manager and test harnes
        sm = jabber.component.ServiceManager("foo", "password")
        svc = JabberServiceHarness()
        svc.setServiceParent(sm)

        # Create a write list
        wlist = []

        # Setup a XmlStream
        xs = sm.getFactory().buildProtocol(None)
        xs.transport = self
        xs.transport.write = wlist.append

        # Indicate that it's connected
        xs.connectionMade()

        # Ensure the test service harness got notified
        self.assertEquals(True, svc.transportConnectedFlag)

        # Jump ahead and pretend like the stream got auth'd
        xs.dispatch(xs, xmlstream.STREAM_AUTHD_EVENT)

        # Ensure the test service harness got notified
        self.assertEquals(True, svc.componentConnectedFlag)

        # Pretend to drop the connection
        xs.connectionLost(None)

        # Ensure the test service harness got notified
        self.assertEquals(True, svc.componentDisconnectedFlag)
