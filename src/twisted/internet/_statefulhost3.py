# -*- test-case-name: twisted.internet.test.test_endpoints -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import count
from typing import (
    Callable,
    Dict,
    FrozenSet,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    TYPE_CHECKING,
    TypeVar,
)

from twisted.internet.address import HostnameAddress, IPv4Address, IPv6Address
from twisted.internet.defer import CancelledError, Deferred
from twisted.internet.error import ConnectingCancelledError, DNSLookupError
from twisted.internet.interfaces import (
    IAddress,
    IDelayedCall,
    IHostResolution,
    IProtocolFactory,
    IReactorTime,
    IResolutionReceiver,
    IStreamClientEndpoint,
    IStreamServerEndpoint,
)
from twisted.internet.protocol import Protocol as TwistedProtocol
from twisted.python.failure import Failure
from zope.interface import implementer
from ._shutil import CallWhenAll, Outstanding


if TYPE_CHECKING:
    from twisted.internet.endpoints import HostnameEndpoint


T = TypeVar("T")


class ConnectionFailedParts(Enum):
    ResolutionCompleted = auto()
    NoResolvedNamesToAttempt = auto()
    AllConnectionsFailed = auto()
    NotCancelled = auto()
    NotEstablished = auto()


@implementer(IResolutionReceiver)
@dataclass
class Resolution(object):
    allCall: CallWhenAll[ConnectionFailedParts]
    enq: Callable[[IAddress], None]
    inProgress: Optional[IHostResolution] = None
    everResolved: bool = False

    def resolutionBegan(self, resolutionInProgress: IHostResolution) -> None:
        """
        Name resolution has started.
        """
        self.inProgress = resolutionInProgress

    def addressResolved(self, address: IAddress) -> None:
        """
        An address was resolved.
        """
        self.everResolved = True
        self.enq(address)

    def resolutionComplete(self) -> None:
        """
        Name resolution is complete, no further names will be resolved.
        """
        self.inProgress = None
        self.allCall.add(ConnectionFailedParts.ResolutionCompleted)

    def cancel(self) -> None:
        if self.inProgress is not None:
            self.inProgress.cancel()


def addr2endpoint(
    hostnameEndpoint: HostnameEndpoint,
    address: IAddress,
) -> Optional[IStreamClientEndpoint]:
    """
    Convert an address into an endpoint
    """
    # Circular imports.
    from twisted.internet.endpoints import TCP6ClientEndpoint
    from twisted.internet.endpoints import TCP4ClientEndpoint

    reactor = hostnameEndpoint._reactor
    timeout = hostnameEndpoint._timeout
    bindAddress = hostnameEndpoint._bindAddress

    if isinstance(address, IPv6Address):
        return TCP6ClientEndpoint(
            reactor, address.host, address.port, timeout, bindAddress
        )
    if isinstance(address, IPv4Address):
        return TCP4ClientEndpoint(
            reactor, address.host, address.port, timeout, bindAddress
        )
    return None


