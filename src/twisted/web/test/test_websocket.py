# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.websocket}.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from unittest import skipIf

from zope.interface import implementer

from twisted.internet.address import IPv4Address
from twisted.internet.defer import Deferred
from twisted.internet.error import ConnectionDone
from twisted.internet.interfaces import IPushProducer
from twisted.internet.task import Clock
from twisted.internet.testing import (
    AccumulatingProtocol,
    MemoryReactorClock,
    StringTransport,
)
from twisted.python.failure import Failure
from twisted.test.iosim import ConnectionCompleter, IOPump
from twisted.trial.unittest import SynchronousTestCase
from twisted.web._responses import BAD_REQUEST
from twisted.web.client import Agent, readBody
from twisted.web.iweb import IRequest
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Request, Site
from twisted.web.static import Data

WSP = TypeVar("WSP", bound="WebSocketProtocol")
shouldSkip = False


class WeirdResource(Resource):
    def render_GET(self, request: Request) -> bytes:
        """
        Per U{the wsproto documentation
        <https://python-hyper.org/projects/wsproto/en/latest/api.html#wsproto.events.RejectConnection.has_body>}:

            - The only scenario in which the caller receives a RejectConnection
              with C{has_body == False} is if the peer violates sends an
              informational status code (1xx) other than 101

        This is a weird edge case so we provoke it.
        """
        request.setResponseCode(102)
        return b""


class DelayedResponse(Resource):
    """
    A resource that will not respond to a C{GET} request right away.  You will
    need to use the C{request.write(b'RESPONSE BODY')} and C{request.finish()}
    to trigger a response.
    """

    def render_GET(self, request: Request) -> int:
        self.request = request
        return NOT_DONE_YET


try:
    __import__("wsproto")
except ImportError:
    shouldSkip = True
else:
    from twisted.web.websocket import (
        ConnectionRejected,
        WebSocketClientEndpoint,
        WebSocketClientFactory,
        WebSocketProtocol,
        WebSocketResource,
        WebSocketServerFactory,
        WebSocketTransport,
    )

    @dataclass
    class MyWSP(WebSocketProtocol):
        """
        Used to implement both client-side and server-side WebSocket
        application that will help with testing.
        """

        pongs: list[bytes] = field(default_factory=list)
        wasLost: Failure | None = None

        def negotiationStarted(self, transport: WebSocketTransport) -> None:
            self.transport = transport

        def negotiationFinished(self) -> None:
            ...

        def connectionLost(self, reason: Failure) -> None:
            self.wasLost = reason

        def bytesMessageReceived(self, data: bytes | bytearray) -> None:
            if data == b"request":
                self.transport.sendBytesMessage(b"\x00resp\x01onse\xff")
            else:
                self.bDeferred.callback(data)

        def textMessageReceived(self, data: str) -> None:
            if data == "request":
                self.transport.sendTextMessage("response")
            else:
                self.deferred.callback(data)

        def pongReceived(self, payload: bytes) -> None:
            self.pongs.append(payload)

        def sendRequest(self) -> Deferred[str]:
            """
            Send a text message to the server and expect a response.
            """
            self.deferred: Deferred[str] = Deferred()
            self.transport.sendTextMessage("request")
            return self.deferred

        def bytesRequest(self) -> Deferred[bytes | bytearray]:
            """
            Send a bytes message to the server and expect a response.
            """
            self.bDeferred: Deferred[bytes | bytearray] = Deferred()
            self.transport.sendBytesMessage(b"request")
            return self.bDeferred

    class MyFactory(WebSocketServerFactory[MyWSP]):
        fixture: WebSocketFixture[Any]

        def buildProtocol(self, request: IRequest) -> MyWSP:
            new = MyWSP()
            self.fixture.servers.append(new)
            return new

    class MyClientFactory(WebSocketClientFactory[MyWSP]):
        def buildProtocol(self, uri: str) -> MyWSP:
            return MyWSP()


@dataclass
class WebSocketFixture(Generic[WSP]):
    clientFactory: WebSocketClientFactory[WSP] = field()
    reactor: MemoryReactorClock = field(default_factory=MemoryReactorClock)
    resource: Resource = field(default_factory=Resource)
    portNumber: int = 80
    servers: list[WSP] = field(default_factory=list)
    slowResource: DelayedResponse = field(default_factory=DelayedResponse)

    @classmethod
    def new(cls, clientFactory: WebSocketClientFactory[WSP]) -> WebSocketFixture[WSP]:
        self = cls(clientFactory)
        serverFactory = MyFactory()
        serverFactory.fixture = self
        self.resource.putChild(b"connect", WebSocketResource(serverFactory))
        self.resource.putChild(
            b"resource", Data(b"some-data", "application/octet-stream")
        )
        self.resource.putChild(b"processing", WeirdResource())
        self.resource.putChild(b"slow", self.slowResource)
        self.reactor.listenTCP(
            self.portNumber, Site(self.resource, reactor=self.reactor)
        )
        return self

    async def connect(self, uri: str = "http://localhost:80/connect") -> WSP:
        client = WebSocketClientEndpoint.new(self.reactor, uri)
        return await client.connect(self.clientFactory)

    def complete(self, greet: bool = True) -> IOPump:
        """
        There should be a single websocket connection in progress; complete it.

        @param greet: Should we immediately issue a greeting, i.e. deliver any
            pending buffered TCP data, upon connection?  If C{False}, the
            caller must call C{flush} on the result to deliver any pending
            data.
        """
        completer = ConnectionCompleter(self.reactor)
        succeeded = completer.succeedOnce(greet=greet)
        assert succeeded is not None, "Connection not in progress."
        return succeeded


