from __future__ import annotations

from typing import Any

from twisted.internet.defer import Failure
from twisted.internet.task import LoopingCall, deferLater, react
from twisted.web.websocket import WebSocketClientEndpoint, WebSocketTransport


class WebSocketClientDemo:
    @classmethod
    def buildProtocol(cls, uri: str) -> WebSocketClientDemo:
        return cls()

    def textMessageReceived(self, data: str) -> None:
        print(f"received text: {data!r}")

    def negotiationStarted(self, transport: WebSocketTransport) -> None:
        self.transport = transport

    def negotiationFinished(self) -> None:
        self.transport.sendTextMessage("hello, world!")

    def bytesMessageReceived(self, data: bytes) -> None:
        ...

    def connectionLost(self, reason: Failure) -> None:
        ...

    def pongReceived(self, payload: bytes) -> None:
        ...


async def main(reactor: Any) -> None:
    endpoint = WebSocketClientEndpoint.new(
        reactor, "ws://localhost:8080/websocket-server.rpy"
    )
    print("connecting...")
    await endpoint.connect(WebSocketClientDemo)
    print("connected!")
    await deferLater(reactor, 10)


react(main)
