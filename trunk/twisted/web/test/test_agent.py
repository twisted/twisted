# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.client.Agent} and related new client APIs.
"""

import cookielib
import zlib
from StringIO import StringIO

from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.web import client, error, http_headers
from twisted.web._newclient import RequestNotSent, RequestTransmissionFailed
from twisted.web._newclient import ResponseNeverReceived, ResponseFailed
from twisted.internet import defer, task
from twisted.python.failure import Failure
from twisted.python.components import proxyForInterface
from twisted.test.proto_helpers import StringTransport
from twisted.test.proto_helpers import MemoryReactor
from twisted.internet.task import Clock
from twisted.internet.error import ConnectionRefusedError, ConnectionDone
from twisted.internet.protocol import Protocol, Factory
from twisted.internet.defer import Deferred, succeed
from twisted.internet.endpoints import TCP4ClientEndpoint, SSL4ClientEndpoint
from twisted.web.client import FileBodyProducer, Request, HTTPConnectionPool
from twisted.web.client import _WebToNormalContextFactory
from twisted.web.client import WebClientContextFactory, _HTTP11ClientFactory
from twisted.web.iweb import UNKNOWN_LENGTH, IBodyProducer, IResponse
from twisted.web._newclient import HTTP11ClientProtocol, Response
from twisted.web.error import SchemeNotSupported

try:
    from twisted.internet import ssl
except:
    ssl = None


class GetBodyProtocol(Protocol):

    def __init__(self, deferred):
        self.deferred = deferred
        self.buf = ''

    def dataReceived(self, bytes):
        self.buf += bytes

    def connectionLost(self, reason):
        self.deferred.callback(self.buf)


def getBody(response):
    d = defer.Deferred()
    response.deliverBody(GetBodyProtocol(d))
    return d



class StubHTTPProtocol(Protocol):
    """
    A protocol like L{HTTP11ClientProtocol} but which does not actually know
    HTTP/1.1 and only collects requests in a list.

    @ivar requests: A C{list} of two-tuples.  Each time a request is made, a
        tuple consisting of the request and the L{Deferred} returned from the
        request method is appended to this list.
    """
    def __init__(self):
        self.requests = []
        self.state = 'QUIESCENT'


    def request(self, request):
        """
        Capture the given request for later inspection.

        @return: A L{Deferred} which this code will never fire.
        """
        result = Deferred()
        self.requests.append((request, result))
        return result



class FileConsumer(object):
    def __init__(self, outputFile):
        self.outputFile = outputFile


    def write(self, bytes):
        self.outputFile.write(bytes)



class FileBodyProducerTests(unittest.TestCase):
    """
    Tests for the L{FileBodyProducer} which reads bytes from a file and writes
    them to an L{IConsumer}.
    """
    def _termination(self):
        """
        This method can be used as the C{terminationPredicateFactory} for a
        L{Cooperator}.  It returns a predicate which immediately returns
        C{False}, indicating that no more work should be done this iteration.
        This has the result of only allowing one iteration of a cooperative
        task to be run per L{Cooperator} iteration.
        """
        return lambda: True


    def setUp(self):
        """
        Create a L{Cooperator} hooked up to an easily controlled, deterministic
        scheduler to use with L{FileBodyProducer}.
        """
        self._scheduled = []
        self.cooperator = task.Cooperator(
            self._termination, self._scheduled.append)


    def test_interface(self):
        """
        L{FileBodyProducer} instances provide L{IBodyProducer}.
        """
        self.assertTrue(verifyObject(
                IBodyProducer, FileBodyProducer(StringIO(""))))


    def test_unknownLength(self):
        """
        If the L{FileBodyProducer} is constructed with a file-like object
        without either a C{seek} or C{tell} method, its C{length} attribute is
        set to C{UNKNOWN_LENGTH}.
        """
        class HasSeek(object):
            def seek(self, offset, whence):
                pass

        class HasTell(object):
            def tell(self):
                pass

        producer = FileBodyProducer(HasSeek())
        self.assertEqual(UNKNOWN_LENGTH, producer.length)
        producer = FileBodyProducer(HasTell())
        self.assertEqual(UNKNOWN_LENGTH, producer.length)


    def test_knownLength(self):
        """
        If the L{FileBodyProducer} is constructed with a file-like object with
        both C{seek} and C{tell} methods, its C{length} attribute is set to the
        size of the file as determined by those methods.
        """
        inputBytes = "here are some bytes"
        inputFile = StringIO(inputBytes)
        inputFile.seek(5)
        producer = FileBodyProducer(inputFile)
        self.assertEqual(len(inputBytes) - 5, producer.length)
        self.assertEqual(inputFile.tell(), 5)


    def test_defaultCooperator(self):
        """
        If no L{Cooperator} instance is passed to L{FileBodyProducer}, the
        global cooperator is used.
        """
        producer = FileBodyProducer(StringIO(""))
        self.assertEqual(task.cooperate, producer._cooperate)


    def test_startProducing(self):
        """
        L{FileBodyProducer.startProducing} starts writing bytes from the input
        file to the given L{IConsumer} and returns a L{Deferred} which fires
        when they have all been written.
        """
        expectedResult = "hello, world"
        readSize = 3
        output = StringIO()
        consumer = FileConsumer(output)
        producer = FileBodyProducer(
            StringIO(expectedResult), self.cooperator, readSize)
        complete = producer.startProducing(consumer)
        for i in range(len(expectedResult) // readSize + 1):
            self._scheduled.pop(0)()
        self.assertEqual([], self._scheduled)
        self.assertEqual(expectedResult, output.getvalue())
        self.assertEqual(None, self.successResultOf(complete))


    def test_inputClosedAtEOF(self):
        """
        When L{FileBodyProducer} reaches end-of-file on the input file given to
        it, the input file is closed.
        """
        readSize = 4
        inputBytes = "some friendly bytes"
        inputFile = StringIO(inputBytes)
        producer = FileBodyProducer(inputFile, self.cooperator, readSize)
        consumer = FileConsumer(StringIO())
        producer.startProducing(consumer)
        for i in range(len(inputBytes) // readSize + 2):
            self._scheduled.pop(0)()
        self.assertTrue(inputFile.closed)


    def test_failedReadWhileProducing(self):
        """
        If a read from the input file fails while producing bytes to the
        consumer, the L{Deferred} returned by
        L{FileBodyProducer.startProducing} fires with a L{Failure} wrapping
        that exception.
        """
        class BrokenFile(object):
            def read(self, count):
                raise IOError("Simulated bad thing")
        producer = FileBodyProducer(BrokenFile(), self.cooperator)
        complete = producer.startProducing(FileConsumer(StringIO()))
        self._scheduled.pop(0)()
        self.failureResultOf(complete).trap(IOError)


    def test_stopProducing(self):
        """
        L{FileBodyProducer.stopProducing} stops the underlying L{IPullProducer}
        and the cooperative task responsible for calling C{resumeProducing} and
        closes the input file but does not cause the L{Deferred} returned by
        C{startProducing} to fire.
        """
        expectedResult = "hello, world"
        readSize = 3
        output = StringIO()
        consumer = FileConsumer(output)
        inputFile = StringIO(expectedResult)
        producer = FileBodyProducer(
            inputFile, self.cooperator, readSize)
        complete = producer.startProducing(consumer)
        producer.stopProducing()
        self.assertTrue(inputFile.closed)
        self._scheduled.pop(0)()
        self.assertEqual("", output.getvalue())
        self.assertNoResult(complete)


    def test_pauseProducing(self):
        """
        L{FileBodyProducer.pauseProducing} temporarily suspends writing bytes
        from the input file to the given L{IConsumer}.
        """
        expectedResult = "hello, world"
        readSize = 5
        output = StringIO()
        consumer = FileConsumer(output)
        producer = FileBodyProducer(
            StringIO(expectedResult), self.cooperator, readSize)
        complete = producer.startProducing(consumer)
        self._scheduled.pop(0)()
        self.assertEqual(output.getvalue(), expectedResult[:5])
        producer.pauseProducing()

        # Sort of depends on an implementation detail of Cooperator: even
        # though the only task is paused, there's still a scheduled call.  If
        # this were to go away because Cooperator became smart enough to cancel
        # this call in this case, that would be fine.
        self._scheduled.pop(0)()

        # Since the producer is paused, no new data should be here.
        self.assertEqual(output.getvalue(), expectedResult[:5])
        self.assertEqual([], self._scheduled)
        self.assertNoResult(complete)


    def test_resumeProducing(self):
        """
        L{FileBodyProducer.resumeProducing} re-commences writing bytes from the
        input file to the given L{IConsumer} after it was previously paused
        with L{FileBodyProducer.pauseProducing}.
        """
        expectedResult = "hello, world"
        readSize = 5
        output = StringIO()
        consumer = FileConsumer(output)
        producer = FileBodyProducer(
            StringIO(expectedResult), self.cooperator, readSize)
        producer.startProducing(consumer)
        self._scheduled.pop(0)()
        self.assertEqual(expectedResult[:readSize], output.getvalue())
        producer.pauseProducing()
        producer.resumeProducing()
        self._scheduled.pop(0)()
        self.assertEqual(expectedResult[:readSize * 2], output.getvalue())



class FakeReactorAndConnectMixin:
    """
    A test mixin providing a testable C{Reactor} class and a dummy C{connect}
    method which allows instances to pretend to be endpoints.
    """

    class Reactor(MemoryReactor, Clock):
        def __init__(self):
            MemoryReactor.__init__(self)
            Clock.__init__(self)


    class StubEndpoint(object):
        """
        Endpoint that wraps existing endpoint, substitutes StubHTTPProtocol, and
        resulting protocol instances are attached to the given test case.
        """

        def __init__(self, endpoint, testCase):
            self.endpoint = endpoint
            self.testCase = testCase
            self.factory = _HTTP11ClientFactory(lambda p: None)
            self.protocol = StubHTTPProtocol()
            self.factory.buildProtocol = lambda addr: self.protocol

        def connect(self, ignoredFactory):
            self.testCase.protocol = self.protocol
            self.endpoint.connect(self.factory)
            return succeed(self.protocol)


    def buildAgentForWrapperTest(self, reactor):
        """
        Return an Agent suitable for use in tests that wrap the Agent and want
        both a fake reactor and StubHTTPProtocol.
        """
        agent = client.Agent(reactor)
        _oldGetEndpoint = agent._getEndpoint
        agent._getEndpoint = lambda *args: (
            self.StubEndpoint(_oldGetEndpoint(*args), self))
        return agent


    def connect(self, factory):
        """
        Fake implementation of an endpoint which synchronously
        succeeds with an instance of L{StubHTTPProtocol} for ease of
        testing.
        """
        protocol = StubHTTPProtocol()
        protocol.makeConnection(None)
        self.protocol = protocol
        return succeed(protocol)



class DummyEndpoint(object):
    """
    An endpoint that uses a fake transport.
    """

    def connect(self, factory):
        protocol = factory.buildProtocol(None)
        protocol.makeConnection(StringTransport())
        return succeed(protocol)



class BadEndpoint(object):
    """
    An endpoint that shouldn't be called.
    """

    def connect(self, factory):
        raise RuntimeError("This endpoint should not have been used.")


class DummyFactory(Factory):
    """
    Create C{StubHTTPProtocol} instances.
    """
    def __init__(self, quiescentCallback):
        pass

    protocol = StubHTTPProtocol



class HTTPConnectionPoolTests(unittest.TestCase, FakeReactorAndConnectMixin):
    """
    Tests for the L{HTTPConnectionPool} class.
    """

    def setUp(self):
        self.fakeReactor = self.Reactor()
        self.pool = HTTPConnectionPool(self.fakeReactor)
        self.pool._factory = DummyFactory
        # The retry code path is tested in HTTPConnectionPoolRetryTests:
        self.pool.retryAutomatically = False


    def test_getReturnsNewIfCacheEmpty(self):
        """
        If there are no cached connections,
        L{HTTPConnectionPool.getConnection} returns a new connection.
        """
        self.assertEqual(self.pool._connections, {})

        def gotConnection(conn):
            self.assertIsInstance(conn, StubHTTPProtocol)
            # The new connection is not stored in the pool:
            self.assertNotIn(conn, self.pool._connections.values())

        unknownKey = 12245
        d = self.pool.getConnection(unknownKey, DummyEndpoint())
        return d.addCallback(gotConnection)


    def test_putStartsTimeout(self):
        """
        If a connection is put back to the pool, a 240-sec timeout is started.

        When the timeout hits, the connection is closed and removed from the
        pool.
        """
        # We start out with one cached connection:
        protocol = StubHTTPProtocol()
        protocol.makeConnection(StringTransport())
        self.pool._putConnection(("http", "example.com", 80), protocol)

        # Connection is in pool, still not closed:
        self.assertEqual(protocol.transport.disconnecting, False)
        self.assertIn(protocol,
                      self.pool._connections[("http", "example.com", 80)])

        # Advance 239 seconds, still not closed:
        self.fakeReactor.advance(239)
        self.assertEqual(protocol.transport.disconnecting, False)
        self.assertIn(protocol,
                      self.pool._connections[("http", "example.com", 80)])
        self.assertIn(protocol, self.pool._timeouts)

        # Advance past 240 seconds, connection will be closed:
        self.fakeReactor.advance(1.1)
        self.assertEqual(protocol.transport.disconnecting, True)
        self.assertNotIn(protocol,
                         self.pool._connections[("http", "example.com", 80)])
        self.assertNotIn(protocol, self.pool._timeouts)


    def test_putExceedsMaxPersistent(self):
        """
        If an idle connection is put back in the cache and the max number of
        persistent connections has been exceeded, one of the connections is
        closed and removed from the cache.
        """
        pool = self.pool

        # We start out with two cached connection, the max:
        origCached = [StubHTTPProtocol(), StubHTTPProtocol()]
        for p in origCached:
            p.makeConnection(StringTransport())
            pool._putConnection(("http", "example.com", 80), p)
        self.assertEqual(pool._connections[("http", "example.com", 80)],
                         origCached)
        timeouts = pool._timeouts.copy()

        # Now we add another one:
        newProtocol = StubHTTPProtocol()
        newProtocol.makeConnection(StringTransport())
        pool._putConnection(("http", "example.com", 80), newProtocol)

        # The oldest cached connections will be removed and disconnected:
        newCached = pool._connections[("http", "example.com", 80)]
        self.assertEqual(len(newCached), 2)
        self.assertEqual(newCached, [origCached[1], newProtocol])
        self.assertEqual([p.transport.disconnecting for p in newCached],
                         [False, False])
        self.assertEqual(origCached[0].transport.disconnecting, True)
        self.assertTrue(timeouts[origCached[0]].cancelled)
        self.assertNotIn(origCached[0], pool._timeouts)


    def test_maxPersistentPerHost(self):
        """
        C{maxPersistentPerHost} is enforced per C{(scheme, host, port)}:
        different keys have different max connections.
        """
        def addProtocol(scheme, host, port):
            p = StubHTTPProtocol()
            p.makeConnection(StringTransport())
            self.pool._putConnection((scheme, host, port), p)
            return p
        persistent = []
        persistent.append(addProtocol("http", "example.com", 80))
        persistent.append(addProtocol("http", "example.com", 80))
        addProtocol("https", "example.com", 443)
        addProtocol("http", "www2.example.com", 80)

        self.assertEqual(
            self.pool._connections[("http", "example.com", 80)], persistent)
        self.assertEqual(
            len(self.pool._connections[("https", "example.com", 443)]), 1)
        self.assertEqual(
            len(self.pool._connections[("http", "www2.example.com", 80)]), 1)


    def test_getCachedConnection(self):
        """
        Getting an address which has a cached connection returns the cached
        connection, removes it from the cache and cancels its timeout.
        """
        # We start out with one cached connection:
        protocol = StubHTTPProtocol()
        protocol.makeConnection(StringTransport())
        self.pool._putConnection(("http", "example.com", 80), protocol)

        def gotConnection(conn):
            # We got the cached connection:
            self.assertIdentical(protocol, conn)
            self.assertNotIn(
                conn, self.pool._connections[("http", "example.com", 80)])
            # And the timeout was cancelled:
            self.fakeReactor.advance(241)
            self.assertEqual(conn.transport.disconnecting, False)
            self.assertNotIn(conn, self.pool._timeouts)

        return self.pool.getConnection(("http", "example.com", 80),
                                       BadEndpoint(),
                                       ).addCallback(gotConnection)


    def test_newConnection(self):
        """
        The pool's C{_newConnection} method constructs a new connection.
        """
        # We start out with one cached connection:
        protocol = StubHTTPProtocol()
        protocol.makeConnection(StringTransport())
        key = 12245
        self.pool._putConnection(key, protocol)

        def gotConnection(newConnection):
            # We got a new connection:
            self.assertNotIdentical(protocol, newConnection)
            # And the old connection is still there:
            self.assertIn(protocol, self.pool._connections[key])
            # While the new connection is not:
            self.assertNotIn(newConnection, self.pool._connections.values())

        d = self.pool._newConnection(key, DummyEndpoint())
        return d.addCallback(gotConnection)


    def test_getSkipsDisconnected(self):
        """
        When getting connections out of the cache, disconnected connections
        are removed and not returned.
        """
        pool = self.pool
        key = ("http", "example.com", 80)

        # We start out with two cached connection, the max:
        origCached = [StubHTTPProtocol(), StubHTTPProtocol()]
        for p in origCached:
            p.makeConnection(StringTransport())
            pool._putConnection(key, p)
        self.assertEqual(pool._connections[key], origCached)

        # We close the first one:
        origCached[0].state = "DISCONNECTED"

        # Now, when we retrive connections we should get the *second* one:
        result = []
        self.pool.getConnection(key,
                                BadEndpoint()).addCallback(result.append)
        self.assertIdentical(result[0], origCached[1])

        # And both the disconnected and removed connections should be out of
        # the cache:
        self.assertEqual(pool._connections[key], [])
        self.assertEqual(pool._timeouts, {})


    def test_putNotQuiescent(self):
        """
        If a non-quiescent connection is put back in the cache, an error is
        logged.
        """
        protocol = StubHTTPProtocol()
        # By default state is QUIESCENT
        self.assertEqual(protocol.state, "QUIESCENT")

        protocol.state = "NOTQUIESCENT"
        self.pool._putConnection(("http", "example.com", 80), protocol)
        exc, = self.flushLoggedErrors(RuntimeError)
        self.assertEqual(
            exc.value.args[0],
            "BUG: Non-quiescent protocol added to connection pool.")
        self.assertIdentical(None, self.pool._connections.get(
                ("http", "example.com", 80)))


    def test_getUsesQuiescentCallback(self):
        """
        When L{HTTPConnectionPool.getConnection} connects, it returns a
        C{Deferred} that fires with an instance of L{HTTP11ClientProtocol}
        that has the correct quiescent callback attached. When this callback
        is called the protocol is returned to the cache correctly, using the
        right key.
        """
        class StringEndpoint(object):
            def connect(self, factory):
                p = factory.buildProtocol(None)
                p.makeConnection(StringTransport())
                return succeed(p)

        pool = HTTPConnectionPool(self.fakeReactor, True)
        pool.retryAutomatically = False
        result = []
        key = "a key"
        pool.getConnection(
            key, StringEndpoint()).addCallback(
            result.append)
        protocol = result[0]
        self.assertIsInstance(protocol, HTTP11ClientProtocol)

        # Now that we have protocol instance, lets try to put it back in the
        # pool:
        protocol._state = "QUIESCENT"
        protocol._quiescentCallback(protocol)

        # If we try to retrive a connection to same destination again, we
        # should get the same protocol, because it should've been added back
        # to the pool:
        result2 = []
        pool.getConnection(
            key, StringEndpoint()).addCallback(
            result2.append)
        self.assertIdentical(result2[0], protocol)


    def test_closeCachedConnections(self):
        """
        L{HTTPConnectionPool.closeCachedConnections} closes all cached
        connections and removes them from the cache. It returns a Deferred
        that fires when they have all lost their connections.
        """
        persistent = []
        def addProtocol(scheme, host, port):
            p = HTTP11ClientProtocol()
            p.makeConnection(StringTransport())
            self.pool._putConnection((scheme, host, port), p)
            persistent.append(p)
        addProtocol("http", "example.com", 80)
        addProtocol("http", "www2.example.com", 80)
        doneDeferred = self.pool.closeCachedConnections()

        # Connections have begun disconnecting:
        for p in persistent:
            self.assertEqual(p.transport.disconnecting, True)
        self.assertEqual(self.pool._connections, {})
        # All timeouts were cancelled and removed:
        for dc in self.fakeReactor.getDelayedCalls():
            self.assertEqual(dc.cancelled, True)
        self.assertEqual(self.pool._timeouts, {})

        # Returned Deferred fires when all connections have been closed:
        result = []
        doneDeferred.addCallback(result.append)
        self.assertEqual(result, [])
        persistent[0].connectionLost(Failure(ConnectionDone()))
        self.assertEqual(result, [])
        persistent[1].connectionLost(Failure(ConnectionDone()))
        self.assertEqual(result, [None])



class AgentTests(unittest.TestCase, FakeReactorAndConnectMixin):
    """
    Tests for the new HTTP client API provided by L{Agent}.
    """
    def setUp(self):
        """
        Create an L{Agent} wrapped around a fake reactor.
        """
        self.reactor = self.Reactor()
        self.agent = client.Agent(self.reactor)


    def completeConnection(self):
        """
        Do whitebox stuff to finish any outstanding connection attempts the
        agent may have initiated.

        This spins the fake reactor clock just enough to get L{ClientCreator},
        which agent is implemented in terms of, to fire its Deferreds.
        """
        self.reactor.advance(0)


    def test_defaultPool(self):
        """
        If no pool is passed in, the L{Agent} creates a non-persistent pool.
        """
        agent = client.Agent(self.reactor)
        self.assertIsInstance(agent._pool, HTTPConnectionPool)
        self.assertEqual(agent._pool.persistent, False)
        self.assertIdentical(agent._reactor, agent._pool._reactor)


    def test_persistent(self):
        """
        If C{persistent} is set to C{True} on the L{HTTPConnectionPool} (the
        default), C{Request}s are created with their C{persistent} flag set to
        C{True}.
        """
        pool = HTTPConnectionPool(self.reactor)
        agent = client.Agent(self.reactor, pool=pool)
        agent._getEndpoint = lambda *args: self
        agent.request("GET", "http://127.0.0.1")
        self.assertEqual(self.protocol.requests[0][0].persistent, True)


    def test_nonPersistent(self):
        """
        If C{persistent} is set to C{False} when creating the
        L{HTTPConnectionPool}, C{Request}s are created with their
        C{persistent} flag set to C{False}.

        Elsewhere in the tests for the underlying HTTP code we ensure that
        this will result in the disconnection of the HTTP protocol once the
        request is done, so that the connection will not be returned to the
        pool.
        """
        pool = HTTPConnectionPool(self.reactor, persistent=False)
        agent = client.Agent(self.reactor, pool=pool)
        agent._getEndpoint = lambda *args: self
        agent.request("GET", "http://127.0.0.1")
        self.assertEqual(self.protocol.requests[0][0].persistent, False)


    def test_connectUsesConnectionPool(self):
        """
        When a connection is made by the Agent, it uses its pool's
        C{getConnection} method to do so, with the endpoint returned by
        C{self._getEndpoint}. The key used is C{(scheme, host, port)}.
        """
        endpoint = DummyEndpoint()
        class MyAgent(client.Agent):
            def _getEndpoint(this, scheme, host, port):
                self.assertEqual((scheme, host, port),
                                 ("http", "foo", 80))
                return endpoint

        class DummyPool(object):
            connected = False
            persistent = False
            def getConnection(this, key, ep):
                this.connected = True
                self.assertEqual(ep, endpoint)
                # This is the key the default Agent uses, others will have
                # different keys:
                self.assertEqual(key, ("http", "foo", 80))
                return defer.succeed(StubHTTPProtocol())

        pool = DummyPool()
        agent = MyAgent(self.reactor, pool=pool)
        self.assertIdentical(pool, agent._pool)

        headers = http_headers.Headers()
        headers.addRawHeader("host", "foo")
        bodyProducer = object()
        agent.request('GET', 'http://foo/',
                      bodyProducer=bodyProducer, headers=headers)
        self.assertEqual(agent._pool.connected, True)


    def test_unsupportedScheme(self):
        """
        L{Agent.request} returns a L{Deferred} which fails with
        L{SchemeNotSupported} if the scheme of the URI passed to it is not
        C{'http'}.
        """
        return self.assertFailure(
            self.agent.request('GET', 'mailto:alice@example.com'),
            SchemeNotSupported)


    def test_connectionFailed(self):
        """
        The L{Deferred} returned by L{Agent.request} fires with a L{Failure} if
        the TCP connection attempt fails.
        """
        result = self.agent.request('GET', 'http://foo/')
        # Cause the connection to be refused
        host, port, factory = self.reactor.tcpClients.pop()[:3]
        factory.clientConnectionFailed(None, Failure(ConnectionRefusedError()))
        self.completeConnection()
        return self.assertFailure(result, ConnectionRefusedError)


    def test_connectHTTP(self):
        """
        L{Agent._getEndpoint} return a C{TCP4ClientEndpoint} when passed a
        scheme of C{'http'}.
        """
        expectedHost = 'example.com'
        expectedPort = 1234
        endpoint = self.agent._getEndpoint('http', expectedHost, expectedPort)
        self.assertEqual(endpoint._host, expectedHost)
        self.assertEqual(endpoint._port, expectedPort)
        self.assertIsInstance(endpoint, TCP4ClientEndpoint)


    def test_connectHTTPS(self):
        """
        L{Agent._getEndpoint} return a C{SSL4ClientEndpoint} when passed a
        scheme of C{'https'}.
        """
        expectedHost = 'example.com'
        expectedPort = 4321
        endpoint = self.agent._getEndpoint('https', expectedHost, expectedPort)
        self.assertIsInstance(endpoint, SSL4ClientEndpoint)
        self.assertEqual(endpoint._host, expectedHost)
        self.assertEqual(endpoint._port, expectedPort)
        self.assertIsInstance(endpoint._sslContextFactory,
                              _WebToNormalContextFactory)
        # Default context factory was used:
        self.assertIsInstance(endpoint._sslContextFactory._webContext,
                              WebClientContextFactory)
    if ssl is None:
        test_connectHTTPS.skip = "OpenSSL not present"


    def test_connectHTTPSCustomContextFactory(self):
        """
        If a context factory is passed to L{Agent.__init__} it will be used to
        determine the SSL parameters for HTTPS requests.  When an HTTPS request
        is made, the hostname and port number of the request URL will be passed
        to the context factory's C{getContext} method.  The resulting context
        object will be used to establish the SSL connection.
        """
        expectedHost = 'example.org'
        expectedPort = 20443
        expectedContext = object()

        contextArgs = []
        class StubWebContextFactory(object):
            def getContext(self, hostname, port):
                contextArgs.append((hostname, port))
                return expectedContext

        agent = client.Agent(self.reactor, StubWebContextFactory())
        endpoint = agent._getEndpoint('https', expectedHost, expectedPort)
        contextFactory = endpoint._sslContextFactory
        context = contextFactory.getContext()
        self.assertEqual(context, expectedContext)
        self.assertEqual(contextArgs, [(expectedHost, expectedPort)])


    def test_hostProvided(self):
        """
        If C{None} is passed to L{Agent.request} for the C{headers} parameter,
        a L{Headers} instance is created for the request and a I{Host} header
        added to it.
        """
        self.agent._getEndpoint = lambda *args: self
        self.agent.request(
            'GET', 'http://example.com/foo?bar')

        req, res = self.protocol.requests.pop()
        self.assertEqual(req.headers.getRawHeaders('host'), ['example.com'])


    def test_hostOverride(self):
        """
        If the headers passed to L{Agent.request} includes a value for the
        I{Host} header, that value takes precedence over the one which would
        otherwise be automatically provided.
        """
        headers = http_headers.Headers({'foo': ['bar'], 'host': ['quux']})
        self.agent._getEndpoint = lambda *args: self
        self.agent.request(
            'GET', 'http://example.com/foo?bar', headers)

        req, res = self.protocol.requests.pop()
        self.assertEqual(req.headers.getRawHeaders('host'), ['quux'])


    def test_headersUnmodified(self):
        """
        If a I{Host} header must be added to the request, the L{Headers}
        instance passed to L{Agent.request} is not modified.
        """
        headers = http_headers.Headers()
        self.agent._getEndpoint = lambda *args: self
        self.agent.request(
            'GET', 'http://example.com/foo', headers)

        protocol = self.protocol

        # The request should have been issued.
        self.assertEqual(len(protocol.requests), 1)
        # And the headers object passed in should not have changed.
        self.assertEqual(headers, http_headers.Headers())


    def test_hostValueStandardHTTP(self):
        """
        When passed a scheme of C{'http'} and a port of C{80},
        L{Agent._computeHostValue} returns a string giving just
        the host name passed to it.
        """
        self.assertEqual(
            self.agent._computeHostValue('http', 'example.com', 80),
            'example.com')


    def test_hostValueNonStandardHTTP(self):
        """
        When passed a scheme of C{'http'} and a port other than C{80},
        L{Agent._computeHostValue} returns a string giving the
        host passed to it joined together with the port number by C{":"}.
        """
        self.assertEqual(
            self.agent._computeHostValue('http', 'example.com', 54321),
            'example.com:54321')


    def test_hostValueStandardHTTPS(self):
        """
        When passed a scheme of C{'https'} and a port of C{443},
        L{Agent._computeHostValue} returns a string giving just
        the host name passed to it.
        """
        self.assertEqual(
            self.agent._computeHostValue('https', 'example.com', 443),
            'example.com')


    def test_hostValueNonStandardHTTPS(self):
        """
        When passed a scheme of C{'https'} and a port other than C{443},
        L{Agent._computeHostValue} returns a string giving the
        host passed to it joined together with the port number by C{":"}.
        """
        self.assertEqual(
            self.agent._computeHostValue('https', 'example.com', 54321),
            'example.com:54321')


    def test_request(self):
        """
        L{Agent.request} establishes a new connection to the host indicated by
        the host part of the URI passed to it and issues a request using the
        method, the path portion of the URI, the headers, and the body producer
        passed to it.  It returns a L{Deferred} which fires with an
        L{IResponse} from the server.
        """
        self.agent._getEndpoint = lambda *args: self

        headers = http_headers.Headers({'foo': ['bar']})
        # Just going to check the body for identity, so it doesn't need to be
        # real.
        body = object()
        self.agent.request(
            'GET', 'http://example.com:1234/foo?bar', headers, body)

        protocol = self.protocol

        # The request should be issued.
        self.assertEqual(len(protocol.requests), 1)
        req, res = protocol.requests.pop()
        self.assertIsInstance(req, Request)
        self.assertEqual(req.method, 'GET')
        self.assertEqual(req.uri, '/foo?bar')
        self.assertEqual(
            req.headers,
            http_headers.Headers({'foo': ['bar'],
                                  'host': ['example.com:1234']}))
        self.assertIdentical(req.bodyProducer, body)


    def test_connectTimeout(self):
        """
        L{Agent} takes a C{connectTimeout} argument which is forwarded to the
        following C{connectTCP} agent.
        """
        agent = client.Agent(self.reactor, connectTimeout=5)
        agent.request('GET', 'http://foo/')
        timeout = self.reactor.tcpClients.pop()[3]
        self.assertEqual(5, timeout)


    def test_connectSSLTimeout(self):
        """
        L{Agent} takes a C{connectTimeout} argument which is forwarded to the
        following C{connectSSL} call.
        """
        agent = client.Agent(self.reactor, connectTimeout=5)
        agent.request('GET', 'https://foo/')
        timeout = self.reactor.sslClients.pop()[4]
        self.assertEqual(5, timeout)


    def test_bindAddress(self):
        """
        L{Agent} takes a C{bindAddress} argument which is forwarded to the
        following C{connectTCP} call.
        """
        agent = client.Agent(self.reactor, bindAddress='192.168.0.1')
        agent.request('GET', 'http://foo/')
        address = self.reactor.tcpClients.pop()[4]
        self.assertEqual('192.168.0.1', address)


    def test_bindAddressSSL(self):
        """
        L{Agent} takes a C{bindAddress} argument which is forwarded to the
        following C{connectSSL} call.
        """
        agent = client.Agent(self.reactor, bindAddress='192.168.0.1')
        agent.request('GET', 'https://foo/')
        address = self.reactor.sslClients.pop()[5]
        self.assertEqual('192.168.0.1', address)



class HTTPConnectionPoolRetryTests(unittest.TestCase, FakeReactorAndConnectMixin):
    """
    L{client.HTTPConnectionPool}, by using
    L{client._RetryingHTTP11ClientProtocol}, supports retrying requests done
    against previously cached connections.
    """

    def test_onlyRetryIdempotentMethods(self):
        """
        Only GET, HEAD, OPTIONS, TRACE, DELETE methods should cause a retry.
        """
        pool = client.HTTPConnectionPool(None)
        connection = client._RetryingHTTP11ClientProtocol(None, pool)
        self.assertTrue(connection._shouldRetry("GET", RequestNotSent(), None))
        self.assertTrue(connection._shouldRetry("HEAD", RequestNotSent(), None))
        self.assertTrue(connection._shouldRetry(
                "OPTIONS", RequestNotSent(), None))
        self.assertTrue(connection._shouldRetry(
                "TRACE", RequestNotSent(), None))
        self.assertTrue(connection._shouldRetry(
                "DELETE", RequestNotSent(), None))
        self.assertFalse(connection._shouldRetry(
                "POST", RequestNotSent(), None))
        self.assertFalse(connection._shouldRetry(
                "MYMETHOD", RequestNotSent(), None))
        # This will be covered by a different ticket, since we need support
        #for resettable body producers:
        # self.assertTrue(connection._doRetry("PUT", RequestNotSent(), None))


    def test_onlyRetryIfNoResponseReceived(self):
        """
        Only L{RequestNotSent}, L{RequestTransmissionFailed} and
        L{ResponseNeverReceived} exceptions should be a cause for retrying.
        """
        pool = client.HTTPConnectionPool(None)
        connection = client._RetryingHTTP11ClientProtocol(None, pool)
        self.assertTrue(connection._shouldRetry("GET", RequestNotSent(), None))
        self.assertTrue(connection._shouldRetry(
                "GET", RequestTransmissionFailed([]), None))
        self.assertTrue(connection._shouldRetry(
                "GET", ResponseNeverReceived([]),None))
        self.assertFalse(connection._shouldRetry(
                "GET", ResponseFailed([]), None))
        self.assertFalse(connection._shouldRetry(
                "GET", ConnectionRefusedError(), None))


    def test_wrappedOnPersistentReturned(self):
        """
        If L{client.HTTPConnectionPool.getConnection} returns a previously
        cached connection, it will get wrapped in a
        L{client._RetryingHTTP11ClientProtocol}.
        """
        pool = client.HTTPConnectionPool(Clock())

        # Add a connection to the cache:
        protocol = StubHTTPProtocol()
        protocol.makeConnection(StringTransport())
        pool._putConnection(123, protocol)

        # Retrieve it, it should come back wrapped in a
        # _RetryingHTTP11ClientProtocol:
        d = pool.getConnection(123, DummyEndpoint())

        def gotConnection(connection):
            self.assertIsInstance(connection,
                                  client._RetryingHTTP11ClientProtocol)
            self.assertIdentical(connection._clientProtocol, protocol)
        return d.addCallback(gotConnection)


    def test_notWrappedOnNewReturned(self):
        """
        If L{client.HTTPConnectionPool.getConnection} returns a new
        connection, it will be returned as is.
        """
        pool = client.HTTPConnectionPool(None)
        d = pool.getConnection(123, DummyEndpoint())

        def gotConnection(connection):
            # Don't want to use isinstance since potentially the wrapper might
            # subclass it at some point:
            self.assertIdentical(connection.__class__, HTTP11ClientProtocol)
        return d.addCallback(gotConnection)


    def retryAttempt(self, willWeRetry):
        """
        Fail a first request, possibly retrying depending on argument.
        """
        protocols = []
        def newProtocol():
            protocol = StubHTTPProtocol()
            protocols.append(protocol)
            return defer.succeed(protocol)

        bodyProducer = object()
        request = client.Request("FOO", "/", client.Headers(), bodyProducer,
                                 persistent=True)
        newProtocol()
        protocol = protocols[0]
        retrier = client._RetryingHTTP11ClientProtocol(protocol, newProtocol)

        def _shouldRetry(m, e, bp):
            self.assertEqual(m, "FOO")
            self.assertIdentical(bp, bodyProducer)
            self.assertIsInstance(e, (RequestNotSent, ResponseNeverReceived))
            return willWeRetry
        retrier._shouldRetry = _shouldRetry

        d = retrier.request(request)

        # So far, one request made:
        self.assertEqual(len(protocols), 1)
        self.assertEqual(len(protocols[0].requests), 1)

        # Fail the first request:
        protocol.requests[0][1].errback(RequestNotSent())
        return d, protocols


    def test_retryIfShouldRetryReturnsTrue(self):
        """
        L{client._RetryingHTTP11ClientProtocol} retries when
        L{client._RetryingHTTP11ClientProtocol._shouldRetry} returns C{True}.
        """
        d, protocols = self.retryAttempt(True)
        # We retried!
        self.assertEqual(len(protocols), 2)
        response = object()
        protocols[1].requests[0][1].callback(response)
        return d.addCallback(self.assertIdentical, response)


    def test_dontRetryIfShouldRetryReturnsFalse(self):
        """
        L{client._RetryingHTTP11ClientProtocol} does not retry when
        L{client._RetryingHTTP11ClientProtocol._shouldRetry} returns C{False}.
        """
        d, protocols = self.retryAttempt(False)
        # We did not retry:
        self.assertEqual(len(protocols), 1)
        return self.assertFailure(d, RequestNotSent)


    def test_onlyRetryWithoutBody(self):
        """
        L{_RetryingHTTP11ClientProtocol} only retries queries that don't have
        a body.

        This is an implementation restriction; if the restriction is fixed,
        this test should be removed and PUT added to list of methods that
        support retries.
        """
        pool = client.HTTPConnectionPool(None)
        connection = client._RetryingHTTP11ClientProtocol(None, pool)
        self.assertTrue(connection._shouldRetry("GET", RequestNotSent(), None))
        self.assertFalse(connection._shouldRetry("GET", RequestNotSent(), object()))


    def test_onlyRetryOnce(self):
        """
        If a L{client._RetryingHTTP11ClientProtocol} fails more than once on
        an idempotent query before a response is received, it will not retry.
        """
        d, protocols = self.retryAttempt(True)
        self.assertEqual(len(protocols), 2)
        # Fail the second request too:
        protocols[1].requests[0][1].errback(ResponseNeverReceived([]))
        # We didn't retry again:
        self.assertEqual(len(protocols), 2)
        return self.assertFailure(d, ResponseNeverReceived)


    def test_dontRetryIfRetryAutomaticallyFalse(self):
        """
        If L{HTTPConnectionPool.retryAutomatically} is set to C{False}, don't
        wrap connections with retrying logic.
        """
        pool = client.HTTPConnectionPool(Clock())
        pool.retryAutomatically = False

        # Add a connection to the cache:
        protocol = StubHTTPProtocol()
        protocol.makeConnection(StringTransport())
        pool._putConnection(123, protocol)

        # Retrieve it, it should come back unwrapped:
        d = pool.getConnection(123, DummyEndpoint())

        def gotConnection(connection):
            self.assertIdentical(connection, protocol)
        return d.addCallback(gotConnection)


    def test_retryWithNewConnection(self):
        """
        L{client.HTTPConnectionPool} creates
        {client._RetryingHTTP11ClientProtocol} with a new connection factory
        method that creates a new connection using the same key and endpoint
        as the wrapped connection.
        """
        pool = client.HTTPConnectionPool(Clock())
        key = 123
        endpoint = DummyEndpoint()
        newConnections = []

        # Override the pool's _newConnection:
        def newConnection(k, e):
            newConnections.append((k, e))
        pool._newConnection = newConnection

        # Add a connection to the cache:
        protocol = StubHTTPProtocol()
        protocol.makeConnection(StringTransport())
        pool._putConnection(key, protocol)

        # Retrieve it, it should come back wrapped in a
        # _RetryingHTTP11ClientProtocol:
        d = pool.getConnection(key, endpoint)

        def gotConnection(connection):
            self.assertIsInstance(connection,
                                  client._RetryingHTTP11ClientProtocol)
            self.assertIdentical(connection._clientProtocol, protocol)
            # Verify that the _newConnection method on retrying connection
            # calls _newConnection on the pool:
            self.assertEqual(newConnections, [])
            connection._newConnection()
            self.assertEqual(len(newConnections), 1)
            self.assertEqual(newConnections[0][0], key)
            self.assertIdentical(newConnections[0][1], endpoint)
        return d.addCallback(gotConnection)




class CookieTestsMixin(object):
    """
    Mixin for unit tests dealing with cookies.
    """
    def addCookies(self, cookieJar, uri, cookies):
        """
        Add a cookie to a cookie jar.
        """
        response = client._FakeUrllib2Response(
            client.Response(
                ('HTTP', 1, 1),
                200,
                'OK',
                client.Headers({'Set-Cookie': cookies}),
                None))
        request = client._FakeUrllib2Request(uri)
        cookieJar.extract_cookies(response, request)
        return request, response



class CookieJarTests(unittest.TestCase, CookieTestsMixin):
    """
    Tests for L{twisted.web.client._FakeUrllib2Response} and
    L{twisted.web.client._FakeUrllib2Request}'s interactions with
    C{cookielib.CookieJar} instances.
    """
    def makeCookieJar(self):
        """
        Create a C{cookielib.CookieJar} with some sample cookies.
        """
        cookieJar = cookielib.CookieJar()
        reqres = self.addCookies(
            cookieJar,
            'http://example.com:1234/foo?bar',
            ['foo=1; cow=moo; Path=/foo; Comment=hello',
             'bar=2; Comment=goodbye'])
        return cookieJar, reqres


    def test_extractCookies(self):
        """
        L{cookielib.CookieJar.extract_cookies} extracts cookie information from
        fake urllib2 response instances.
        """
        jar = self.makeCookieJar()[0]
        cookies = dict([(c.name, c) for c in jar])

        cookie = cookies['foo']
        self.assertEqual(cookie.version, 0)
        self.assertEqual(cookie.name, 'foo')
        self.assertEqual(cookie.value, '1')
        self.assertEqual(cookie.path, '/foo')
        self.assertEqual(cookie.comment, 'hello')
        self.assertEqual(cookie.get_nonstandard_attr('cow'), 'moo')

        cookie = cookies['bar']
        self.assertEqual(cookie.version, 0)
        self.assertEqual(cookie.name, 'bar')
        self.assertEqual(cookie.value, '2')
        self.assertEqual(cookie.path, '/')
        self.assertEqual(cookie.comment, 'goodbye')
        self.assertIdentical(cookie.get_nonstandard_attr('cow'), None)


    def test_sendCookie(self):
        """
        L{cookielib.CookieJar.add_cookie_header} adds a cookie header to a fake
        urllib2 request instance.
        """
        jar, (request, response) = self.makeCookieJar()

        self.assertIdentical(
            request.get_header('Cookie', None),
            None)

        jar.add_cookie_header(request)
        self.assertEqual(
            request.get_header('Cookie', None),
            'foo=1; bar=2')



class CookieAgentTests(unittest.TestCase, CookieTestsMixin,
                       FakeReactorAndConnectMixin):
    """
    Tests for L{twisted.web.client.CookieAgent}.
    """
    def setUp(self):
        self.reactor = self.Reactor()


    def test_emptyCookieJarRequest(self):
        """
        L{CookieAgent.request} does not insert any C{'Cookie'} header into the
        L{Request} object if there is no cookie in the cookie jar for the URI
        being requested. Cookies are extracted from the response and stored in
        the cookie jar.
        """
        cookieJar = cookielib.CookieJar()
        self.assertEqual(list(cookieJar), [])

        agent = self.buildAgentForWrapperTest(self.reactor)
        cookieAgent = client.CookieAgent(agent, cookieJar)
        d = cookieAgent.request(
            'GET', 'http://example.com:1234/foo?bar')

        def _checkCookie(ignored):
            cookies = list(cookieJar)
            self.assertEqual(len(cookies), 1)
            self.assertEqual(cookies[0].name, 'foo')
            self.assertEqual(cookies[0].value, '1')

        d.addCallback(_checkCookie)

        req, res = self.protocol.requests.pop()
        self.assertIdentical(req.headers.getRawHeaders('cookie'), None)

        resp = client.Response(
            ('HTTP', 1, 1),
            200,
            'OK',
            client.Headers({'Set-Cookie': ['foo=1',]}),
            None)
        res.callback(resp)

        return d


    def test_requestWithCookie(self):
        """
        L{CookieAgent.request} inserts a C{'Cookie'} header into the L{Request}
        object when there is a cookie matching the request URI in the cookie
        jar.
        """
        uri = 'http://example.com:1234/foo?bar'
        cookie = 'foo=1'

        cookieJar = cookielib.CookieJar()
        self.addCookies(cookieJar, uri, [cookie])
        self.assertEqual(len(list(cookieJar)), 1)

        agent = self.buildAgentForWrapperTest(self.reactor)
        cookieAgent = client.CookieAgent(agent, cookieJar)
        cookieAgent.request('GET', uri)

        req, res = self.protocol.requests.pop()
        self.assertEqual(req.headers.getRawHeaders('cookie'), [cookie])


    def test_secureCookie(self):
        """
        L{CookieAgent} is able to handle secure cookies, ie cookies which
        should only be handled over https.
        """
        uri = 'https://example.com:1234/foo?bar'
        cookie = 'foo=1;secure'

        cookieJar = cookielib.CookieJar()
        self.addCookies(cookieJar, uri, [cookie])
        self.assertEqual(len(list(cookieJar)), 1)

        agent = self.buildAgentForWrapperTest(self.reactor)
        cookieAgent = client.CookieAgent(agent, cookieJar)
        cookieAgent.request('GET', uri)

        req, res = self.protocol.requests.pop()
        self.assertEqual(req.headers.getRawHeaders('cookie'), ['foo=1'])


    def test_secureCookieOnInsecureConnection(self):
        """
        If a cookie is setup as secure, it won't be sent with the request if
        it's not over HTTPS.
        """
        uri = 'http://example.com/foo?bar'
        cookie = 'foo=1;secure'

        cookieJar = cookielib.CookieJar()
        self.addCookies(cookieJar, uri, [cookie])
        self.assertEqual(len(list(cookieJar)), 1)

        agent = self.buildAgentForWrapperTest(self.reactor)
        cookieAgent = client.CookieAgent(agent, cookieJar)
        cookieAgent.request('GET', uri)

        req, res = self.protocol.requests.pop()
        self.assertIdentical(None, req.headers.getRawHeaders('cookie'))


    def test_portCookie(self):
        """
        L{CookieAgent} supports cookies which enforces the port number they
        need to be transferred upon.
        """
        uri = 'https://example.com:1234/foo?bar'
        cookie = 'foo=1;port=1234'

        cookieJar = cookielib.CookieJar()
        self.addCookies(cookieJar, uri, [cookie])
        self.assertEqual(len(list(cookieJar)), 1)

        agent = self.buildAgentForWrapperTest(self.reactor)
        cookieAgent = client.CookieAgent(agent, cookieJar)
        cookieAgent.request('GET', uri)

        req, res = self.protocol.requests.pop()
        self.assertEqual(req.headers.getRawHeaders('cookie'), ['foo=1'])


    def test_portCookieOnWrongPort(self):
        """
        When creating a cookie with a port directive, it won't be added to the
        L{cookie.CookieJar} if the URI is on a different port.
        """
        uri = 'https://example.com:4567/foo?bar'
        cookie = 'foo=1;port=1234'

        cookieJar = cookielib.CookieJar()
        self.addCookies(cookieJar, uri, [cookie])
        self.assertEqual(len(list(cookieJar)), 0)



class Decoder1(proxyForInterface(IResponse)):
    """
    A test decoder to be used by L{client.ContentDecoderAgent} tests.
    """



class Decoder2(Decoder1):
    """
    A test decoder to be used by L{client.ContentDecoderAgent} tests.
    """



class ContentDecoderAgentTests(unittest.TestCase, FakeReactorAndConnectMixin):
    """
    Tests for L{client.ContentDecoderAgent}.
    """

    def setUp(self):
        """
        Create an L{Agent} wrapped around a fake reactor.
        """
        self.reactor = self.Reactor()
        self.agent = self.buildAgentForWrapperTest(self.reactor)


    def test_acceptHeaders(self):
        """
        L{client.ContentDecoderAgent} sets the I{Accept-Encoding} header to the
        names of the available decoder objects.
        """
        agent = client.ContentDecoderAgent(
            self.agent, [('decoder1', Decoder1), ('decoder2', Decoder2)])

        agent.request('GET', 'http://example.com/foo')

        protocol = self.protocol

        self.assertEqual(len(protocol.requests), 1)
        req, res = protocol.requests.pop()
        self.assertEqual(req.headers.getRawHeaders('accept-encoding'),
                          ['decoder1,decoder2'])


    def test_existingHeaders(self):
        """
        If there are existing I{Accept-Encoding} fields,
        L{client.ContentDecoderAgent} creates a new field for the decoders it
        knows about.
        """
        headers = http_headers.Headers({'foo': ['bar'],
                                        'accept-encoding': ['fizz']})
        agent = client.ContentDecoderAgent(
            self.agent, [('decoder1', Decoder1), ('decoder2', Decoder2)])
        agent.request('GET', 'http://example.com/foo', headers=headers)

        protocol = self.protocol

        self.assertEqual(len(protocol.requests), 1)
        req, res = protocol.requests.pop()
        self.assertEqual(
            list(req.headers.getAllRawHeaders()),
            [('Host', ['example.com']),
             ('Foo', ['bar']),
             ('Accept-Encoding', ['fizz', 'decoder1,decoder2'])])


    def test_plainEncodingResponse(self):
        """
        If the response is not encoded despited the request I{Accept-Encoding}
        headers, L{client.ContentDecoderAgent} simply forwards the response.
        """
        agent = client.ContentDecoderAgent(
            self.agent, [('decoder1', Decoder1), ('decoder2', Decoder2)])
        deferred = agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        response = Response(('HTTP', 1, 1), 200, 'OK', http_headers.Headers(),
                            None)
        res.callback(response)

        return deferred.addCallback(self.assertIdentical, response)


    def test_unsupportedEncoding(self):
        """
        If an encoding unknown to the L{client.ContentDecoderAgent} is found,
        the response is unchanged.
        """
        agent = client.ContentDecoderAgent(
            self.agent, [('decoder1', Decoder1), ('decoder2', Decoder2)])
        deferred = agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers({'foo': ['bar'],
                                        'content-encoding': ['fizz']})
        response = Response(('HTTP', 1, 1), 200, 'OK', headers, None)
        res.callback(response)

        return deferred.addCallback(self.assertIdentical, response)


    def test_unknownEncoding(self):
        """
        When L{client.ContentDecoderAgent} encounters a decoder it doesn't know
        about, it stops decoding even if another encoding is known afterwards.
        """
        agent = client.ContentDecoderAgent(
            self.agent, [('decoder1', Decoder1), ('decoder2', Decoder2)])
        deferred = agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers({'foo': ['bar'],
                                        'content-encoding':
                                        ['decoder1,fizz,decoder2']})
        response = Response(('HTTP', 1, 1), 200, 'OK', headers, None)
        res.callback(response)

        def check(result):
            self.assertNotIdentical(response, result)
            self.assertIsInstance(result, Decoder2)
            self.assertEqual(['decoder1,fizz'],
                              result.headers.getRawHeaders('content-encoding'))

        return deferred.addCallback(check)



class SimpleAgentProtocol(Protocol):
    """
    A L{Protocol} to be used with an L{client.Agent} to receive data.

    @ivar finished: L{Deferred} firing when C{connectionLost} is called.

    @ivar made: L{Deferred} firing when C{connectionMade} is called.

    @ivar received: C{list} of received data.
    """

    def __init__(self):
        self.made = Deferred()
        self.finished = Deferred()
        self.received = []


    def connectionMade(self):
        self.made.callback(None)


    def connectionLost(self, reason):
        self.finished.callback(None)


    def dataReceived(self, data):
        self.received.append(data)



class ContentDecoderAgentWithGzipTests(unittest.TestCase,
                                       FakeReactorAndConnectMixin):

    def setUp(self):
        """
        Create an L{Agent} wrapped around a fake reactor.
        """
        self.reactor = self.Reactor()
        agent = self.buildAgentForWrapperTest(self.reactor)
        self.agent = client.ContentDecoderAgent(
            agent, [("gzip", client.GzipDecoder)])


    def test_gzipEncodingResponse(self):
        """
        If the response has a C{gzip} I{Content-Encoding} header,
        L{GzipDecoder} wraps the response to return uncompressed data to the
        user.
        """
        deferred = self.agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers({'foo': ['bar'],
                                        'content-encoding': ['gzip']})
        transport = StringTransport()
        response = Response(('HTTP', 1, 1), 200, 'OK', headers, transport)
        response.length = 12
        res.callback(response)

        compressor = zlib.compressobj(2, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
        data = (compressor.compress('x' * 6) + compressor.compress('y' * 4) +
                compressor.flush())

        def checkResponse(result):
            self.assertNotIdentical(result, response)
            self.assertEqual(result.version, ('HTTP', 1, 1))
            self.assertEqual(result.code, 200)
            self.assertEqual(result.phrase, 'OK')
            self.assertEqual(list(result.headers.getAllRawHeaders()),
                              [('Foo', ['bar'])])
            self.assertEqual(result.length, UNKNOWN_LENGTH)
            self.assertRaises(AttributeError, getattr, result, 'unknown')

            response._bodyDataReceived(data[:5])
            response._bodyDataReceived(data[5:])
            response._bodyDataFinished()

            protocol = SimpleAgentProtocol()
            result.deliverBody(protocol)

            self.assertEqual(protocol.received, ['x' * 6 + 'y' * 4])
            return defer.gatherResults([protocol.made, protocol.finished])

        deferred.addCallback(checkResponse)

        return deferred


    def test_brokenContent(self):
        """
        If the data received by the L{GzipDecoder} isn't valid gzip-compressed
        data, the call to C{deliverBody} fails with a C{zlib.error}.
        """
        deferred = self.agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers({'foo': ['bar'],
                                        'content-encoding': ['gzip']})
        transport = StringTransport()
        response = Response(('HTTP', 1, 1), 200, 'OK', headers, transport)
        response.length = 12
        res.callback(response)

        data = "not gzipped content"

        def checkResponse(result):
            response._bodyDataReceived(data)

            result.deliverBody(Protocol())

        deferred.addCallback(checkResponse)
        self.assertFailure(deferred, client.ResponseFailed)

        def checkFailure(error):
            error.reasons[0].trap(zlib.error)
            self.assertIsInstance(error.response, Response)

        return deferred.addCallback(checkFailure)


    def test_flushData(self):
        """
        When the connection with the server is lost, the gzip protocol calls
        C{flush} on the zlib decompressor object to get uncompressed data which
        may have been buffered.
        """
        class decompressobj(object):

            def __init__(self, wbits):
                pass

            def decompress(self, data):
                return 'x'

            def flush(self):
                return 'y'


        oldDecompressObj = zlib.decompressobj
        zlib.decompressobj = decompressobj
        self.addCleanup(setattr, zlib, 'decompressobj', oldDecompressObj)

        deferred = self.agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers({'content-encoding': ['gzip']})
        transport = StringTransport()
        response = Response(('HTTP', 1, 1), 200, 'OK', headers, transport)
        res.callback(response)

        def checkResponse(result):
            response._bodyDataReceived('data')
            response._bodyDataFinished()

            protocol = SimpleAgentProtocol()
            result.deliverBody(protocol)

            self.assertEqual(protocol.received, ['x', 'y'])
            return defer.gatherResults([protocol.made, protocol.finished])

        deferred.addCallback(checkResponse)

        return deferred


    def test_flushError(self):
        """
        If the C{flush} call in C{connectionLost} fails, the C{zlib.error}
        exception is caught and turned into a L{ResponseFailed}.
        """
        class decompressobj(object):

            def __init__(self, wbits):
                pass

            def decompress(self, data):
                return 'x'

            def flush(self):
                raise zlib.error()


        oldDecompressObj = zlib.decompressobj
        zlib.decompressobj = decompressobj
        self.addCleanup(setattr, zlib, 'decompressobj', oldDecompressObj)

        deferred = self.agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers({'content-encoding': ['gzip']})
        transport = StringTransport()
        response = Response(('HTTP', 1, 1), 200, 'OK', headers, transport)
        res.callback(response)

        def checkResponse(result):
            response._bodyDataReceived('data')
            response._bodyDataFinished()

            protocol = SimpleAgentProtocol()
            result.deliverBody(protocol)

            self.assertEqual(protocol.received, ['x', 'y'])
            return defer.gatherResults([protocol.made, protocol.finished])

        deferred.addCallback(checkResponse)

        self.assertFailure(deferred, client.ResponseFailed)

        def checkFailure(error):
            error.reasons[1].trap(zlib.error)
            self.assertIsInstance(error.response, Response)

        return deferred.addCallback(checkFailure)



class ProxyAgentTests(unittest.TestCase, FakeReactorAndConnectMixin):
    """
    Tests for L{client.ProxyAgent}.
    """

    def setUp(self):
        self.reactor = self.Reactor()
        self.agent = client.ProxyAgent(
            TCP4ClientEndpoint(self.reactor, "bar", 5678), self.reactor)
        oldEndpoint = self.agent._proxyEndpoint
        self.agent._proxyEndpoint = self.StubEndpoint(oldEndpoint, self)


    def test_proxyRequest(self):
        """
        L{client.ProxyAgent} issues an HTTP request against the proxy, with the
        full URI as path, when C{request} is called.
        """
        headers = http_headers.Headers({'foo': ['bar']})
        # Just going to check the body for identity, so it doesn't need to be
        # real.
        body = object()
        self.agent.request(
            'GET', 'http://example.com:1234/foo?bar', headers, body)

        host, port, factory = self.reactor.tcpClients.pop()[:3]
        self.assertEqual(host, "bar")
        self.assertEqual(port, 5678)

        self.assertIsInstance(factory._wrappedFactory,
                              client._HTTP11ClientFactory)

        protocol = self.protocol

        # The request should be issued.
        self.assertEqual(len(protocol.requests), 1)
        req, res = protocol.requests.pop()
        self.assertIsInstance(req, Request)
        self.assertEqual(req.method, 'GET')
        self.assertEqual(req.uri, 'http://example.com:1234/foo?bar')
        self.assertEqual(
            req.headers,
            http_headers.Headers({'foo': ['bar'],
                                  'host': ['example.com:1234']}))
        self.assertIdentical(req.bodyProducer, body)


    def test_nonPersistent(self):
        """
        C{ProxyAgent} connections are not persistent by default.
        """
        self.assertEqual(self.agent._pool.persistent, False)


    def test_connectUsesConnectionPool(self):
        """
        When a connection is made by the C{ProxyAgent}, it uses its pool's
        C{getConnection} method to do so, with the endpoint it was constructed
        with and a key of C{("http-proxy", endpoint)}.
        """
        endpoint = DummyEndpoint()
        class DummyPool(object):
            connected = False
            persistent = False
            def getConnection(this, key, ep):
                this.connected = True
                self.assertIdentical(ep, endpoint)
                # The key is *not* tied to the final destination, but only to
                # the address of the proxy, since that's where *we* are
                # connecting:
                self.assertEqual(key, ("http-proxy", endpoint))
                return defer.succeed(StubHTTPProtocol())

        pool = DummyPool()
        agent = client.ProxyAgent(endpoint, self.reactor, pool=pool)
        self.assertIdentical(pool, agent._pool)

        agent.request('GET', 'http://foo/')
        self.assertEqual(agent._pool.connected, True)



class RedirectAgentTests(unittest.TestCase, FakeReactorAndConnectMixin):
    """
    Tests for L{client.RedirectAgent}.
    """

    def setUp(self):
        self.reactor = self.Reactor()
        self.agent = client.RedirectAgent(
            self.buildAgentForWrapperTest(self.reactor))


    def test_noRedirect(self):
        """
        L{client.RedirectAgent} behaves like L{client.Agent} if the response
        doesn't contain a redirect.
        """
        deferred = self.agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers()
        response = Response(('HTTP', 1, 1), 200, 'OK', headers, None)
        res.callback(response)

        self.assertEqual(0, len(self.protocol.requests))

        def checkResponse(result):
            self.assertIdentical(result, response)

        return deferred.addCallback(checkResponse)


    def _testRedirectDefault(self, code):
        """
        When getting a redirect, L{RedirectAgent} follows the URL specified in
        the L{Location} header field and make a new request.
        """
        self.agent.request('GET', 'http://example.com/foo')

        host, port = self.reactor.tcpClients.pop()[:2]
        self.assertEqual("example.com", host)
        self.assertEqual(80, port)

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers(
            {'location': ['https://example.com/bar']})
        response = Response(('HTTP', 1, 1), code, 'OK', headers, None)
        res.callback(response)

        req2, res2 = self.protocol.requests.pop()
        self.assertEqual('GET', req2.method)
        self.assertEqual('/bar', req2.uri)

        host, port = self.reactor.sslClients.pop()[:2]
        self.assertEqual("example.com", host)
        self.assertEqual(443, port)


    def test_redirect301(self):
        """
        L{RedirectAgent} follows redirects on status code 301.
        """
        self._testRedirectDefault(301)


    def test_redirect302(self):
        """
        L{RedirectAgent} follows redirects on status code 302.
        """
        self._testRedirectDefault(302)


    def test_redirect307(self):
        """
        L{RedirectAgent} follows redirects on status code 307.
        """
        self._testRedirectDefault(307)


    def test_redirect303(self):
        """
        L{RedirectAgent} changes the methods to C{GET} when getting a redirect
        on a C{POST} request.
        """
        self.agent.request('POST', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers(
            {'location': ['http://example.com/bar']})
        response = Response(('HTTP', 1, 1), 303, 'OK', headers, None)
        res.callback(response)

        req2, res2 = self.protocol.requests.pop()
        self.assertEqual('GET', req2.method)
        self.assertEqual('/bar', req2.uri)


    def test_noLocationField(self):
        """
        If no L{Location} header field is found when getting a redirect,
        L{RedirectAgent} fails with a L{ResponseFailed} error wrapping a
        L{error.RedirectWithNoLocation} exception.
        """
        deferred = self.agent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers()
        response = Response(('HTTP', 1, 1), 301, 'OK', headers, None)
        res.callback(response)

        self.assertFailure(deferred, client.ResponseFailed)

        def checkFailure(fail):
            fail.reasons[0].trap(error.RedirectWithNoLocation)
            self.assertEqual('http://example.com/foo',
                             fail.reasons[0].value.uri)
            self.assertEqual(301, fail.response.code)

        return deferred.addCallback(checkFailure)


    def test_307OnPost(self):
        """
        When getting a 307 redirect on a C{POST} request, L{RedirectAgent} fais
        with a L{ResponseFailed} error wrapping a L{error.PageRedirect}
        exception.
        """
        deferred = self.agent.request('POST', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers()
        response = Response(('HTTP', 1, 1), 307, 'OK', headers, None)
        res.callback(response)

        self.assertFailure(deferred, client.ResponseFailed)

        def checkFailure(fail):
            fail.reasons[0].trap(error.PageRedirect)
            self.assertEqual('http://example.com/foo',
                             fail.reasons[0].value.location)
            self.assertEqual(307, fail.response.code)

        return deferred.addCallback(checkFailure)


    def test_redirectLimit(self):
        """
        If the limit of redirects specified to L{RedirectAgent} is reached, the
        deferred fires with L{ResponseFailed} error wrapping a
        L{InfiniteRedirection} exception.
        """
        agent = self.buildAgentForWrapperTest(self.reactor)
        redirectAgent = client.RedirectAgent(agent, 1)

        deferred = redirectAgent.request('GET', 'http://example.com/foo')

        req, res = self.protocol.requests.pop()

        headers = http_headers.Headers(
            {'location': ['http://example.com/bar']})
        response = Response(('HTTP', 1, 1), 302, 'OK', headers, None)
        res.callback(response)

        req2, res2 = self.protocol.requests.pop()

        response2 = Response(('HTTP', 1, 1), 302, 'OK', headers, None)
        res2.callback(response2)

        self.assertFailure(deferred, client.ResponseFailed)

        def checkFailure(fail):
            fail.reasons[0].trap(error.InfiniteRedirection)
            self.assertEqual('http://example.com/foo',
                             fail.reasons[0].value.location)
            self.assertEqual(302, fail.response.code)

        return deferred.addCallback(checkFailure)
