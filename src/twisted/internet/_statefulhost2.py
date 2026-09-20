from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Protocol, TypeVar

from zope.interface import implementer

from automat import TypeMachineBuilder

from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import Deferred as D
from twisted.internet.error import DNSLookupError
from twisted.internet.interfaces import (
    IAddress,
    IDelayedCall,
    IHostResolution,
    IProtocol,
    IProtocolFactory,
    IResolutionReceiver,
    IStreamClientEndpoint,
)
from twisted.internet.protocol import Protocol as TwistedProtocol
from twisted.python.failure import Failure

if TYPE_CHECKING:
    from twisted.internet.endpoints import HostnameEndpoint

T = TypeVar("T")


@implementer(IResolutionReceiver)
class CxnTry(Protocol):
    # IResolutionReceiver
    def resolutionBegan(self, resolutionInProgress: IHostResolution) -> None:
        ...

    def addressResolved(self, address: IAddress) -> None:
        ...

    def resolutionComplete(self) -> None:
        ...

    # Internal Methods
    def start(self) -> D[IProtocol]:
        ...

    def established(self, protocol: TwistedProtocol) -> None:
        ...

    def noPendingConnections(self) -> None:
        ...

    def userCancellation(self, deferred: D[IProtocol]) -> None:
        ...

    def attemptDelayExpired(self) -> None:
        ...


def addr2endpoint(
    hostnameEndpoint: HostnameEndpoint, address: IAddress
) -> IStreamClientEndpoint:
    # Circular imports.
    from twisted.internet.endpoints import TCP4ClientEndpoint, TCP6ClientEndpoint

    _endpoints = {IPv6Address: TCP6ClientEndpoint, IPv4Address: TCP4ClientEndpoint}
    assert isinstance(address, (IPv4Address, IPv6Address))
    return _endpoints[type(address)](
        hostnameEndpoint._reactor,
        address.host,
        address.port,
        hostnameEndpoint._timeout,
        hostnameEndpoint._bindAddress,
    )


@dataclass
class AttemptState:
    deferred: D[IProtocol]
    endpoint: HostnameEndpoint
    protocolFactory: IProtocolFactory
    lastAttemptTime: float = 0.0
    pendingCxnTrys: List[D[IProtocol]] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    nextAttemptCall: IDelayedCall | None = None
    resolutionInProgress: IHostResolution | None = None

    def oneAttemptLater(self, machine: CxnTry) -> None:
        def noneAndInput() -> None:
            self.nextAttemptCall = None
            machine.attemptDelayExpired()

        assert self.nextAttemptCall is None
        self.nextAttemptCall = self.endpoint._reactor.callLater(
            self.endpoint._attemptDelay
            - (self.endpoint._reactor.seconds() - self.lastAttemptTime),
            noneAndInput,
        )

    def queueOneAttempt(self, attempt: CxnTry, address: IAddress) -> None:
        def removePending(result: T) -> T:
            self.pendingCxnTrys.remove(connected)
            return result

        def maybeNoMoreConnections(result: object) -> None:
            if not self.pendingCxnTrys:
                attempt.noPendingConnections()

        self.lastAttemptTime = self.endpoint._reactor.seconds()
        endpoint = addr2endpoint(self.endpoint, address)
        connected = endpoint.connect(self.protocolFactory)
        self.pendingCxnTrys.append(connected)
        connected.addBoth(removePending)
        connected.addCallbacks(attempt.established, self.failures.append)
        connected.addBoth(maybeNoMoreConnections)


def rememberRes(
    attempt: CxnTry, core: AttemptState, resolutionInProgress: IHostResolution
) -> IHostResolution:
    return resolutionInProgress


def addressResolved(attempt: CxnTry, core: AttemptState, address: IAddress) -> None:
    core.queueOneAttempt(attempt, address)


