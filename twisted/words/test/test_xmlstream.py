# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.xish.xmlstream}.
"""

from twisted.internet import protocol
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



class BootstrapMixinTest(unittest.TestCase):
    """
    Tests for L{xmlstream.BootstrapMixin}.

    @ivar factory: Instance of the factory or mixin under test.
    """

    def setUp(self):
        self.factory = xmlstream.BootstrapMixin()


    def test_installBootstraps(self):
        """
        Dispatching an event should fire registered bootstrap observers.
        """
        called = []

        def cb(data):
            called.append(data)

        dispatcher = DummyProtocol()
        self.factory.addBootstrap('//event/myevent', cb)
        self.factory.installBootstraps(dispatcher)

        dispatcher.dispatch(None, '//event/myevent')
        self.assertEquals(1, len(called))


    def test_addAndRemoveBootstrap(self):
        """
        Test addition and removal of a bootstrap event handler.
        """

        called = []

        def cb(data):
            called.append(data)

        self.factory.addBootstrap('//event/myevent', cb)
        self.factory.removeBootstrap('//event/myevent', cb)

        dispatcher = DummyProtocol()
        self.factory.installBootstraps(dispatcher)

        dispatcher.dispatch(None, '//event/myevent')
        self.assertFalse(called)



class GenericXmlStreamFactoryTestsMixin(BootstrapMixinTest):
    """
    Generic tests for L{XmlStream} factories.
    """

    def setUp(self):
        self.factory = xmlstream.XmlStreamFactory()


    def test_buildProtocolInstallsBootstraps(self):
        """
        The protocol factory installs bootstrap event handlers on the protocol.
        """
        called = []

        def cb(data):
            called.append(data)

        self.factory.addBootstrap('//event/myevent', cb)

        xs = self.factory.buildProtocol(None)
        xs.dispatch(None, '//event/myevent')

        self.assertEquals(1, len(called))


    def test_buildProtocolStoresFactory(self):
        """
        The protocol factory is saved in the protocol.
        """
        xs = self.factory.buildProtocol(None)
        self.assertIdentical(self.factory, xs.factory)



class XmlStreamFactoryMixinTest(GenericXmlStreamFactoryTestsMixin):
    """
    Tests for L{xmlstream.XmlStreamFactoryMixin}.
    """

    def setUp(self):
        self.factory = xmlstream.XmlStreamFactoryMixin(None, test=None)
        self.factory.protocol = DummyProtocol


    def test_buildProtocolFactoryArguments(self):
        """
        Arguments passed to the factory should be passed to protocol on
        instantiation.
        """
        xs = self.factory.buildProtocol(None)

        self.assertEquals((None,), xs.args)
        self.assertEquals({'test': None}, xs.kwargs)
