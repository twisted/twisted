# -*- test-case-name: twisted.test.test_udp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import annotations

import socket
import struct
from typing import Any

from twisted.internet.abstract import isIPAddress, isIPv6Address
from twisted.internet.defer import Deferred, succeed
from twisted.internet.error import MulticastJoinError
from twisted.internet.interfaces import IReactorCore


def _maybeResolve(reactor: IReactorCore, addr: str) -> Deferred[str]:
    if isIPv6Address(addr) or isIPAddress(addr):
        return succeed(addr)
    return reactor.resolve(addr)


class MulticastMixin:
    """
    Implement multicast functionality.
    """

    addressFamily: socket.AddressFamily
    reactor: Any
    socket: socket.socket

    def _addrpack(self, addr: str) -> bytes:
        """
        Pack an IP address literal into bytes, according to the address family
        of this transport.
        """
        try:
            return socket.inet_pton(self.addressFamily, addr)
        except OSError:
            raise MulticastJoinError(
                f"invalid address literal for {socket.AddressFamily(self.addressFamily).name}: {addr!r}"
            )

    @property
    def _ipproto(self) -> int:
        return (
            socket.IPPROTO_IP
            if self.addressFamily == socket.AF_INET
            else socket.IPPROTO_IPV6
        )

    @property
    def _multiloop(self) -> int:
        return (
            socket.IP_MULTICAST_LOOP
            if self.addressFamily == socket.AF_INET
            else socket.IPV6_MULTICAST_LOOP
        )

    @property
    def _multiif(self) -> int:
        return (
            socket.IP_MULTICAST_IF
            if self.addressFamily == socket.AF_INET
            else socket.IPV6_MULTICAST_IF
        )

    @property
    def _joingroup(self) -> int:
        return (
            socket.IP_ADD_MEMBERSHIP
            if self.addressFamily == socket.AF_INET
            else socket.IPV6_JOIN_GROUP
        )

    @property
    def _leavegroup(self) -> int:
        return (
            socket.IP_DROP_MEMBERSHIP
            if self.addressFamily == socket.AF_INET
            else socket.IPV6_LEAVE_GROUP
        )

    def getOutgoingInterface(self) -> str | int:
        blen = 0x4 if self.addressFamily == socket.AF_INET else 0x10
        ipproto = self._ipproto
        multiif = self._multiif
        i = self.socket.getsockopt(ipproto, multiif, blen)
        from sys import byteorder

        if self.addressFamily == socket.AF_INET6:
            return int.from_bytes(i, byteorder)
        return socket.inet_ntop(self.addressFamily, i)

    def setOutgoingInterface(self, addr: str | int) -> Deferred[int]:
        """
        @see: L{IMulticastTransport.setOutgoingInterface}
        """

        async def asynchronously() -> int:
            i: bytes | int
            if self.addressFamily == socket.AF_INET:
                assert isinstance(
                    addr, str
                ), "IPv4 interfaces are specified as addresses"
                i = self._addrpack(await _maybeResolve(self.reactor, addr))
            else:
                assert isinstance(
                    addr, int
                ), "IPv6 interfaces are specified as integers"
                i = addr
            self.socket.setsockopt(self._ipproto, self._multiif, i)
            return 1

        return Deferred.fromCoroutine(asynchronously())

    def getLoopbackMode(self) -> bool:
        return bool(self.socket.getsockopt(self._ipproto, self._multiloop))

    def setLoopbackMode(self, mode: int) -> None:
        # mode = struct.pack("b", bool(mode))
        a = self._ipproto
        b = self._multiloop
        self.socket.setsockopt(a, b, int(bool(mode)))

    def getTTL(self) -> int:
        return self.socket.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL)

    def setTTL(self, ttl: int) -> None:
        bttl = struct.pack("B", ttl)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, bttl)

    def _joinleave(self, addr: str, interface: str, join: bool) -> Deferred[None]:
        cmd = self._joingroup if join else self._leavegroup
        if not interface:
            interface = "0.0.0.0" if self.addressFamily == socket.AF_INET else "::"

        async def impl() -> None:
            resaddr = await _maybeResolve(self.reactor, addr)
            resif = await _maybeResolve(self.reactor, interface)

            packaddr = self._addrpack(resaddr)
            packif = self._addrpack(resif)
            try:
                self.socket.setsockopt(self._ipproto, cmd, packaddr + packif)
            except OSError as e:
                raise MulticastJoinError(addr, interface, *e.args) from e

        return Deferred.fromCoroutine(impl())

    def joinGroup(self, addr: str, interface: str = "") -> Deferred[None]:
        """
        @see: L{IMulticastTransport.joinGroup}
        """
        return self._joinleave(addr, interface, True)

    def leaveGroup(self, addr: str, interface: str = "") -> Deferred[None]:
        """
        @see: L{IMulticastTransport.leaveGroup}
        """
        return self._joinleave(addr, interface, False)
