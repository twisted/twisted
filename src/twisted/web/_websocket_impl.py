# -*- test-case-name: twisted.web.test.test_websocket -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Private implementation module for public L{twisted.web.websocket}.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from functools import singledispatch
from typing import Callable, Generic, TypeVar, Union

from zope.interface import implementer

from hyperlink import URL
from wsproto import Connection, ConnectionType, WSConnection
from wsproto.connection import ConnectionState
from wsproto.events import (
    AcceptConnection,
    BytesMessage,
    CloseConnection,
    Event,
    Ping,
    Pong,
    RejectConnection,
    RejectData,
    Request as WSRequest,
    TextMessage,
)
from wsproto.handshake import H11Handshake
from wsproto.utilities import RemoteProtocolError

from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IConsumer,
    IProtocol,
    IPushProducer,
    IReactorTCP,
    ITransport,
)
from twisted.internet.protocol import Factory as ProtocolFactory
from twisted.logger import Logger
from twisted.python.failure import Failure
from twisted.web._responses import BAD_REQUEST
from twisted.web.client import (
    URI,
    BrowserLikePolicyForHTTPS,
    Response,
    _StandardEndpointFactory,
)
from twisted.web.http_headers import Headers
from twisted.web.iweb import IAgentEndpointFactory, IPolicyForHTTPS
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Request


class WebSocketTransport(typing.Protocol):
    """
    The transport that can send websocket messages.
    """

    def sendTextMessage(self, text: str) -> None:
        """
        Send a text message.
        """

    def sendBytesMessage(self, data: bytes) -> None:
        """
        Send a bytes message.
        """

    def loseConnection(self, code: int = 1000) -> None:
        """
        Drop the websocket connection.
        """

    def ping(self, payload: bytes = b"") -> None:
        """
        Send a websocket Ping request to measure latency.

        @note: Per U{Mozilla's documentation
            <https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_servers#pings_and_pongs_the_heartbeat_of_websockets>},
            multiple 'ping' requests may be coalesced into a single 'pong', and
            unsolicited 'pong' requests must be ignored, so we do not return a
            L{deferred <twisted.internet.defer.Deferred>} here; pongs are
            delivered separately.
        """

    def attachProducer(self, producer: IPushProducer) -> None:
        """
        Attach the given L{IPushProducer} to this transport.
        """

    def detachProducer(self) -> None:
        """
        Detach a previously attached L{IPushProducer} from this transport.
        """


@dataclass
class ConnectionRejected(Exception):
    """
    A websocket connection was rejected by an HTTP response.

    @ivar response: The HTTP response that describes the rejection.
    """

    response: Response


class WebSocketProtocol(typing.Protocol):
    """
    An object that conforms to L{WebSocketProtocol} can receive all the events
    from a websocket connection.

    @note: While this is I{sort of} like a L{byte-stream protocol
        <twisted.internet.interfaces.IProtocol>}, the interface is distinct in
        a few ways; in particular, we have discrete C{negotiationStarted} and
        C{negotiationFinished} methods, representing those events in the
        websocket handshaking process, and no C{connectionMade}; similarly,
        since websockets can natively support both text and bytes messages,
        rather than fragmentable segments of a byte stream, we have
        C{textMessageReceived} and C{bytesMessageReceived} but no
        C{dataReceived}.  Finally, this is a L{typing.Protocol} and not a
        L{zope.interface.Interface}, since it does not predate the L{typing}
        module.
    """

    def negotiationStarted(self, transport: WebSocketTransport) -> None:
        """
        An underlying transport (e.g.: a TCP connection) has been established;
        negotiation of the websocket transport has begun.
        """

    def negotiationFinished(self) -> None:
        """
        Negotiation is complete: a bidirectional websocket channel is now fully
        established.
        """

    def pongReceived(self, payload: bytes) -> None:
        """
        A Pong message was received.

        @note: Per U{the standard
            <https://www.rfc-editor.org/rfc/rfc6455#section-5.5.2>}::

                A Pong frame sent in response to a Ping frame must have identical
                "Application data" as found in the message body of the Ping frame
                being replied to.

                If an endpoint receives a Ping frame and has not yet sent Pong
                frame(s) in response to previous Ping frame(s), the endpoint MAY
                elect to send a Pong frame for only the most recently processed
                Ping frame.

            Given that some Pong frames may be dropped, this event should only
            be used in concert with the transport's L{.ping
            <WebSocketTransport.ping>} method for its intended purpose, to
            measure latency and connection durability, not to transport
            application data.
        """

    def textMessageReceived(self, message: str) -> None:
        """
        A text message was received from the peer.
        """

    def bytesMessageReceived(self, data: bytes) -> None:
        """
        A bytes message was received from the peer.
        """

    def connectionLost(self, reason: Failure) -> None:
        """
        The websocket connection was lost.
        """


_WSP = TypeVar("_WSP", covariant=True, bound=WebSocketProtocol)
_Bootstrap = Callable[[Union[WSConnection, Connection], ITransport], None]
_log = Logger()


