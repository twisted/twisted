from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Protocol, TypeVar

from zope.interface import implementer

from automat import TypeMachineBuilder

from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import Deferred
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
class ConnectionAttempt(Protocol):
    """ """

    def start(self) -> Deferred[IProtocol]:
        """
        Begin the connection attempt.
        """

    def cancel(self) -> None:
        """
        A user requested cancellation
        """

    def attemptTimeoutExpired(self) -> None:
        """
        We have been attempting to connect for too long.
        """

    # IResolutionReceiver
    def resolutionBegan(self, resolutionInProgress: IHostResolution) -> None:
        """ """

    def addressResolved(self, address: IAddress) -> None:
        # endpointResolved skipped because we're handling this directly as an input
        """ """

    def resolutionComplete(self) -> None:
        """ """

    def established(self, protocol: TwistedProtocol) -> None:
        """ """

    def oneAttemptFailed(self, reason: Failure) -> None:
        """
        A connection cannot be established
        """

    def endpointQueueEmpty(self) -> None:
        """
        There are no more endpoints in the outbound queue.
        """

    def noPendingConnections(self) -> None:
        """
        The last pending connection has terminated, in either success or
        failure.
        """

    # def userCancellation(self):
    #     """
    #     A user cancelled the outermost deferred.
    #     """
    # now handled by .cancel()

    def attemptDelayExpired(self) -> None:
        """
        It's time to unqueue the next connection attempt.
        """

    def moreQueuedEndpoints(self) -> None:
        """
        More endpoints remain in the queue.
        """


def addr2endpoints(
    hostnameEndpoint: HostnameEndpoint, address: IAddress
) -> Iterable[IStreamClientEndpoint]:
    """
    Convert an address into an endpoint
    """
    # Circular imports.
    from twisted.internet.endpoints import TCP4ClientEndpoint, TCP6ClientEndpoint

    reactor = hostnameEndpoint._reactor
    timeout = hostnameEndpoint._timeout
    bindAddress = hostnameEndpoint._bindAddress

    if isinstance(address, IPv6Address):
        yield TCP6ClientEndpoint(
            reactor, address.host, address.port, timeout, bindAddress
        )
    if isinstance(address, IPv4Address):
        yield TCP4ClientEndpoint(
            reactor, address.host, address.port, timeout, bindAddress
        )


@dataclass
class ConnectionAttemptCore:
    """
    Automat state core for a single in-progress call to HostnameEndpoint.connect()
    """

    # this is only ever un-set in Idle state. Should this even be a state,
    # then, or just a construction parameter?
    deferred: Deferred[IProtocol]

    # provide for feedback.  TODO: can the framework do this and auto-populate
    # such an annotation?
    machine: ConnectionAttempt

    endpoint: HostnameEndpoint
    endpointQueue: list[IStreamClientEndpoint]
    pendingConnectionAttempts: List[Deferred[IProtocol]]
    lastAttemptTime: float
    protocolFactory: IProtocolFactory
    failures: list[Failure]
    nextAttemptCall: Optional[IDelayedCall] = None
    resolutionInProgress: IHostResolution | None = None

    @property
    def reactor(self) -> Any:
        return self.endpoint._reactor

    def oneAttemptLater(self) -> None:
        assert self.nextAttemptCall is None

        def noneAndInput() -> None:
            self.nextAttemptCall = None
            self.machine.attemptDelayExpired()

        self.nextAttemptCall = self.endpoint._reactor.callLater(
            self.endpoint._attemptDelay
            - (self.endpoint._reactor.seconds() - self.lastAttemptTime),
            noneAndInput,
        )

    def resolutionFailure(self) -> None:
        """
        Name resolution failed.
        """
        self.deferred.errback(
            Failure(
                DNSLookupError(
                    f"no results for hostname lookup: {self.endpoint._hostText}"
                )
            )
        )

    def queueOneAttempt(self, address: IAddress) -> None:
        """
        Add an endpoint to the list of endpoints that we should still use.
        """
        self.endpointQueue.extend(addr2endpoints(self.endpoint, address))

    def doOneAttempt(self) -> None:
        """
        Perform an attempt, draining the queue.
        """
        self.lastAttemptTime = self.endpoint._reactor.seconds()
        endpoint = self.endpointQueue.pop(0)
        if not self.endpointQueue:
            self.machine.endpointQueueEmpty()
        else:
            self.machine.moreQueuedEndpoints()
        connected = endpoint.connect(self.protocolFactory)
        self.pendingConnectionAttempts.append(connected)

        def removePending(result: T) -> T:
            self.pendingConnectionAttempts.remove(connected)
            return result

        connected.addBoth(removePending)
        connected.addCallbacks(self.machine.established, self.failures.append)

        def maybeNoMoreConnections(result: object) -> None:
            if not self.pendingConnectionAttempts:
                self.machine.noPendingConnections()

        connected.addBoth(maybeNoMoreConnections)


ConnectionAttemptImpl: TypeMachineBuilder[
    ConnectionAttempt, ConnectionAttemptCore
] = TypeMachineBuilder(ConnectionAttempt, ConnectionAttemptCore)


idle = ConnectionAttemptImpl.state("idle")
awaitingResolution = ConnectionAttemptImpl.state("awaitingResolution")


def rememberResolution(
    attempt: ConnectionAttempt,
    core: ConnectionAttemptCore,
    resolutionInProgress: IHostResolution,
) -> IHostResolution:
    return resolutionInProgress