@skipIf(shouldSkip, "wsproto library required for websockets")
class WebSocketTests(SynchronousTestCase):
    def test_websocket(self) -> None:
        """
        Connecting to a websocket server (installed with L{WebSocketResource})
        from a websocket client (connected with L{WebSocketClientEndpoint})
        results in a websocket connection.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        connected = Deferred.fromCoroutine(fixture.connect())
        self.assertNoResult(connected)
        self.assertEqual(len(fixture.reactor.tcpServers), 1)
        self.assertEqual(len(fixture.reactor.tcpClients), 1)
        pump = fixture.complete()
        wsClient = self.successResultOf(connected)
        requested = wsClient.sendRequest()
        self.assertNoResult(requested)
        pump.flush()
        self.assertEqual(self.successResultOf(requested), "response")

    def test_bytesMessage(self) -> None:
        """
        Connecting to a websocket server and sending it a bytes message results
        in C{bytesMessageReceived} being called.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        connected = Deferred.fromCoroutine(fixture.connect())
        pump = fixture.complete()
        wsClient = self.successResultOf(connected)
        bRequested = wsClient.bytesRequest()
        self.assertNoResult(bRequested)
        pump.flush()
        self.assertEqual(self.successResultOf(bRequested), b"\x00resp\x01onse\xff")

    def test_backpressure(self) -> None:
        """
        Websocket transports can notify a producer of backpressure events via
        attachProducer.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        Deferred.fromCoroutine(fixture.connect())
        pump = fixture.complete()
        events = []

        @implementer(IPushProducer)
        class TestProducer:
            def pauseProducing(self) -> None:
                events.append("paused")

            def resumeProducing(self) -> None:
                events.append("resumed")

            def stopProducing(self) -> None:
                events.append("stopped")

        testProducer = TestProducer()
        fixture.servers[0].transport.attachProducer(testProducer)
        self.assertEqual(events, [])
        pump.serverIO.producer.pauseProducing()
        self.assertEqual(events, ["paused"])
        pump.serverIO.producer.resumeProducing()
        self.assertEqual(events, ["paused", "resumed"])
        pump.serverIO.producer.stopProducing()
        self.assertEqual(events, ["paused", "resumed", "stopped"])
        self.assertIs(pump.serverIO.producer, testProducer)
        fixture.servers[0].transport.detachProducer()
        self.assertIs(pump.serverIO.producer, None)

    def test_pingPong(self) -> None:
        """
        Internally, Twisted's websocket resource responds to all ping requests
        with a pong as required by the spec, so peers can issue a C{ping} and
        receive a C{pong} message with the same payload; our websocket
        transport also implements a C{ping} method to send that message.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        connected = Deferred.fromCoroutine(fixture.connect())
        pump = fixture.complete()
        wsClient = self.successResultOf(connected)
        wsClient.transport.ping(b"123")
        self.assertEqual(wsClient.pongs, [])
        pump.flush()
        self.assertEqual(wsClient.pongs, [b"123"])

    def test_serverConnectionLost(self) -> None:
        """
        When the underlying TCP connection is lost,
        L{WebSocketProtocol.connectionLost} is invoked.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        connected = Deferred.fromCoroutine(fixture.connect())
        pump = fixture.complete()
        wsClient = self.successResultOf(connected)
        self.assertIs(fixture.servers[0].wasLost, None)
        self.assertIs(wsClient.wasLost, None)
        wsClient.transport.loseConnection()
        self.assertIs(fixture.servers[0].wasLost, None)
        self.assertIs(wsClient.wasLost, None)
        pump.flush()
        self.assertIsNot(fixture.servers[0].wasLost, None)
        self.assertIsNot(wsClient.wasLost, None)

    def test_bad(self) -> None:
        """
        Attempting to issue an C{HTTP GET} against a websocket server
        (installed with L{WebSocketResource}) results in a C{BAD_REQUEST}
        response.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        agent = Agent(fixture.reactor)
        response = agent.request(b"GET", b"http://localhost/connect")
        self.assertNoResult(response)
        fixture.complete()
        r = self.successResultOf(response)
        self.assertEqual(r.code, BAD_REQUEST)
        body = readBody(r)
        self.assertEqual(
            self.successResultOf(body), b"websocket protocol negotiation error"
        )

    def test_connectionRefused(self) -> None:
        """
        Attempting to connect to a regular HTTP resource that does not support
        websockets will result in the Deferred returned from
        L{WebSocketClientEndpoint} failing.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        connected = Deferred.fromCoroutine(fixture.connect("http://localhost/empty"))
        pump = fixture.complete(greet=False)
        self.assertNoResult(connected)
        pump.flush()
        self.failureResultOf(connected, ConnectionRejected)

    def test_connectionRefusedWeird(self) -> None:
        """
        Attempting to connect to a regular HTTP resource that does not support
        websockets will result in the Deferred returned from
        L{WebSocketClientEndpoint} failing.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        connected = Deferred.fromCoroutine(
            fixture.connect("http://localhost/processing")
        )
        pump = fixture.complete(greet=False)
        self.assertNoResult(connected)
        pump.flush()
        self.failureResultOf(connected, ConnectionRejected)

    def test_connectionRefusedSlow(self) -> None:
        """
        When the client connection is refused by an asynchronous HTTP response,
        the websocket client will not be notified until the response arrives.
        """
        fixture = WebSocketFixture.new(MyClientFactory())
        connected = Deferred.fromCoroutine(fixture.connect("http://localhost/slow"))
        pump = fixture.complete(greet=True)
        self.assertNoResult(connected)
        fixture.slowResource.request.write(b"")
        pump.flush()

        rejected = self.failureResultOf(connected, ConnectionRejected)
        resp = rejected.value.response
        resp.deliverBody(p := AccumulatingProtocol())
        self.assertEqual(p.data, b"")
        req = fixture.slowResource.request
        req.write(b"hello")
        pump.flush()
        self.assertEqual(p.data, b"hello")
        req.write(b"world")
        pump.flush()
        self.assertEqual(p.data, b"helloworld")
        req.finish()
        self.assertIs(p.closedReason, None)
        pump.flush()
        # expressed this way because assertIs isn't a guard for mypy
        assert p.closedReason is not None, "should be closed now"
        self.assertEqual(p.closedReason.type, ConnectionDone)