class WebSocketServerFactory(typing.Protocol[_WSP]):
    """
    A L{WebSocketServerFactory} is a factory for a particular kind of
    L{WebSocketProtocol} that implements server-side websocket listeners via
    L{WebSocketResource}.
    """

    def buildProtocol(self, request: Request) -> _WSP:
        """
        To conform to L{WebSocketServerFactory}, you must implement a
        C{buildProtocol} method which takes a L{Request
        <twisted.web.server.Request>} and returns a L{WebSocketProtocol}.

        @return: a L{WebSocketProtocol} that will handle the inbound
            connection.
        """


class WebSocketClientFactory(typing.Protocol[_WSP]):
    """
    A L{WebSocketClientFactory} is a factory for a particular kind of
    L{WebSocketProtocol} that implements client-side websocket listeners via
    L{WebSocketClientEndpoint}.
    """

    def buildProtocol(self, url: str) -> _WSP:
        """
        To conform to L{WebSocketServerFactory}, you must implement a
        C{buildProtocol} method which takes a string representing an URL and
        returns a L{WebSocketProtocol}.

        @return: a L{WebSocketProtocol} that will handle the outgoing
            connection.
        """


@dataclass(frozen=True)
class WebSocketClientEndpoint:
    """
    A L{WebSocketClientEndpoint} describes an URL to connect to and a way of
    connecting to that URL, that can connect a L{WebSocketClientFactory} to
    that URL.
    """

    endpointFactory: IAgentEndpointFactory
    """
    an L{IAgentEndpointFactory} that constructs agent endpoints when L{connect
    <WebSocketClientEndpoint.connect>}
    """
    url: str
    """
    the URL to connect to.
    """

    @classmethod
    def new(
        cls,
        reactor: IReactorTCP,
        url: str,
        tlsPolicy: IPolicyForHTTPS = BrowserLikePolicyForHTTPS(),
        connectTimeout: int | None = None,
        bindAddress: bytes | None = None,
    ) -> WebSocketClientEndpoint:
        """
        Construct a L{WebSocketClientEndpoint} from a reactor and a URL.

        @param reactor: The reactor to use for the TCP connection.

        @param url: a string describing an URL where a websocket server lives.

        @param tlsPolicy: The TLS policy to use for HTTPS connections.

        @param connectTimeout: The number of seconds for the TCP-level
            connection timeout.

        @param bindAddress: The bind address to use for the TCP client
            connections.

        @return: the newly constructed endpoint.
        """
        endpointFactory = _StandardEndpointFactory(
            reactor, tlsPolicy, connectTimeout, bindAddress
        )
        return WebSocketClientEndpoint(endpointFactory, url)

    async def connect(self, protocolFactory: WebSocketClientFactory[_WSP]) -> _WSP:
        """
        Make an outgoing connection to this L{WebSocketClientEndpoint}'s HTTPS
        connection.

        @param protocolFactory: The constructor for the protocol.

        @return: A coroutine (that yields L{Deferred}s) that completes with the
            connected L{WebSocketProtocol} once the websocket connection is
            established.
        """
        endpoint = self.endpointFactory.endpointForURI(
            URI.fromBytes(self.url.encode("utf-8"))
        )

        def clientBootstrap(wsc: WSConnection | Connection, t: ITransport) -> None:
            h = URL.fromText(self.url)
            target = str(h.replace(scheme="", host="", port=None))
            t.write(wsc.send(WSRequest(h.host, target)))

        connected: _WebSocketWireProtocol[_WSP] = await endpoint.connect(
            ProtocolFactory.forProtocol(
                lambda: _WebSocketWireProtocol(
                    WSConnection(ConnectionType.CLIENT),
                    clientBootstrap,
                    protocolFactory.buildProtocol(self.url),
                )
            )
        )
        return await connected._done


@singledispatch
def _handleEvent(event: Event, proto: AnyWSWP) -> None:
    """
    Handle a websocket protocol event.
    """


@implementer(IProtocol)
@dataclass
class _WebSocketWireProtocol(Generic[_WSP]):
    # Required constructor arguments.
    _wsconn: WSConnection | Connection
    _bootstrap: _Bootstrap
    _wsp: _WSP

    # Public attribute.
    transport: ITransport = field(init=False)

    # Internal state.
    _done: Deferred[_WSP] = field(init=False)
    _rejectResponse: Response | None = None

    def makeConnection(self, transport: ITransport) -> None:
        self.transport = transport
        self._done = Deferred()
        self.connectionMade()

    def connectionMade(self) -> None:
        # TODO: write during negotiationStarted breaks the connection?
        self._wsp.negotiationStarted(self)
        self._bootstrap(self._wsconn, self.transport)

    def dataReceived(self, data: bytes) -> None:
        self._wsconn.receive_data(data)
        for event in self._wsconn.events():
            _handleEvent(event, self)

    def connectionLost(self, reason: Failure) -> None:
        self._wsp.connectionLost(reason)
        if self._rejectResponse is not None:
            self._rejectResponse._bodyDataFinished(reason)
            self._rejectResponse = None

    # Implementation of WebSocketTransport
    def sendTextMessage(self, text: str) -> None:
        t = self.transport
        assert t is not None
        t.write(self._wsconn.send(TextMessage(text)))

    def sendBytesMessage(self, data: bytes) -> None:
        t = self.transport
        assert t is not None
        t.write(self._wsconn.send(BytesMessage(data)))

    def ping(self, payload: bytes = b"") -> None:
        t = self.transport
        assert t is not None
        t.write(self._wsconn.send(Ping(payload)))

    def loseConnection(self, code: int = 1000, reason: str = "") -> None:
        t = self.transport
        assert t is not None
        t.write(self._wsconn.send(CloseConnection(code, reason)))
        t.loseConnection()

    def attachProducer(self, producer: IPushProducer) -> None:
        IConsumer(self.transport).registerProducer(producer, True)

    def detachProducer(self) -> None:
        IConsumer(self.transport).unregisterProducer()

    def _completeConnection(self) -> None:
        done = self._done
        del self._done
        done.callback(self._wsp)
        self._wsp.negotiationFinished()

    def _rejectConnection(self) -> None:
        assert self._rejectResponse is not None
        done = self._done
        del self._done
        done.errback(ConnectionRejected(self._rejectResponse))


