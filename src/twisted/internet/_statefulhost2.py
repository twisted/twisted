from dataclasses import dataclass
from typing import List, Optional, Protocol, TYPE_CHECKING

from automat import TypicalMachine

from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import Deferred
from twisted.internet.error import DNSLookupError
from twisted.internet.interfaces import IAddress, IDelayedCall, IHostResolution, IResolutionReceiver, IStreamClientEndpoint
from twisted.internet.protocol import Protocol as TwistedProtocol
from twisted.python.failure import Failure
from zope.interface import implementer


if TYPE_CHECKING:
    from twisted.internet.endpoints import HostnameEndpoint


@implementer(IResolutionReceiver)
class ConnectionAttempt(Protocol):
    """ """

    def start(self) -> None:
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

    def oneAttemptFailed(self, reason):
        """
        A connection cannot be established
        """

    def endpointQueueEmpty(self):
        """
        There are no more endpoints in the outbound queue.
        """

    def noPendingConnections(self):
        """
        The last pending connection has terminated, in either success or
        failure.
        """

    # def userCancellation(self):
    #     """
    #     A user cancelled the outermost deferred.
    #     """
    # now handled by .cancel()

    def attemptDelayExpired(self):
        """
        It's time to unqueue the next connection attempt.
        """

    def moreQueuedEndpoints(self):
        """
        More endpoints remain in the queue.
        """


def addr2endpoint(
    hostnameEndpoint: HostnameEndpoint,
    address: IAddress,
) -> None:
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


class ConnectionAttemptCore:
    """ """

    # this is only ever un-set in Idle state. Should this even be a state,
    # then, or just a construction parameter?
    deferred: Deferred[TwistedProtocol]

    # provide for feedback.  TODO: can the framework do this and auto-populate
    # such an annotation?
    machine: ConnectionAttempt

    # populated by _cooperateWithNew's argument
    endpoint: HostnameEndpoint

    # constructed by _cooperateWithNew
    endpointQueue: List[IStreamClientEndpoint]
    pendingConnectionAttempts: List[Deferred[TwistedProtocol]]
    lastAttemptTime: float
    nextAttemptCall: Optional[IDelayedCall] = None

    def oneAttemptLater(self) -> None:
        assert self.nextAttemptCall is None
        def noneAndInput() -> None:
            self.nextAttemptCall = None
            self.machine.attemptDelayExpired()

        self.nextAttemptCall = self.endpoint._reactor.callLater(
            self.endpoint._attemptDelay -
            (self.endpoint._reactor.seconds() - self.lastAttemptTime),
            noneAndInput
        )

    def resolutionFailure(self) -> None:
        """ """
        self.deferred.errback(
            Failure(
                DNSLookupError(
                    "no results for hostname lookup: {}".format(self.endpoint._hostStr)
                )
            )
        )

    def queueOneAttempt(self, address: IStreamClientEndpoint) -> None:
        """
        Add an endpoint to the list of endpoints that we should still use.
        """
        self._endpointQueue.append(addr2endpoint(self.endpoint, address))

    def doOneAttempt(self) -> None:
        """
        Perform an attempt, draining the queue.
        """
        self.lastAttemptTime = self.endpoint._reactor.seconds()
        endpoint = self._endpointQueue.pop(0)
        if not self._endpointQueue:
            self.machine.endpointQueueEmpty()
        else:
            self.machine.moreQueuedEndpoints()
        connected = endpoint.connect(self.protocolFactory)
        self._pendingConnectionAttempts.append(connected)

        def removePending(result):
            self._pendingConnectionAttempts.remove(connected)
            return result

        connected.addBoth(removePending)
        connected.addCallbacks(self.established, self.failures.append)

        def maybeNoMoreConnections(result):
            if not self._pendingConnectionAttempts:
                self.noPendingConnections()

        connected.addBoth(maybeNoMoreConnections)


def _cooperateWithNew(
    capture: List[ConnectionAttemptCore], endpoint: HostnameEndpoint
) -> ConnectionAttemptCore:
    """ """
    self = ConnectionAttemptCore()
    self.endpoint = endpoint
    self.endpointQueue = []
    self.pendingConnectionAttempts = []
    capture.append(self)
    return self


ConnectionAttemptImpl: TypicalMachine[
    ConnectionAttempt, ConnectionAttemptCore
] = TypicalMachine(_cooperateWithNew)


