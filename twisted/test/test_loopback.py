# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test case for L{twisted.protocols.loopback}.
"""

from zope.interface import implements

from twisted.trial import unittest
from twisted.trial.util import suppress as SUPPRESS
from twisted.protocols import basic, loopback
from twisted.internet import defer
from twisted.internet.protocol import Protocol
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IAddress, IPushProducer, IPullProducer
from twisted.internet import reactor, interfaces


class SimpleProtocol(basic.LineReceiver):
    def __init__(self):
        self.conn = defer.Deferred()
        self.lines = []
        self.connLost = []

    def connectionMade(self):
        self.conn.callback(None)

    def lineReceived(self, line):
        self.lines.append(line)

    def connectionLost(self, reason):
        self.connLost.append(reason)


class DoomProtocol(SimpleProtocol):
    i = 0
    def lineReceived(self, line):
        self.i += 1
        if self.i < 4:
            # by this point we should have connection closed,
            # but just in case we didn't we won't ever send 'Hello 4'
            self.sendLine("Hello %d" % self.i)
        SimpleProtocol.lineReceived(self, line)
        if self.lines[-1] == "Hello 3":
            self.transport.loseConnection()


class LoopbackTestCaseMixin:
    def testRegularFunction(self):
        s = SimpleProtocol()
        c = SimpleProtocol()

        def sendALine(result):
            s.sendLine("THIS IS LINE ONE!")
            s.transport.loseConnection()
        s.conn.addCallback(sendALine)

        def check(ignored):
            self.assertEqual(c.lines, ["THIS IS LINE ONE!"])
            self.assertEqual(len(s.connLost), 1)
            self.assertEqual(len(c.connLost), 1)
        d = defer.maybeDeferred(self.loopbackFunc, s, c)
        d.addCallback(check)
        return d

    def testSneakyHiddenDoom(self):
        s = DoomProtocol()
        c = DoomProtocol()

        def sendALine(result):
            s.sendLine("DOOM LINE")
        s.conn.addCallback(sendALine)

        def check(ignored):
            self.assertEqual(s.lines, ['Hello 1', 'Hello 2', 'Hello 3'])
            self.assertEqual(c.lines, ['DOOM LINE', 'Hello 1', 'Hello 2', 'Hello 3'])
            self.assertEqual(len(s.connLost), 1)
            self.assertEqual(len(c.connLost), 1)
        d = defer.maybeDeferred(self.loopbackFunc, s, c)
        d.addCallback(check)
        return d



class LoopbackAsyncTestCase(LoopbackTestCaseMixin, unittest.TestCase):
    loopbackFunc = staticmethod(loopback.loopbackAsync)


    def test_makeConnection(self):
        """
        Test that the client and server protocol both have makeConnection
        invoked on them by loopbackAsync.
        """
        class TestProtocol(Protocol):
            transport = None
            def makeConnection(self, transport):
                self.transport = transport

        server = TestProtocol()
        client = TestProtocol()
        loopback.loopbackAsync(server, client)
        self.failIfEqual(client.transport, None)
        self.failIfEqual(server.transport, None)


    def _hostpeertest(self, get, testServer):
        """
        Test one of the permutations of client/server host/peer.
        """
        class TestProtocol(Protocol):
            def makeConnection(self, transport):
                Protocol.makeConnection(self, transport)
                self.onConnection.callback(transport)

        if testServer:
            server = TestProtocol()
            d = server.onConnection = Deferred()
            client = Protocol()
        else:
            server = Protocol()
            client = TestProtocol()
            d = client.onConnection = Deferred()

        loopback.loopbackAsync(server, client)

        def connected(transport):
            host = getattr(transport, get)()
            self.failUnless(IAddress.providedBy(host))

        return d.addCallback(connected)


    def test_serverHost(self):
        """
        Test that the server gets a transport with a properly functioning
        implementation of L{ITransport.getHost}.
        """
        return self._hostpeertest("getHost", True)


    def test_serverPeer(self):
        """
        Like C{test_serverHost} but for L{ITransport.getPeer}
        """
        return self._hostpeertest("getPeer", True)


    def test_clientHost(self, get="getHost"):
        """
        Test that the client gets a transport with a properly functioning
        implementation of L{ITransport.getHost}.
        """
        return self._hostpeertest("getHost", False)


    def test_clientPeer(self):
        """
        Like C{test_clientHost} but for L{ITransport.getPeer}.
        """
        return self._hostpeertest("getPeer", False)


    def _greetingtest(self, write, testServer):
        """
        Test one of the permutations of write/writeSequence client/server.
        """
        class GreeteeProtocol(Protocol):
            bytes = ""
            def dataReceived(self, bytes):
                self.bytes += bytes
                if self.bytes == "bytes":
                    self.received.callback(None)

        class GreeterProtocol(Protocol):
            def connectionMade(self):
                getattr(self.transport, write)("bytes")

        if testServer:
            server = GreeterProtocol()
            client = GreeteeProtocol()
            d = client.received = Deferred()
        else:
            server = GreeteeProtocol()
            d = server.received = Deferred()
            client = GreeterProtocol()

        loopback.loopbackAsync(server, client)
        return d


    def test_clientGreeting(self):
        """
        Test that on a connection where the client speaks first, the server
        receives the bytes sent by the client.
        """
        return self._greetingtest("write", False)


    def test_clientGreetingSequence(self):
        """
        Like C{test_clientGreeting}, but use C{writeSequence} instead of
        C{write} to issue the greeting.
        """
        return self._greetingtest("writeSequence", False)


    def test_serverGreeting(self, write="write"):
        """
        Test that on a connection where the server speaks first, the client
        receives the bytes sent by the server.
        """
        return self._greetingtest("write", True)


    def test_serverGreetingSequence(self):
        """
        Like C{test_serverGreeting}, but use C{writeSequence} instead of
        C{write} to issue the greeting.
        """
        return self._greetingtest("writeSequence", True)


    def _producertest(self, producerClass):
        toProduce = map(str, range(0, 10))

        class ProducingProtocol(Protocol):
            def connectionMade(self):
                self.producer = producerClass(list(toProduce))
                self.producer.start(self.transport)

        class ReceivingProtocol(Protocol):
            bytes = ""
            def dataReceived(self, bytes):
                self.bytes += bytes
                if self.bytes == ''.join(toProduce):
                    self.received.callback((client, server))

        server = ProducingProtocol()
        client = ReceivingProtocol()
        client.received = Deferred()

        loopback.loopbackAsync(server, client)
        return client.received


    def test_pushProducer(self):
        """
        Test a push producer registered against a loopback transport.
        """
        class PushProducer(object):
            implements(IPushProducer)
            resumed = False

            def __init__(self, toProduce):
                self.toProduce = toProduce

            def resumeProducing(self):
                self.resumed = True

            def start(self, consumer):
                self.consumer = consumer
                consumer.registerProducer(self, True)
                self._produceAndSchedule()

            def _produceAndSchedule(self):
                if self.toProduce:
                    self.consumer.write(self.toProduce.pop(0))
                    reactor.callLater(0, self._produceAndSchedule)
                else:
                    self.consumer.unregisterProducer()
        d = self._producertest(PushProducer)

        def finished((client, server)):
            self.failIf(
                server.producer.resumed,
                "Streaming producer should not have been resumed.")
        d.addCallback(finished)
        return d


    def test_pullProducer(self):
        """
        Test a pull producer registered against a loopback transport.
        """
        class PullProducer(object):
            implements(IPullProducer)

            def __init__(self, toProduce):
                self.toProduce = toProduce

            def start(self, consumer):
                self.consumer = consumer
                self.consumer.registerProducer(self, False)

            def resumeProducing(self):
                self.consumer.write(self.toProduce.pop(0))
                if not self.toProduce:
                    self.consumer.unregisterProducer()
        return self._producertest(PullProducer)


    def test_writeNotReentrant(self):
        """
        L{loopback.loopbackAsync} does not call a protocol's C{dataReceived}
        method while that protocol's transport's C{write} method is higher up
        on the stack.
        """
        class Server(Protocol):
            def dataReceived(self, bytes):
                self.transport.write("bytes")

        class Client(Protocol):
            ready = False

            def connectionMade(self):
                reactor.callLater(0, self.go)

            def go(self):
                self.transport.write("foo")
                self.ready = True

            def dataReceived(self, bytes):
                self.wasReady = self.ready
                self.transport.loseConnection()


        server = Server()
        client = Client()
        d = loopback.loopbackAsync(client, server)
        def cbFinished(ignored):
            self.assertTrue(client.wasReady)
        d.addCallback(cbFinished)
        return d


    def test_pumpPolicy(self):
        """
        The callable passed as the value for the C{pumpPolicy} parameter to
        L{loopbackAsync} is called with a L{_LoopbackQueue} of pending bytes
        and a protocol to which they should be delivered.
        """
        pumpCalls = []
        def dummyPolicy(queue, target):
            bytes = []
            while queue:
                bytes.append(queue.get())
            pumpCalls.append((target, bytes))

        client = Protocol()
        server = Protocol()

        finished = loopback.loopbackAsync(server, client, dummyPolicy)
        self.assertEqual(pumpCalls, [])

        client.transport.write("foo")
        client.transport.write("bar")
        server.transport.write("baz")
        server.transport.write("quux")
        server.transport.loseConnection()

        def cbComplete(ignored):
            self.assertEqual(
                pumpCalls,
                # The order here is somewhat arbitrary.  The implementation
                # happens to always deliver data to the client first.
                [(client, ["baz", "quux", None]),
                 (server, ["foo", "bar"])])
        finished.addCallback(cbComplete)
        return finished


    def test_identityPumpPolicy(self):
        """
        L{identityPumpPolicy} is a pump policy which calls the target's
        C{dataReceived} method one for each string in the queue passed to it.
        """
        bytes = []
        client = Protocol()
        client.dataReceived = bytes.append
        queue = loopback._LoopbackQueue()
        queue.put("foo")
        queue.put("bar")
        queue.put(None)

        loopback.identityPumpPolicy(queue, client)

        self.assertEqual(bytes, ["foo", "bar"])


    def test_collapsingPumpPolicy(self):
        """
        L{collapsingPumpPolicy} is a pump policy which calls the target's
        C{dataReceived} only once with all of the strings in the queue passed
        to it joined together.
        """
        bytes = []
        client = Protocol()
        client.dataReceived = bytes.append
        queue = loopback._LoopbackQueue()
        queue.put("foo")
        queue.put("bar")
        queue.put(None)

        loopback.collapsingPumpPolicy(queue, client)

        self.assertEqual(bytes, ["foobar"])



class LoopbackTCPTestCase(LoopbackTestCaseMixin, unittest.TestCase):
    loopbackFunc = staticmethod(loopback.loopbackTCP)


class LoopbackUNIXTestCase(LoopbackTestCaseMixin, unittest.TestCase):
    loopbackFunc = staticmethod(loopback.loopbackUNIX)

    if interfaces.IReactorUNIX(reactor, None) is None:
        skip = "Current reactor does not support UNIX sockets"