AnyWSWP = _WebSocketWireProtocol[WebSocketProtocol]


@_handleEvent.register
def _handle_acceptConnection(event: AcceptConnection, proto: AnyWSWP) -> None:
    proto._completeConnection()


@_handleEvent.register
def _handle_rejectConnection(event: RejectConnection, proto: AnyWSWP) -> None:
    hdr = Headers()
    for k, v in event.headers:
        hdr.addRawHeader(k, v)
    proto._rejectResponse = Response("1.1", event.status_code, "", hdr, proto.transport)
    proto._rejectConnection()


@_handleEvent.register
def _handle_rejectData(event: RejectData, proto: AnyWSWP) -> None:
    assert (
        proto._rejectResponse is not None
    ), "response should never be None when receiving RejectData"
    proto._rejectResponse._bodyDataReceived(event.data)
    if event.body_finished:
        proto.transport.loseConnection()


@_handleEvent.register
def _handle_textMessage(event: TextMessage, proto: AnyWSWP) -> None:
    proto._wsp.textMessageReceived(event.data)


@_handleEvent.register
def _handle_bytesMessage(event: BytesMessage, proto: AnyWSWP) -> None:
    proto._wsp.bytesMessageReceived(event.data)


@_handleEvent.register
def _handle_ping(event: Ping, proto: AnyWSWP) -> None:
    proto.transport.write(proto._wsconn.send(event.response()))


@_handleEvent.register
def _handle_pong(event: Pong, proto: AnyWSWP) -> None:
    proto._wsp.pongReceived(event.payload)


@_handleEvent.register
def _handle_closeConnection(event: CloseConnection, proto: AnyWSWP) -> None:
    assert proto.transport is not None
    if proto._wsconn.state != ConnectionState.CLOSED:
        proto.transport.write(proto._wsconn.send(event.response()))
    proto.transport.loseConnection()


def _negotiationError(request: Request) -> bytes:
    request.setResponseCode(BAD_REQUEST)
    request.setHeader("content-type", "text/plain")
    return b"websocket protocol negotiation error"


class WebSocketResource(Resource):
    """
    A L{WebSocketResource} is a L{Resource} that presents a websocket listener.
    You can install it into any twisted web server resource hierarchy.
    """

    def __init__(self, factory: WebSocketServerFactory[WebSocketProtocol]) -> None:
        """
        Create a L{WebSocketResource} that will respond to incoming connections
        with the given L{WebSocketServerFactory}.

        @param factory: The factory that will be used to respond to inbound
            websocket connections on appropriately formatted GET requests.
        """
        super().__init__()
        self.factory = factory

    def render_GET(self, request: Request) -> bytes | int:
        """
        This implementation of the C{GET} HTTP method will respond to inbound
        websocket connections.
        """
        handshake = H11Handshake(ConnectionType.SERVER)
        raw = request.requestHeaders.getAllRawHeaders()
        simpleHeaders = [(hkey, val) for hkey, hvals in raw for val in hvals]
        try:
            handshake.initiate_upgrade_connection(simpleHeaders, request.path)
        except RemoteProtocolError as rpe:
            _log.error("{request} failed with {rpe}", request=request, rpe=rpe)
            return _negotiationError(request)
        wsprot = self.factory.buildProtocol(request)
        assert wsprot is not None, "connection not accepted by twisted"
        toSend = handshake.send(AcceptConnection())
        wscon = handshake.connection
        t = request.channel.transport
        assert t is not None, "channel transport not connected"
        assert wscon is not None, "connection not accepted by wsproto"
        wireProto = _WebSocketWireProtocol(wscon, serverBootstrap, wsprot)
        request.channel._protocolUpgradeForWebsockets(wireProto)
        t.write(toSend)
        wsprot.negotiationFinished()
        return NOT_DONE_YET


def serverBootstrap(wsc: WSConnection | Connection, t: ITransport) -> None:
    """
    The server requires no bootstrapping, so this is a no-op.
    """