def new(hostnameEndpoint: HostnameEndpoint):
    """ """
    x = []
    # TODO: typecheck `build`?
    impl = ConnectionAttemptImpl.build(x, hostnameEndpoint)
    x[0].machine = impl
    return impl


@ConnectionAttemptImpl.state
class Idle(object):
    """
    We are idling, nothing has started yet.
    """

    core: ConnectionAttemptCore

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.start, enter=lambda: AwaitingResolution
    )
    def start(self) -> Deferred[TwistedProtocol]:
        """
        Start the resolution process.
        """
        self.core.resolutionInProgress = (
            self.core.hostnameEndpoint._nameResolver.resolveHostName(
                self.core.machine,
                self.core.hostnameEndpoint._hostText,
                portNumber=self.core.hostnameEndpoint._port,
            )
        )
        it = self.core.deferred = Deferred()
        return it


@ConnectionAttemptImpl.state
class AwaitingResolution(object):
    """
    We just started, and now we're waiting for hostnames to begin.
    """

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.resolutionBegan, enter=lambda: NoNamesYet
    )
    def resolutionBegan(self, resolutionInProgress: IHostResolution) -> None:
        """
        Resolution began, we don't need to do anything.
        """


@dataclass
@ConnectionAttemptImpl.state
class NoNamesYet(object):
    """ """

    core: ConnectionAttemptCore

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.addressResolved, enter=lambda: ResolvingWithPending
    )
    def addressResolved(self, address: IAddress) -> None:
        self.core.queueOneAttempt(address)
        self.core.doOneAttempt()

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.resolutionComplete,
        enter=lambda: Done,
    )
    def resolutionComplete(self) -> None:
        return self.core.resolutionFailure()

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.cancel,
        enter=lambda: Done,
    )
    def cancel(self) -> None:
        self.core.resolutionInProgress.cancel()


@ConnectionAttemptImpl.state
class ResolvingNames(object):
    """ """

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.addressResolved, enter=lambda: ResolvingWithPending
    )
    def addressResolved(self, address: IAddress) -> None:
        self.core.queueOneAttempt(address)
        self.core.doOneAttempt()

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.resolutionComplete,
        enter=lambda: Done,
    )
    def resolutionComplete(self) -> None:
        self.core.connectionFailure()


@ConnectionAttemptImpl.state
class ResolvingWithPending(object):
    """
    We are in the middle of resolving names, and also we have several pending
    connections.
    """

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.noPendingConnections,
        enter=lambda: ResolvingNames,
    )
    def noPendingConnections(self) -> None:
        """
        No pending connections remain. Transition to Resolving only.
        """

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.addressResolved,
        enter=lambda: ResolvingWithPendingAndQueued,
    )
    def addressResolved(self, address: IAddress) -> None:
        self.core.queueOneAttempt(address)
        self.core.doOneAttempt()

    @ConnectionAttemptImpl.handle(
        ConnectionAttempt.endpointQueueEmpty,
        enter=lambda: ResolvingWithPending,
    )
    def endpointQueueEmpty(self) -> None:
        """
        Endpoint queue empty; transition to resolving-with-pending only and do
        nothing.
        """


@ConnectionAttemptImpl.state
class JustPending:
    """
    Name resolution is done, but there are pending connection attempts.
    """

    # _justPending.upon(
    #     moreQueuedEndpoints.input,
    #     enter=_pendingAndQueued,
    #     outputs=[
    #         oneAttemptLater0,
    #     ],
    # )
    def moreQueuedEndpoints(self) -> None:
        """
        
        """
        


    _justPending.upon(
        endpointQueueEmpty.input,
        enter=_justPending,
        outputs=[],
    )
    _justPending.upon(
        noPendingConnections.input,
        enter=_done,
        outputs=[connectionFailure],
        collector=list,
    )

    _justPending.upon(
        userCancellation.input,
        enter=_done,
        outputs=[cancelOtherPending0, connectionFailure],
    )
    _justPending.upon(
        established.input,
        enter=_done,
        outputs=[cancelOtherPending1, complete],
        collector=list,
    )


@ConnectionAttemptImpl.state
class JustQueued:
    """
    There are no pending connections right now, but there are queued ones.
    """

    _justQueued.upon(
        moreQueuedEndpoints.input,
        enter=_pendingAndQueued,
        outputs=[oneAttemptLater0],
        collector=list,
    )
    _justQueued.upon(
        noPendingConnections.input, enter=_justQueued, outputs=[doOneAttempt0]
    )
    _justQueued.upon(endpointQueueEmpty.input, enter=_justPending, outputs=[])


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
