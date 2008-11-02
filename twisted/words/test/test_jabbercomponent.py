# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.protocols.jabber.component}
"""

import sha
from twisted.trial import unittest

from twisted.words.protocols.jabber import component
from twisted.words.protocols import jabber
from twisted.words.protocols.jabber import xmlstream

class DummyTransport:
    def __init__(self, list):
        self.list = list

    def write(self, bytes):
        self.list.append(bytes)

class ComponentInitiatingInitializerTest(unittest.TestCase):
    def setUp(self):
        self.output = []

        self.authenticator = xmlstream.Authenticator()
        self.authenticator.password = 'secret'
        self.xmlstream = xmlstream.XmlStream(self.authenticator)
        self.xmlstream.namespace = 'test:component'
        self.xmlstream.send = self.output.append
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
                "<stream:stream xmlns='test:component' "
                "xmlns:stream='http://etherx.jabber.org/streams' "
                "from='example.com' id='12345' version='1.0'>")
        self.xmlstream.sid = '12345'
        self.init = component.ComponentInitiatingInitializer(self.xmlstream)

    def testHandshake(self):
        """
        Test basic operations of component handshake.
        """

        d = self.init.initialize()

        # the initializer should have sent the handshake request

        handshake = self.output[-1]
        self.assertEquals('handshake', handshake.name)
        self.assertEquals('test:component', handshake.uri)
        self.assertEquals(sha.new("%s%s" % ('12345', 'secret')).hexdigest(),
                          unicode(handshake))

        # successful authentication

        handshake.children = []
        self.xmlstream.dataReceived(handshake.toXml())

        return d

class ComponentAuthTest(unittest.TestCase):
    def authPassed(self, stream):
        self.authComplete = True

    def testAuth(self):
        self.authComplete = False
        outlist = []

        ca = component.ConnectComponentAuthenticator("cjid", "secret")
        xs = xmlstream.XmlStream(ca)
        xs.transport = DummyTransport(outlist)

        xs.addObserver(xmlstream.STREAM_AUTHD_EVENT,
                       self.authPassed)

        # Go...
        xs.connectionMade()
        xs.dataReceived("<stream:stream xmlns='jabber:component:accept' xmlns:stream='http://etherx.jabber.org/streams' from='cjid' id='12345'>")

        # Calculate what we expect the handshake value to be
        hv = sha.new("%s%s" % ("12345", "secret")).hexdigest()

        self.assertEquals(outlist[1], "<handshake>%s</handshake>" % (hv))

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