class Receiver:
    def __init__(self) -> None:
        self.messages: list[bytes | str] = []

    def buildProtocol(self, request: Request) -> Receiver:
        return self

    def bytesMessageReceived(self, data: bytes | bytearray) -> None:
        self.messages.append(bytes(data))

    def textMessageReceived(self, data: str) -> None:
        self.messages.append(data)

    def negotiationStarted(self, transport: WebSocketTransport) -> None:
        ...

    def negotiationFinished(self) -> None:
        ...

    def pongReceived(self, payload: bytes) -> None:
        ...

    def connectionLost(self, reason: Failure) -> None:
        ...


@skipIf(shouldSkip, "wsproto library required for websockets")
class MessageTest(SynchronousTestCase):
    def setUp(self) -> None:
        self.receiver = Receiver()
        root = Resource()
        root.putChild(b"ws", WebSocketResource(self.receiver))
        self.server = Site(root, reactor=Clock()).buildProtocol(
            IPv4Address("TCP", "127.0.0.1", 12345)
        )
        transport = StringTransport()
        self.server.makeConnection(transport)
        self.server.dataReceived(
            b"GET /ws HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Version: 13\r\n"
            b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n"
        )
        self.assertIn(b"HTTP/1.1 101", transport.value())

    # FIN=1, opcode=binary, MASK=1, length=6, four-byte zero mask, payload
    frame = b"\x82\x86\x00\x00\x00\x00abcdef"
    # FIN=1, opcode=text, MASK=1, length=6, four-byte zero mask, payload
    textFrame = b"\x81\x86\x00\x00\x00\x00abcdef"

    def testCompleteFrameControl(self) -> None:
        self.server.dataReceived(self.frame)
        self.assertEqual(self.receiver.messages, [b"abcdef"])

    def testOneFrameAcrossTwoReads(self) -> None:
        """
        A partial binary message is not forwarded
        unless it is fully received.
        """
        self.server.dataReceived(self.frame[:8])
        self.assertEqual(self.receiver.messages, [])
        self.server.dataReceived(self.frame[8:])
        self.assertEqual(self.receiver.messages, [b"abcdef"])

    def testOneFrameAcrossTwoReadsText(self) -> None:
        self.server.dataReceived(self.textFrame[:8])
        self.server.dataReceived(self.textFrame[8:])
        self.assertEqual(self.receiver.messages, ["abcdef"])

    def testOneMessageAcrossTwoFrames(self) -> None:
        # A non-final binary frame followed by a final continuation frame
        self.server.dataReceived(
            b"".join(
                [
                    b"\x02\x82\x00\x00\x00\x00ab",
                    b"\x80\x84\x00\x00\x00\x00cdef",
                ]
            )
        )
        self.assertEqual(self.receiver.messages, [b"abcdef"])

    def testOneMessageAcrossTwoFramesText(self) -> None:
        # A non-final binary frame followed by a final continuation frame
        self.server.dataReceived(
            b"".join(
                [
                    b"\x01\x82\x00\x00\x00\x00ab",
                    b"\x80\x84\x00\x00\x00\x00cdef",
                ]
            )
        )
        self.assertEqual(self.receiver.messages, ["abcdef"])
