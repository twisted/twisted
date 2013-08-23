# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.names.server}.
"""

from zope.interface.verify import verifyClass

from twisted.internet.interfaces import IProtocolFactory
from twisted.names import dns, resolve, server
from twisted.trial import unittest



class DNSServerFactoryTests(unittest.TestCase):
    """
    Tests for L{server.DNSServerFactory}.
    """

    def test_resolverType(self):
        """
        L{server.DNSServerFactory.resolver} is a
        L{resolve.ResolverChain} instance
        """
        self.assertIsInstance(
            server.DNSServerFactory().resolver,
            resolve.ResolverChain)


    def test_resolverDefaultEmpty(self):
        """
        L{server.DNSServerFactory.resolver} is an empty
        L{resolve.ResolverChain} by default.
        """
        self.assertEqual(
            server.DNSServerFactory().resolver.resolvers,
            [])


    def test_authorities(self):
        """
        L{server.DNSServerFactory.__init__} accepts an C{authorities}
        argument. The value of this argument is a list and is used to
        extend the C{resolver} L{resolve.ResolverChain}.
        """
        dummyResolver = object()
        self.assertEqual(
            server.DNSServerFactory(
                authorities=[dummyResolver]).resolver.resolvers,
            [dummyResolver])


    def test_caches(self):
        """
        L{server.DNSServerFactory.__init__} accepts a C{caches}
        argument. The value of this argument is a list and is used to
        extend the C{resolver} L{resolve.ResolverChain}.
        """
        dummyResolver = object()
        self.assertEqual(
            server.DNSServerFactory(
                caches=[dummyResolver]).resolver.resolvers,
            [dummyResolver])


    def test_clients(self):
        """
        L{server.DNSServerFactory.__init__} accepts a C{clients}
        argument. The value of this argument is a list and is used to
        extend the C{resolver} L{resolve.ResolverChain}.
        """
        dummyResolver = object()
        self.assertEqual(
            server.DNSServerFactory(
                clients=[dummyResolver]).resolver.resolvers,
            [dummyResolver])


    def test_resolverOrder(self):
        """
        L{server.DNSServerFactory.resolver} contains an ordered list of
        authorities, caches and clients.
        """
        class DummyAuthority: pass
        class DummyCache: pass
        class DummyClient: pass
        self.assertEqual(
            server.DNSServerFactory(
                authorities=[DummyAuthority],
                caches=[DummyCache],
                clients=[DummyClient]).resolver.resolvers,
            [DummyAuthority, DummyCache, DummyClient])


    def test_cacheDefault(self):
        """
        L{server.DNSServerFactory.cache} is L{None} by default.
        """
        self.assertIdentical(server.DNSServerFactory().cache, None)


    def test_cacheOverride(self):
        """
        L{server.DNSServerFactory.__init__} assigns the first object in
        the C{caches} list to L{server.DNSServerFactory.cache}.
        """
        dummyResolver = object()
        self.assertEqual(
            server.DNSServerFactory(caches=[dummyResolver]).cache,
            dummyResolver)


    def test_canRecurseDefault(self):
        """
        L{server.DNSServerFactory.canRecurse} is a flag indicating that
        this server is capable of performing recursive DNS lookups. It
        defaults to L{False}.
        """
        self.assertEqual(server.DNSServerFactory().canRecurse, False)


    def test_canRecurseOverride(self):
        """
        L{server.DNSServerFactory.__init__} sets C{canRecurse} to L{True}
        if it is supplied with C{clients}.
        """
        self.assertEqual(server.DNSServerFactory(clients=[None]).canRecurse, True)


    def test_verboseDefault(self):
        """
        L{server.DNSServerFactory.verbose} defaults to L{False}.
        """
        self.assertEqual(server.DNSServerFactory().verbose, False)


    def test_verboseOverride(self):
        """
        L{server.DNSServerFactory.__init__} accepts a C{verbose} argument
        which overrides L{server.DNSServerFactory.verbose}.
        """
        self.assertEqual(server.DNSServerFactory(verbose=True).verbose, True)


    def test_interface(self):
        """
        L{server.DNSServerFactory} implements L{IProtocolFactory}.
        """
        self.assertTrue(verifyClass(IProtocolFactory, server.DNSServerFactory))


    def test_defaultProtocol(self):
        """
        L{server.DNSServerFactory.protocol} defaults to
        L{dns.DNSProtocol}.
        """
        self.assertIdentical(server.DNSServerFactory.protocol, dns.DNSProtocol)


    def test_buildProtocolDefaultProtocolType(self):
        """
        L{server.DNSServerFactory.buildProtocol} returns an instance of
        L{server.DNSServerFactory.protocol} by default.
        """
        self.assertIsInstance(
            server.DNSServerFactory().buildProtocol(addr=None),
            server.DNSServerFactory.protocol)


    def test_buildProtocolProtocolOverride(self):
        """
        L{server.DNSServerFactory.buildProtocol} builds a protocol by
        calling L{server.DNSServerFactory.protocol} with its self as a
        positional argument.
        """
        class StubProtocol:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        f = server.DNSServerFactory()
        f.protocol = StubProtocol
        p = f.buildProtocol(addr=None)
        self.assertIsInstance(p, StubProtocol)
        self.assertEqual(p.args, (f,))
        self.assertEqual(p.kwargs, {})


    def _messageReceivedTest(self, methodName, message):
        """
        Assert that the named method is called with the given message when
        it is passed to L{DNSServerFactory.messageReceived}.
        """
        # Make it appear to have some queries so that
        # DNSServerFactory.allowQuery allows it.
        message.queries = [None]

        receivedMessages = []
        def fakeHandler(message, protocol, address):
            receivedMessages.append((message, protocol, address))

        class FakeProtocol(object):
            def writeMessage(self, message):
                pass

        protocol = FakeProtocol()
        factory = server.DNSServerFactory(None)
        setattr(factory, methodName, fakeHandler)
        factory.messageReceived(message, protocol)
        self.assertEqual(receivedMessages, [(message, protocol, None)])


    def test_notifyMessageReceived(self):
        """
        L{DNSServerFactory.messageReceived} passes messages with an opcode
        of C{OP_NOTIFY} on to L{DNSServerFactory.handleNotify}.
        """
        # RFC 1996, section 4.5
        opCode = 4
        self._messageReceivedTest('handleNotify', dns.Message(opCode=opCode))


    def test_updateMessageReceived(self):
        """
        L{DNSServerFactory.messageReceived} passes messages with an opcode
        of C{OP_UPDATE} on to L{DNSServerFactory.handleOther}.

        This may change if the implementation ever covers update messages.
        """
        # RFC 2136, section 1.3
        opCode = 5
        self._messageReceivedTest('handleOther', dns.Message(opCode=opCode))


    def test_connectionTracking(self):
        """
        The C{connectionMade} and C{connectionLost} methods of
        L{DNSServerFactory} cooperate to keep track of all
        L{DNSProtocol} objects created by a factory which are
        connected.
        """
        protoA, protoB = object(), object()
        factory = server.DNSServerFactory()
        factory.connectionMade(protoA)
        self.assertEqual(factory.connections, [protoA])
        factory.connectionMade(protoB)
        self.assertEqual(factory.connections, [protoA, protoB])
        factory.connectionLost(protoA)
        self.assertEqual(factory.connections, [protoB])
        factory.connectionLost(protoB)
        self.assertEqual(factory.connections, [])
