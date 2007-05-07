# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.xish.xmlstream}.
"""

from twisted.internet import defer, protocol
from twisted.trial import unittest
from twisted.words.xish import utility, xmlstream

class XmlStreamTest(unittest.TestCase):
    def setUp(self):
        self.errorOccurred = False
        self.streamStarted = False
        self.streamEnded = False
        self.outlist = []
        self.xmlstream = xmlstream.XmlStream()
        self.xmlstream.transport = self
        self.xmlstream.transport.write = self.outlist.append

    # Auxilary methods
    def loseConnection(self):
        self.xmlstream.connectionLost("no reason")

    def streamStartEvent(self, rootelem):
        self.streamStarted = True

    def streamErrorEvent(self, errelem):
        self.errorOccurred = True

    def streamEndEvent(self, _):
        self.streamEnded = True

    def testBasicOp(self):
        xs = self.xmlstream
        xs.addObserver(xmlstream.STREAM_START_EVENT,
                       self.streamStartEvent)
        xs.addObserver(xmlstream.STREAM_ERROR_EVENT,
                       self.streamErrorEvent)
        xs.addObserver(xmlstream.STREAM_END_EVENT,
                       self.streamEndEvent)

        # Go...
        xs.connectionMade()
        xs.send("<root>")
        self.assertEquals(self.outlist[0], "<root>")

        xs.dataReceived("<root>")
        self.assertEquals(self.streamStarted, True)

        self.assertEquals(self.errorOccurred, False)
        self.assertEquals(self.streamEnded, False)
        xs.dataReceived("<child><unclosed></child>")
        self.assertEquals(self.errorOccurred, True)
        self.assertEquals(self.streamEnded, True)


class DummyProtocol(protocol.Protocol, utility.EventDispatcher):
    """
    I am a protocol with an event dispatcher without further processing.

    This protocol is only used for testing XmlStreamFactoryMixin to make
    sure the bootstrap observers are added to the protocol instance.
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.observers = []

        utility.EventDispatcher.__init__(self)


class XmlStreamFactoryMixinTest(unittest.TestCase):

    def test_buildProtocol(self):
        """
        Test building of protocol.

        Arguments passed to Factory should be passed to protocol on
        instantiation. Bootstrap observers should be setup.
        """
        d = defer.Deferred()

        f = xmlstream.XmlStreamFactoryMixin(None, test=None)
        f.protocol = DummyProtocol
        f.addBootstrap('//event/myevent', d.callback)
        xs = f.buildProtocol(None)

        self.assertEquals(f, xs.factory)
        self.assertEquals((None,), xs.args)
        self.assertEquals({'test': None}, xs.kwargs)
        xs.dispatch(None, '//event/myevent')
        return d

    def test_addAndRemoveBootstrap(self):
        """
        Test addition and removal of a bootstrap event handler.
        """
        def cb(self):
            pass

        f = xmlstream.XmlStreamFactoryMixin(None, test=None)

        f.addBootstrap('//event/myevent', cb)
        self.assertIn(('//event/myevent', cb), f.bootstraps)

        f.removeBootstrap('//event/myevent', cb)
        self.assertNotIn(('//event/myevent', cb), f.bootstraps)