@dataclass
class Attempts(object):
    """
    Object managing outgoing connection attempts.
    """

    protocolFactory: IProtocolFactory
    failer: CallWhenAll[ConnectionFailedParts]
    clock: IReactorTime
    attemptDelay: float
    established: Callable[[TwistedProtocol], None]
    lastAttemptTime: Optional[float] = None
    delayedCall: Optional[IDelayedCall] = None
    attemptsInProgress: Outstanding[TwistedProtocol] = field(
        default_factory=Outstanding
    )
    endpointQueue: List[IStreamClientEndpoint] = field(default_factory=list)
    failures: List[Failure] = field(default_factory=list)

    def invariants(self):
        self.failer.check(
            [
                (
                    self.attemptsInProgress.empty(),
                    ConnectionFailedParts.AllConnectionsFailed,
                ),
                (
                    not self.endpointQueue,
                    ConnectionFailedParts.NoResolvedNamesToAttempt,
                ),
            ]
        )

    def cancel(self) -> None:
        self.endpointQueue[:] = []
        self.invariants()
        self.attemptsInProgress.cancel()
        if self.delayedCall is not None:
            self.delayedCall.cancel()

    def attempt(self, endpoint: IStreamClientEndpoint) -> None:
        self.endpointQueue.append(endpoint)
        self.invariants()
        self.scheduleQueueDrain()

    def scheduleQueueDrain(self) -> None:
        if self.delayedCall is not None:
            # There is already a queue drain in progress; it'll keep going, so
            # never mind.
            return

        def drainQueue() -> None:
            self.delayedCall = None
            self.lastAttemptTime = self.clock.seconds()
            endpoint = self.endpointQueue.pop(0)
            if self.endpointQueue:
                self.scheduleQueueDrain()

            def maybeNoMoreConnections(result: T) -> T:
                if self.attemptsInProgress.empty() and self.endpointQueue:
                    if self.delayedCall is not None:
                        self.delayedCall.cancel()
                    drainQueue()
                else:
                    self.invariants()
                return result

            a = self.attemptsInProgress.add(endpoint.connect(self.protocolFactory))
            self.invariants()
            (
                a.addCallbacks(self.established, self.failures.append).addBoth(
                    maybeNoMoreConnections
                )
            )

        lastAttemptTime = self.lastAttemptTime
        now = self.clock.seconds()
        desiredDelay = (
            -1
            if lastAttemptTime is None
            else self.attemptDelay - (now - lastAttemptTime)
        )
        if desiredDelay <= 0:
            assert self.delayedCall is None
            drainQueue()
        else:
            assert self.delayedCall is None
            self.delayedCall = self.clock.callLater(
                desiredDelay,
                drainQueue,
            )


def start(
    hostnameEndpoint: HostnameEndpoint,
    protocolFactory: IProtocolFactory,
) -> Deferred[TwistedProtocol]:
    """
    do it
    """
    d: Deferred[TwistedProtocol]
    resolution: Resolution

    def determineFailure() -> Failure:
        if attempts.failures:
            return attempts.failures[0]
        else:
            return DNSLookupError(
                f"no results for hostname lookup: {hostnameEndpoint._hostStr}"
            )

    failer: CallWhenAll[ConnectionFailedParts] = CallWhenAll(
        lambda: d.errback(determineFailure()),
        frozenset(ConnectionFailedParts),
    )

    def cleanup() -> None:
        resolution.cancel()
        attempts.cancel()

    def cancel(d2: Deferred[TwistedProtocol]) -> None:
        failer.remove(ConnectionFailedParts.NotCancelled)
        cleanup()
        d.errback(
            ConnectingCancelledError(
                HostnameAddress(hostnameEndpoint._hostBytes, hostnameEndpoint._port)
            )
        )

    def established(result: TwistedProtocol) -> None:
        failer.remove(ConnectionFailedParts.NotCancelled)
        cleanup()
        d.callback(result)

    d = Deferred(cancel)

    failer.add(ConnectionFailedParts.NotCancelled)
    failer.add(ConnectionFailedParts.NotEstablished)
    # there are no un-failed connections, so at this point all connections have
    # failed, we'll clean it up
    failer.add(ConnectionFailedParts.AllConnectionsFailed)
    failer.add(ConnectionFailedParts.NoResolvedNamesToAttempt)

    attempts = Attempts(
        protocolFactory,
        failer,
        hostnameEndpoint._reactor,
        hostnameEndpoint._attemptDelay,
        established,
    )

    def enq(address: IAddress) -> None:
        newEndpoint = addr2endpoint(hostnameEndpoint, address)
        if newEndpoint is None:
            return
        attempts.attempt(newEndpoint)

    resolution = Resolution(failer, enq)

    hostnameEndpoint._nameResolver.resolveHostName(
        resolution,
        hostnameEndpoint._hostText,
        portNumber=hostnameEndpoint._port,
    )

    return d