noNamesYet = ConnectionAttemptImpl.state("noNamesYet", rememberResolution)
resolvingWithPending = ConnectionAttemptImpl.state("resolvingWithPending")
done = ConnectionAttemptImpl.state("done")
justPending = ConnectionAttemptImpl.state("justPending")
resolvingNames = ConnectionAttemptImpl.state("resolvingNames")
justPending = ConnectionAttemptImpl.state("justPending")
"There are no queued connections right now, but there are pending ones."
justQueued = ConnectionAttemptImpl.state("justQueued")
"There are no pending connections right now, but there are queued ones."
resolvingWithPendingAndQueued = ConnectionAttemptImpl.state(
    "resolvingWithPendingAndQueued"
)


@idle.upon(ConnectionAttempt.start).to(awaitingResolution)
def start(
    attempt: ConnectionAttempt, core: ConnectionAttemptCore
) -> Deferred[IProtocol]:
    """
    Start the resolution process.
    """
    core.endpoint._getNameResolverAndMaybeWarn(core.reactor).resolveHostName(
        core.machine,
        core.endpoint._hostText,
        portNumber=core.endpoint._port,
    )
    core.deferred = Deferred()
    return core.deferred


awaitingResolution.upon(ConnectionAttempt.resolutionBegan).to(noNamesYet).returns(None)


def resolutionBegan(
    attempt: ConnectionAttempt,
    core: ConnectionAttemptCore,
    resolutionInProgress: IHostResolution,
) -> None:
    "Resolution began, we don't need to do anything."


@noNamesYet.upon(ConnectionAttempt.addressResolved).to(resolvingWithPending)
def addressResolvedInProgress(
    attempt: ConnectionAttempt,
    core: ConnectionAttemptCore,
    resolutionInProgress: IHostResolution,
    address: IAddress,
) -> None:
    core.queueOneAttempt(address)
    core.doOneAttempt()


@resolvingWithPending.upon(ConnectionAttempt.addressResolved).to(
    resolvingWithPendingAndQueued
)
def addressResolved(
    attempt: ConnectionAttempt, core: ConnectionAttemptCore, address: IAddress
) -> None:
    core.queueOneAttempt(address)
    core.doOneAttempt()


@noNamesYet.upon(ConnectionAttempt.resolutionComplete).to(done)
def resolutionComplete(
    attempt: ConnectionAttempt,
    core: ConnectionAttemptCore,
    resolutionInProgress: IHostResolution,
) -> None:
    core.resolutionFailure()


@noNamesYet.upon(ConnectionAttempt.cancel).to(done)
def cancel(
    attempt: ConnectionAttempt,
    core: ConnectionAttemptCore,
    resolutionInProgress: IHostResolution,
) -> None:
    resolutionInProgress.cancel()


@resolvingNames.upon(ConnectionAttempt.addressResolved).to(resolvingNames)
def resolvedWhileResolving(
    attempt: ConnectionAttempt, core: ConnectionAttemptCore, address: IAddress
) -> None:
    core.queueOneAttempt(address)
    core.doOneAttempt()


resolvingNames.upon(ConnectionAttempt.resolutionComplete).to(done).returns(None)

resolvingWithPending.upon(ConnectionAttempt.noPendingConnections).to(
    resolvingNames
).returns(None)
"No pending connections remain. Transition to Resolving only."


resolvingWithPending.upon(ConnectionAttempt.endpointQueueEmpty).to(
    resolvingWithPending
).returns(None)
"""
Endpoint queue empty; transition to resolving-with-pending only and do
nothing.
"""


justPending.upon(
    endpointQueueEmpty.input,
    enter=justPending,
    outputs=[],
)
justPending.upon(
    noPendingConnections.input,
    enter=_done,
    outputs=[connectionFailure],
    collector=list,
)

justPending.upon(
    userCancellation.input,
    enter=_done,
    outputs=[cancelOtherPending0, connectionFailure],
)
justPending.upon(
    established.input,
    enter=_done,
    outputs=[cancelOtherPending1, complete],
    collector=list,
)


@ConnectionAttemptImpl.state
class JustQueued:
    _justQueued.upon(
        moreQueuedEndpoints.input,
        enter=_pendingAndQueued,
        outputs=[oneAttemptLater0],
        collector=list,
    )
    _justQueued.upon(
        noPendingConnections.input, enter=_justQueued, outputs=[doOneAttempt0]
    )
    _justQueued.upon(endpointQueueEmpty.input, enter=justPending, outputs=[])


@ConnectionAttemptImpl.state
class ResolvingWithPendingAndQueued:
    """
    This is starting to look like a cartesian product...
    """

    _resolvingWithPendingAndQueued.upon(
        endpointQueueEmpty.input, enter=_resolvingWithPending, outputs=[]
    )
    _resolvingWithPendingAndQueued.upon(
        resolutionComplete.input, enter=_pendingAndQueued, outputs=[]
    )
    _resolvingWithPendingAndQueued.upon(
        noPendingConnections.input, enter=_resolvingWithPendingAndQueued, outputs=[]
    )


@ConnectionAttemptImpl.state
class PendingAndQueued:
    """
    There are pending connection attempts as well as queued connections.
    """

    _pendingAndQueued.upon(
        moreQueuedEndpoints.input, enter=_pendingAndQueued, outputs=[]
    )
    # this one's a bit weird; the queued connection will inevitably _become_ a
    # pending connection, so _pendingAndQueued is still an appropriate state
    # despite the lack of anything presently pending
    _pendingAndQueued.upon(
        noPendingConnections.input,
        enter=_justQueued,
        outputs=[cancelTimer0, doOneAttempt0],
        collector=list,
    )


@ConnectionAttemptImpl.state
class Done:
    """
    The operation is complete.
    """

    _done.upon(noPendingConnections.input, enter=_done, outputs=[], collector=list)


ConnectionAttempter = ConnectionAttemptImpl.build()


def new(hostnameEndpoint: HostnameEndpoint) -> ConnectionAttempt:
    """ """
    return ConnectionAttempter(ConnectionAttemptCore())
