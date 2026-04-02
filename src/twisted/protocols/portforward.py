# -*- test-case-name: twisted.test.test_protocols.PortforwardingTests -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A simple port forwarder.
"""
from __future__ import annotations

from twisted.internet import protocol
from twisted.internet.interfaces import (
    IAddress,
    IConsumer,
    IPushProducer,
    IStreamServerEndpoint,
    ITransport,
)


class Proxy(protocol.Protocol):
    noisy = True
    peer: Proxy | None = None
    factory: protocol.Factory[Proxy]

    def setPeer(self, peer: Proxy | None) -> None:
        self.peer = peer

    def connectionLost(self, reason):
        if self.peer is not None:
            self.peer.transport.loseConnection()
            self.peer = None

    def dataReceived(self, data):
        self.peer.transport.write(data)


class ProxyClient(Proxy):
    factory: protocol.Factory[ProxyClient]  # type:ignore

    def connectionMade(self) -> None:
        assert self.peer is not None
        self.peer.setPeer(self)

        # Wire this and the peer transport together to enable
        # flow control (this stops connections from filling
        # this proxy memory when one side produces data at a
        # higher rate than the other can consume).
        self.transport.registerProducer(self.peer.transport, True)  # type:ignore
        self.peer.transport.registerProducer(self.transport, True)  # type:ignore

        # We're connected, everybody can read to their hearts content.
        self.peer.transport.resumeProducing()  # type:ignore


class ProxyClientFactory(protocol.ClientFactory[ProxyClient]):
    protocol = ProxyClient

    def setServer(self, server):
        self.server = server

    def buildProtocol(self, addr: IAddress | None) -> ProxyClient:
        prot = super().buildProtocol(addr)
        assert prot is not None, "peer must build protocol"
        prot.setPeer(self.server)
        return prot

    def clientConnectionFailed(self, connector, reason):
        self.server.transport.loseConnection()


class _MakeTypesHappy(IPushProducer, IConsumer, ITransport):
    """
    L{ProxyServer}'s transport is implicitly assumed to provide several
    interfaces so include them all here.
    """


class ProxyServer(Proxy):
    clientProtocolFactory = ProxyClientFactory
    reactor = None
    transport: _MakeTypesHappy
    factory: ProxyFactory  # type:ignore[assignment]
    endpoint: IStreamServerEndpoint | None

    def connectionMade(self) -> None:
        # Don't read anything from the connecting client until we have
        # somewhere to send it to.
        self.transport.pauseProducing()

        client = self.clientProtocolFactory()
        client.setServer(self)

        if self.reactor is None:
            from twisted.internet import reactor

            self.reactor = reactor
        self.reactor.connectTCP(self.factory.host, self.factory.port, client)


class ProxyFactory(protocol.Factory[ProxyServer]):
    """
    Factory for port forwarder.
    """

    protocol = ProxyServer

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
