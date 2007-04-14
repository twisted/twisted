# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test case for twisted.protocols.loopback
"""

from zope.interface import implements

from twisted.trial import unittest
from twisted.trial.util import suppress as SUPPRESS
from twisted.protocols import basic, loopback
from twisted.internet import defer
from twisted.internet.protocol import Protocol
from twisted.internet.defer import Deferred, gatherResults
from twisted.internet.interfaces import IAddress, IPushProducer, IPullProducer
from twisted.internet import reactor


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
            self.assertEquals(c.lines, ["THIS IS LINE ONE!"])
            self.assertEquals(len(s.connLost), 1)
            self.assertEquals(len(c.connLost), 1)
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
            self.assertEquals(s.lines, ['Hello 1', 'Hello 2', 'Hello 3'])
            self.assertEquals(c.lines, ['DOOM LINE', 'Hello 1', 'Hello 2', 'Hello 3'])
            self.assertEquals(len(s.connLost), 1)
            self.assertEquals(len(c.connLost), 1)
        d = defer.maybeDeferred(self.loopbackFunc, s, c)
        d.addCallback(check)
        return d



class LoopbackTestCase(LoopbackTestCaseMixin, unittest.TestCase):
    loopbackFunc = staticmethod(loopback.loopback)

    def testRegularFunction(self):
        """
        Suppress loopback deprecation warning.
        """
        return LoopbackTestCaseMixin.testRegularFunction(self)
    testRegularFunction.suppress = [
        SUPPRESS(message="loopback\(\) is deprecated",
                 category=DeprecationWarning)]



class LoopbackAsyncTestCase(LoopbackTestCase):
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


    def test_manyWrites(self):
        """
        Verify that a large number of writes to the transport are handled
        properly with no stack overflows or other issues.
        """
        byte = 'x'
        count = 2 ** 10

        class WriterProtocol(Protocol):
            remaining = count
            succeeded = False

            def __init__(self, finished):
                self.finished = finished

            def connectionMade(self):
                """
                Initialize a tracking buffer and start writing to the peer.
                """
                self.buffer = []
                self.transport.write(byte)

            def dataReceived(self, bytes):
                """
                Record the bytes received and schedule a write to our peer.

                The write doesn't happen synchronously in this function so
                as to trigger the Deferred-using codepath in loopbackAsync. 
                There should probably be another test which covers the
                non-Deferred-using codepath.
                """
                self.buffer.append(bytes)
                self.remaining -= 1
                if self.remaining:
                    reactor.callLater(0, self.transport.write, byte)
                else:
                    self.transport.loseConnection()

            def connectionLost(self, reason):
                self.finished.callback(''.join(self.buffer))


        serverDone = Deferred()
        server = WriterProtocol(serverDone)
        clientDone = Deferred()
        client = WriterProtocol(clientDone)

        def cbConnLost((serverBuffer, clientBuffer)):
            self.assertEqual(serverBuffer, byte * count)
            self.assertEqual(clientBuffer, byte * (count - 1))

        loopback.loopbackAsync(server, client)

        d = gatherResults([serverDone, clientDone])
        d.addCallback(cbConnLost)
        return d


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


class LoopbackTCPTestCase(LoopbackTestCase):
    loopbackFunc = staticmethod(loopback.loopbackTCP)


class LoopbackUNIXTestCase(LoopbackTestCase):
    loopbackFunc = staticmethod(loopback.loopbackUNIX)

    def setUp(self):
        from twisted.internet import reactor, interfaces
        if interfaces.IReactorUNIX(reactor, None) is None:
            raise unittest.SkipTest("Current reactor does not support UNIX sockets")
