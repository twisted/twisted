#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import sys, os, sha
from twisted.trial import unittest

from twisted.words.protocols.jabber.component import ConnectComponentAuthenticator
from twisted.words.protocols import jabber
from twisted.xish import xmlstream

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
