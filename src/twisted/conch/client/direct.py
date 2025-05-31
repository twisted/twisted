# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from twisted.conch import error
from twisted.conch.ssh import transport
from twisted.internet import defer, protocol, reactor
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet.interfaces import (
    IAddress,
    IConnector,
    IListeningPort,
    IReactorTCP,
)
from twisted.python.failure import Failure

if TYPE_CHECKING:
    from twisted.conch.client.options import ConchOptions
    from twisted.conch.ssh.userauth import SSHUserAuthClient


class SSHClientFactory(protocol.ClientFactory):
    def __init__(
        self,
        d: Deferred[None],
        options: ConchOptions,
        verifyHostKey: _VHK,
        userAuthObject: SSHUserAuthClient,
    ) -> None:
        self.d: Deferred[None] | None = d
        self.options = options
        self.verifyHostKey = verifyHostKey
        self.userAuthObject = userAuthObject

    def clientConnectionLost(self, connector: IConnector, reason: Failure) -> None:
        if self.options["reconnect"]:
            connector.connect()

    def clientConnectionFailed(self, connector: IConnector, reason: Failure) -> None:
        if self.d is None:
            return
        d, self.d = self.d, None
        d.errback(reason)

    def buildProtocol(self, addr: IAddress) -> SSHClientTransport:
        trans = SSHClientTransport(self)
        if self.options["ciphers"]:
            trans.supportedCiphers = self.options["ciphers"]
        if self.options["macs"]:
            trans.supportedMACs = self.options["macs"]
        if self.options["compress"]:
            trans.supportedCompressions[0:1] = [b"zlib"]
        if self.options["host-key-algorithms"]:
            trans.supportedPublicKeys = self.options["host-key-algorithms"]
        return trans


class SSHClientTransport(transport.SSHClientTransport):
    # pre-mypy LSP violation
    factory: SSHClientFactory  # type:ignore[assignment]

    def __init__(self, factory: SSHClientFactory) -> None:
        self.factory = factory
        self.unixServer: None | IListeningPort = None

    def connectionLost(self, reason: Failure | None = None) -> None:
        if self.unixServer:
            # The C{unixServer} attribute is untested, and it's not entirely
            # clear that it does anything at all. It appears to be a vestigial
            # attempt to support something like OpenSSH's ControlMaster client
            # option; at some point we should either document and test it, or
            # remove it.

            # https://github.com/twisted/twisted/issues/12418
            d = maybeDeferred(self.unixServer.stopListening)  # pragma: no cover
            self.unixServer = None  # pragma: no cover
        else:
            d = defer.succeed(None)
        d.addCallback(
            lambda x: transport.SSHClientTransport.connectionLost(self, reason)
        )

    def receiveError(self, code, desc):
        if self.factory.d is None:
            return
        d, self.factory.d = self.factory.d, None
        d.errback(error.ConchError(desc, code))

    def sendDisconnect(self, code, reason):
        if self.factory.d is None:
            return
        d, self.factory.d = self.factory.d, None
        transport.SSHClientTransport.sendDisconnect(self, code, reason)
        d.errback(error.ConchError(reason, code))

    def receiveDebug(self, alwaysDisplay, message, lang):
        self._log.debug(
            "Received Debug Message: {message}",
            message=message,
            alwaysDisplay=alwaysDisplay,
            lang=lang,
        )
        if alwaysDisplay:  # XXX what should happen here?
            print(message)

    def verifyHostKey(self, pubKey: bytes, fingerprint: str) -> Deferred[bool]:
        transport = self.transport
        assert transport is not None
        peer = transport.getPeer()
        assert isinstance(
            peer, (IPv4Address, IPv6Address)
        ), "Address must have a host to verify against."
        return self.factory.verifyHostKey(
            self, peer.host.encode("utf-8"), pubKey, fingerprint
        )

    def setService(self, service):
        self._log.info("setting client server to {service}", service=service)
        transport.SSHClientTransport.setService(self, service)
        if service.name != "ssh-userauth" and self.factory.d is not None:
            d, self.factory.d = self.factory.d, None
            d.callback(None)

    def connectionSecure(self):
        self.requestService(self.factory.userAuthObject)


_VHK = Callable[[SSHClientTransport, bytes, bytes, str], Deferred[bool]]


def connect(
    host: str,
    port: int,
    options: ConchOptions,
    verifyHostKey: _VHK,
    userAuthObject: SSHUserAuthClient,
) -> Deferred[None]:
    d: Deferred[None] = defer.Deferred()
    factory = SSHClientFactory(d, options, verifyHostKey, userAuthObject)
    IReactorTCP(reactor).connectTCP(host, port, factory)
    return d