# states
build = TypeMachineBuilder(CxnTry, AttemptState)
idle = build.state("idle")
"initial idle state"
awaitingResolution = build.state("awaitingResolution")
"resolveHostName has been called, but no names have yet been resolved"
noNamesYet = build.state("noNamesYet", rememberRes)
"resolutionBegan called on the resolution receiver, but no names yet"
resolvingWithPending = build.state("resolvingWithPending")
"at least one address has been resolved, and there are pending .connect() calls"
resolvingNames = build.state("resolvingNames")
"at least one address has been resolved, and there are no pending .connect() calls"
justPending = build.state("justPending")
"There are no queued connections right now, but there are pending ones."
justQueued = build.state("justQueued")
"There are no pending connections right now, but there are queued ones."
resolvingWithPendingAndQueued = build.state("resolvingWithPendingAndQueued")
pendingAndQueued = build.state("pendingAndQueued")
done = build.state("done")

awaitingResolution.upon(CxnTry.resolutionBegan).to(noNamesYet).returns(None)
resolvingNames.upon(CxnTry.resolutionComplete).to(done).returns(None)
resolvingNames.upon(CxnTry.addressResolved).to(resolvingNames)(addressResolved)
resolvingWithPending.upon(CxnTry.noPendingConnections).to(resolvingNames).returns(None)
justPending.upon(CxnTry.noPendingConnections).to(done).returns(None)
# FIXME
#     outputs=[connectionFailure],
justPending.upon(CxnTry.userCancellation).to(done).returns(None)
# FIXME
# outputs=[cancelOtherPending0, connectionFailure],
justPending.upon(CxnTry.established).to(done)
# FIXME
#     outputs=[cancelOtherPending1, complete],
justQueued.upon(CxnTry.moreQueuedEndpoints).to(
    pendingAndQueued,
    # FIXME
    # outputs=[oneAttemptLater0],
)
justQueued.upon(CxnTry.noPendingConnections).to(justQueued)
# FIXME
# outputs=[doOneAttempt0]
justQueued.upon(CxnTry.endpointQueueEmpty).to(justPending).returns(None)
resolvingWithPendingAndQueued.upon(CxnTry.endpointQueueEmpty).to(
    resolvingWithPending
).returns(None)
resolvingWithPendingAndQueued.upon(CxnTry.resolutionComplete).to(
    pendingAndQueued
).returns(None)
resolvingWithPendingAndQueued.upon(CxnTry.noPendingConnections).to(
    resolvingWithPendingAndQueued
).returns(None)
pendingAndQueued.upon(CxnTry.moreQueuedEndpoints).to(pendingAndQueued).returns(None)
# this one's a bit weird; the queued connection will inevitably _become_ a
# pending connection, so pendingAndQueued is still an appropriate state despite
# the lack of anything presently pending
pendingAndQueued.upon(CxnTry.noPendingConnections).to(justQueued)
# FIXME
# outputs=[cancelTimer0, doOneAttempt0],
done.upon(CxnTry.noPendingConnections).to(done).returns(None)
noNamesYet.upon(CxnTry.addressResolved).to(resolvingWithPending)(
    lambda attempt, core, resolution, address: addressResolved(attempt, core, address)
)
resolvingWithPending.upon(CxnTry.addressResolved).to(resolvingWithPendingAndQueued)(
    addressResolved
)


@idle.upon(CxnTry.start).to(awaitingResolution)
def doStart(attempt: CxnTry, core: AttemptState) -> D[IProtocol]:
    core.endpoint._getNameResolverAndMaybeWarn(core.endpoint._reactor).resolveHostName(
        attempt,
        core.endpoint._hostText,
        portNumber=core.endpoint._port,
    )
    core.deferred = D(attempt.userCancellation)
    return core.deferred


@noNamesYet.upon(CxnTry.resolutionComplete).to(done)
def completed(attempt: CxnTry, core: AttemptState, res: IHostResolution) -> None:
    e = DNSLookupError(f"no results for hostname lookup: {core.endpoint._hostText}")
    core.deferred.errback(e)


@noNamesYet.upon(CxnTry.userCancellation).to(done)
def cancel(
    attempt: CxnTry, core: AttemptState, res: IHostResolution, deferred: D[IProtocol]
) -> None:
    res.cancel()


CxnTryImpl = build.build()


def start(endpoint: HostnameEndpoint, pf: IProtocolFactory) -> D[IProtocol]:
    state = AttemptState(D(), endpoint, pf)
    return CxnTryImpl(state).start()
