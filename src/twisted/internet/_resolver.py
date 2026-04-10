# -*- test-case-name: twisted.internet.test.test_resolver -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
IPv6-aware hostname resolution.

@see: L{IHostnameResolver}
"""
from __future__ import annotations

from collections.abc import Sequence
from socket import (
    AF_INET,
    AF_INET6,
    AF_UNSPEC,
    SOCK_DGRAM,
    SOCK_STREAM,
    AddressFamily,
    SocketKind,
    gaierror,
    getaddrinfo,
)
from typing import TYPE_CHECKING, Callable, NoReturn, Protocol

from zope.interface import implementer

from twisted.internet._idna import _idnaBytes
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import Deferred
from twisted.internet.error import DNSLookupError
from twisted.internet.interfaces import (
    IAddress,
    IHostnameResolver,
    IHostResolution,
    IReactorThreads,
    IResolutionReceiver,
    IResolverSimple,
)
from twisted.internet.threads import deferToThreadPool
from twisted.logger import Logger
from twisted.python.compat import nativeString

if TYPE_CHECKING:
    from twisted.python.threadpool import ThreadPool


@implementer(IHostResolution)
class HostResolution:
    """
    The in-progress resolution of a given hostname.
    """

    def __init__(self, name: str):
        """
        Create a L{HostResolution} with the given name.
        """
        self.name = name

    def cancel(self) -> NoReturn:
        # IHostResolution.cancel
        raise NotImplementedError()


_any = frozenset([IPv4Address, IPv6Address])

_typesToAF = {
    frozenset([IPv4Address]): AF_INET,
    frozenset([IPv6Address]): AF_INET6,
    _any: AF_UNSPEC,
}

_afToType = {
    AF_INET: IPv4Address,
    AF_INET6: IPv6Address,
}

_transportToSocket = {
    "TCP": SOCK_STREAM,
    "UDP": SOCK_DGRAM,
}

_socktypeToType = {
    SOCK_STREAM: "TCP",
    SOCK_DGRAM: "UDP",
}


class _LikeGetAddrInfo(Protocol):
    """
    A callable matching the type signature of L{getaddrinfo}.
    """

    def __call__(
        self,
        host: bytes | str | None,
        port: bytes | str | int | None,
        family: int = AF_UNSPEC,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> list[
        tuple[
            AddressFamily,
            SocketKind,
            int,
            str,
            tuple[str, int] | tuple[str, int, int, int] | tuple[int, bytes],
        ]
    ]:
        ...


@implementer(IHostnameResolver)
class GAIResolver:
    """
    L{IHostnameResolver} implementation that resolves hostnames by calling
    L{getaddrinfo} in a thread.
    """

    def __init__(
        self,
        reactor: IReactorThreads,
        getThreadPool: Callable[[], ThreadPool] | None = None,
        getaddrinfo: _LikeGetAddrInfo = getaddrinfo,
    ):
        """
        Create a L{GAIResolver}.

        @param reactor: the reactor to schedule result-delivery on
        @type reactor: L{IReactorThreads}

        @param getThreadPool: a function to retrieve the thread pool to use for
            scheduling name resolutions.  If not supplied, the use the given
            C{reactor}'s thread pool.
        @type getThreadPool: 0-argument callable returning a
            L{twisted.python.threadpool.ThreadPool}

        @param getaddrinfo: a reference to the L{getaddrinfo} to use - mainly
            parameterized for testing.
        @type getaddrinfo: callable with the same signature as L{getaddrinfo}
        """
        self._reactor = reactor
        self._getThreadPool = (
            reactor.getThreadPool if getThreadPool is None else getThreadPool
        )
        self._getaddrinfo = getaddrinfo

    def resolveHostName(
        self,
        resolutionReceiver: IResolutionReceiver,
        hostName: str,
        portNumber: int = 0,
        addressTypes: Sequence[type[IAddress]] | None = None,
        transportSemantics: str = "TCP",
    ) -> IHostResolution:
        """
        See L{IHostnameResolver.resolveHostName}

        @param resolutionReceiver: see interface

        @param hostName: see interface

        @param portNumber: see interface

        @param addressTypes: see interface

        @param transportSemantics: see interface

        @return: see interface
        """
        pool = self._getThreadPool()
        addressFamily = _typesToAF[
            _any if addressTypes is None else frozenset(addressTypes)
        ]
        socketType = _transportToSocket[transportSemantics]

        resolution = HostResolution(hostName)

        async def resolveAndProcess() -> None:
            resolutionReceiver.resolutionBegan(resolution)
            try:
                names = await deferToThreadPool(
                    self._reactor,
                    pool,
                    self._getaddrinfo,
                    hostName,
                    portNumber,
                    addressFamily,
                    socketType,
                )
            except gaierror:
                names = []
            for family, socktype, proto, cannoname, sockaddr in names:
                addrType = _afToType[family]
                resolutionReceiver.addressResolved(
                    addrType(_socktypeToType.get(socktype, "TCP"), *sockaddr)
                )
            resolutionReceiver.resolutionComplete()

        Deferred.fromCoroutine(resolveAndProcess())
        return resolution


@implementer(IHostnameResolver)
class SimpleResolverComplexifier:
    """
    A converter from L{IResolverSimple} to L{IHostnameResolver}.
    """

    _log = Logger()

    def __init__(self, simpleResolver: IResolverSimple):
        """
        Construct a L{SimpleResolverComplexifier} with an L{IResolverSimple}.
        """
        self._simpleResolver = simpleResolver

    def resolveHostName(
        self,
        resolutionReceiver: IResolutionReceiver,
        hostName: str,
        portNumber: int = 0,
        addressTypes: Sequence[type[IAddress]] | None = None,
        transportSemantics: str = "TCP",
    ) -> IHostResolution:
        """
        See L{IHostnameResolver.resolveHostName}

        @param resolutionReceiver: see interface

        @param hostName: see interface

        @param portNumber: see interface

        @param addressTypes: see interface

        @param transportSemantics: see interface

        @return: see interface
        """
        # If it's str, we need to make sure that it's just ASCII.
        try:
            hostName_bytes = hostName.encode("ascii")
        except UnicodeEncodeError:
            # If it's not just ASCII, IDNA it. We don't want to give a Unicode
            # string with non-ASCII in it to Python 3, as if anyone passes that
            # to a Python 3 stdlib function, it will probably use the wrong
            # IDNA version and break absolutely everything
            hostName_bytes = _idnaBytes(hostName)

        # Make sure it's passed down as a native str, to maintain the interface
        hostName = nativeString(hostName_bytes)

        resolution = HostResolution(hostName)
        resolutionReceiver.resolutionBegan(resolution)
        (
            self._simpleResolver.getHostByName(hostName)
            .addCallback(
                lambda address: resolutionReceiver.addressResolved(
                    IPv4Address("TCP", address, portNumber)
                )
            )
            .addErrback(
                lambda error: (
                    None
                    if error.check(DNSLookupError)
                    else self._log.failure(
                        "while looking up {name} with {resolver}",
                        error,
                        name=hostName,
                        resolver=self._simpleResolver,
                    )
                )
            )
            .addCallback(lambda nothing: resolutionReceiver.resolutionComplete())
        )
        return resolution


@implementer(IResolutionReceiver)
class FirstOneWins:
    """
    An L{IResolutionReceiver} which fires a L{Deferred} with its first result.
    """

    def __init__(self, deferred: Deferred[str]):
        """
        @param deferred: The L{Deferred} to fire when the first resolution
            result arrives.
        """
        self._deferred = deferred
        self._resolved = False

    def resolutionBegan(self, resolution: IHostResolution) -> None:
        """
        See L{IResolutionReceiver.resolutionBegan}

        @param resolution: See L{IResolutionReceiver.resolutionBegan}
        """
        self._resolution = resolution

    def addressResolved(self, address: IAddress) -> None:
        """
        See L{IResolutionReceiver.addressResolved}

        @param address: See L{IResolutionReceiver.addressResolved}
        """
        if self._resolved:
            return
        self._resolved = True
        # This is used by ComplexResolverSimplifier which specifies only results
        # of IPv4Address.
        assert isinstance(address, IPv4Address)
        self._deferred.callback(address.host)

    def resolutionComplete(self) -> None:
        """
        See L{IResolutionReceiver.resolutionComplete}
        """
        if self._resolved:
            return
        self._deferred.errback(DNSLookupError(self._resolution.name))


@implementer(IResolverSimple)
class ComplexResolverSimplifier:
    """
    A converter from L{IHostnameResolver} to L{IResolverSimple}
    """

    def __init__(self, nameResolver: IHostnameResolver):
        """
        Create a L{ComplexResolverSimplifier} with an L{IHostnameResolver}.

        @param nameResolver: The L{IHostnameResolver} to use.
        """
        self._nameResolver = nameResolver

    def getHostByName(self, name: str, timeouts: Sequence[int] = ()) -> Deferred[str]:
        """
        See L{IResolverSimple.getHostByName}

        @param name: see L{IResolverSimple.getHostByName}

        @param timeouts: see L{IResolverSimple.getHostByName}

        @return: see L{IResolverSimple.getHostByName}
        """
        result: Deferred[str] = Deferred()
        self._nameResolver.resolveHostName(FirstOneWins(result), name, 0, [IPv4Address])
        return result
