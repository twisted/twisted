# -*- test-case-name: twisted.internet.test.test_endpoints -*-

from functools import wraps

from zope.interface import implementer

from automat import MethodicalMachine as _automat

from twisted.internet.address import HostnameAddress, IPv4Address, IPv6Address
from twisted.internet.defer import Deferred
from twisted.internet.error import ConnectingCancelledError, DNSLookupError
from twisted.internet.interfaces import IResolutionReceiver
from twisted.python.failure import Failure


class _FeedbackInput:
    """
    This feature really belongs in automat.
    """

    def __init__(self, machine):
        """ """
        self.machine = machine

    def __call__(self, method):
        """ """
        anInput = self.machine.input()(method)
        return _FeedbackInputOnClass(method, anInput)


class _FeedbackInputOnClass:

    """ """

    def __init__(self, function, input):
        """ """
        self.function = function
        self.input = input

    def __get__(self, oself, type=None):
        """ """
        theInput = self.input.__get__(oself, type)

        @wraps(self.function)
        def function(ooself, *a, **kw):
            wasProcessingFeedback = ooself._isProcessingFeedback
            ooself._isProcessingFeedback = True
            try:
                try:
                    if not wasProcessingFeedback:
                        assert getattr(ooself, "_pendingFeedback", None) is None
                        ooself._pendingFeedback = []
                    result = theInput(*a, **kw)
                    if not wasProcessingFeedback:
                        while ooself._pendingFeedback:
                            f = ooself._pendingFeedback.pop(0)
                            f()
                        assert not ooself._pendingFeedback
                    return result
                finally:
                    if not wasProcessingFeedback:
                        ooself._isProcessingFeedback = False
                        # assert not ooself._pendingFeedback, ooself._pendingFeedback
                        del ooself._pendingFeedback
            except:
                import traceback

                traceback.print_exc()
                raise

        function.input = theInput
        return function.__get__(oself, type)


@implementer(IResolutionReceiver)
class _HostnameConnectionAttempt:
    """ """

    machine = _automat()

    def __init__(self, hostnameEndpoint, protocolFactory):
        """ """
        self.hostnameEndpoint = hostnameEndpoint
        self.protocolFactory = protocolFactory
        self.deferred = Deferred(self.cancel)
        self.failures = []
        self._endpointQueue = []
        self._pendingConnectionAttempts = []
        self._isProcessingFeedback = False

    def cancel(self, deferred):
        """ """
        self.failures.append(
            ConnectingCancelledError(
                HostnameAddress(
                    self.hostnameEndpoint._hostBytes, self.hostnameEndpoint._port
                )
            )
        )
        self.userCancellation()

    @machine.state(initial=True)
    def _idle(self):
        """
        The idle state.
        """

    @machine.state()
    def _awaitingResolution(self):
        """
        Name resolution has been initiated but has not yet begun.
        """

    @machine.state()
    def _noNamesYet(self):
        """ """

    @machine.state()
    def _resolvingNames(self):
        """
        Name resolution is in progress.
        """

    @machine.state()
    def _resolvingWithPending(self):
        """
        Name resolution and an outgoing attempt are both in progress.
        """

    @machine.state()
    def _justPending(self):
        """
        Name resolution is done, but there are pending connection attempts.
        """

    @machine.state()
    def _justQueued(self):
        """
        There are no pending connections right now, but there are queued ones.
        """

    @machine.state()
    def _resolvingWithPendingAndQueued(self):
        """
        This is starting to look like a cartesian product...
        """

    @machine.state()
    def _pendingAndQueued(self):
        """
        There are pending connection attempts as well as queued connections.
        """

    @machine.state()
    def _done(self):
        """
        The operation is complete.
        """

    def feedback(self, thunk):
        """
        Outputs which want to produce an input to the same state machine can
        call this method to provide work to do after the currently queued list
        of state transitions is complete.
        """
        assert self._isProcessingFeedback
        self._pendingFeedback.append(thunk)

    @_FeedbackInput(machine)
    def start(self):
        """ """

    @_FeedbackInput(machine)
    def resolutionBegan(self, resolutionInProgress):
        """
        Hostname resolution began.
        """

    def addressResolved(self, address):
        """
        An address was resolved.
        """
        endpoint = self.addr2endpoint(address)
        if endpoint is not None:
            self.endpointResolved(endpoint)

    @_FeedbackInput(machine)
    def endpointResolved(self, endpoint):
        """
        An endpoint of a known type was resolved from an address.
        """

    @_FeedbackInput(machine)
    def resolutionComplete(self):
        """
        Hostname resolution was completed.
        """

    @_FeedbackInput(machine)
    def established(self, protocol):
        """
        A connection has been established.
        """

    @_FeedbackInput(machine)
    def oneAttemptFailed(self, reason):
        """
        A connection cannot be established
        """

    @_FeedbackInput(machine)
    def endpointQueueEmpty(self):
        """
        There are no more endpoints in the outbound queue.
        """

    @_FeedbackInput(machine)
    def noPendingConnections(self):
        """
        The last pending connection has terminated, in either success or
        failure.
        """

    @_FeedbackInput(machine)
    def userCancellation(self):
        """
        A user cancelled the outermost deferred.
        """

    @_FeedbackInput(machine)
    def attemptDelayExpired(self):
        """
        It's time to unqueue the next connection attempt.
        """

    @_FeedbackInput(machine)
    def moreQueuedEndpoints(self):
        """
        More endpoints remain in the queue.
        """

    def addr2endpoint(self, address):
        """
        Convert an address into an endpoint
        """
        from twisted.internet.endpoints import TCP4ClientEndpoint, TCP6ClientEndpoint

        reactor = self.hostnameEndpoint._reactor
        timeout = self.hostnameEndpoint._timeout
        bindAddress = self.hostnameEndpoint._bindAddress
        if isinstance(address, IPv6Address):
            return TCP6ClientEndpoint(
                reactor, address.host, address.port, timeout, bindAddress
            )
        if isinstance(address, IPv4Address):
            return TCP4ClientEndpoint(
                reactor, address.host, address.port, timeout, bindAddress
            )
        return None

    # --- Outputs ---

    @machine.output()
    def begin(self):
        """
        Start doing name resolution.
        """

        @self.feedback
        def doResolution():
            self.resolutionInProgress = (
                self.hostnameEndpoint._nameResolver.resolveHostName(
                    self,
                    self.hostnameEndpoint._hostText,
                    portNumber=self.hostnameEndpoint._port,
                )
            )

        return self.deferred

    @machine.output()
    def queueOneAttempt(self, endpoint):
        """
        Add an endpoint to the list of endpoints that we should still use.
        """
        self._endpointQueue.append(endpoint)

    @machine.output()
    def doOneAttempt(self, endpoint):
        """
        Make one outbound connection attempt right now.
        """
        self._doOneAttempt()

    @machine.output()
    def doOneAttempt0(self):
        """
        Same.
        """
        self._doOneAttempt()

    def _doOneAttempt(self):
        """ """
        self.lastAttemptTime = self.hostnameEndpoint._reactor.seconds()

        @self.feedback
        def oneAttempt():
            endpoint = self._endpointQueue.pop(0)
            if not self._endpointQueue:
                self.endpointQueueEmpty()
            else:
                self.moreQueuedEndpoints()

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

    @machine.output()
    def oneAttemptLater(self, endpoint):
        """ """
        self._oneAttemptLater()

    @machine.output()
    def oneAttemptLater0(self):
        """ """
        self._oneAttemptLater()

    nextAttemptCall = None

    def _oneAttemptLater(self):
        """ """
        assert self.nextAttemptCall is None

        def noneAndInput():
            self.nextAttemptCall = None
            self.attemptDelayExpired()

        self.nextAttemptCall = self.hostnameEndpoint._reactor.callLater(
            self.hostnameEndpoint._attemptDelay
            - (self.hostnameEndpoint._reactor.seconds() - self.lastAttemptTime),
            noneAndInput,
        )

    @machine.output()
    def cancelTimer(self, protocol):
        """ """
        call = self.nextAttemptCall
        self.nextAttemptCall = None
        self.feedback(call.cancel)

    @machine.output()
    def cancelTimer0(self):
        """ """
        call = self.nextAttemptCall
        self.nextAttemptCall = None
        self.feedback(call.cancel)

    @machine.output()
    def cancelResolution1(self, protocol):
        """ """
        self.cancelResolution0()

    @machine.output()
    def cancelResolution0(self):
        """ """
        self.resolutionInProgress.cancel()

    @machine.output()
    def cancelOtherPending1(self, protocol):
        """ """
        self.feedback(self.cancelOtherPending)

    @machine.output()
    def cancelOtherPending0(self):
        """ """
        self.feedback(self.cancelOtherPending)

    def cancelOtherPending(self):
        """ """
        while self._pendingConnectionAttempts:
            self._pendingConnectionAttempts[0].cancel()

    @machine.output()
    def complete(self, protocol):
        """ """
        self.feedback(lambda: self.deferred.callback(protocol))

    @machine.output()
    def connectionFailure(self):
        """ """
        self.deferred.errback(self.failures.pop())

    @machine.output()
    def resolutionFailure(self):
        """
        Name resolution yielded no results.
        """
        self.deferred.errback(
            Failure(
                DNSLookupError(
                    "no results for hostname lookup: {}".format(
                        self.hostnameEndpoint._hostStr
                    )
                )
            )
        )

    _idle.upon(
        start.input,
        enter=_awaitingResolution,
        outputs=[begin],
        collector=lambda gen: next(iter(list(gen))),
    )

    _awaitingResolution.upon(resolutionBegan.input, enter=_noNamesYet, outputs=[])

    _noNamesYet.upon(
        endpointResolved.input,
        enter=_resolvingWithPending,
        outputs=[queueOneAttempt, doOneAttempt],
    )
    _noNamesYet.upon(
        resolutionComplete.input,
        enter=_done,
        outputs=[resolutionFailure],
    )
    _noNamesYet.upon(userCancellation.input, enter=_done, outputs=[cancelResolution0])

    _resolvingNames.upon(
        endpointResolved.input,
        enter=_resolvingWithPending,
        outputs=[queueOneAttempt, doOneAttempt],
    )
    _resolvingNames.upon(
        resolutionComplete.input,
        enter=_done,
        outputs=[connectionFailure],
    )

    _resolvingWithPending.upon(
        noPendingConnections.input,
        enter=_resolvingNames,
        outputs=[],
    )
    _resolvingWithPending.upon(
        endpointResolved.input,
        enter=_resolvingWithPendingAndQueued,
        outputs=[queueOneAttempt, oneAttemptLater],
    )
    _resolvingWithPending.upon(
        endpointQueueEmpty.input,
        enter=_resolvingWithPending,
        outputs=[],
    )

    _resolvingWithPendingAndQueued.upon(
        endpointQueueEmpty.input, enter=_resolvingWithPending, outputs=[]
    )
    _resolvingWithPendingAndQueued.upon(
        resolutionComplete.input, enter=_pendingAndQueued, outputs=[]
    )
    _resolvingWithPendingAndQueued.upon(
        noPendingConnections.input, enter=_resolvingWithPendingAndQueued, outputs=[]
    )

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

    _resolvingWithPendingAndQueued.upon(
        endpointResolved.input,
        enter=_resolvingWithPendingAndQueued,
        outputs=[queueOneAttempt],
    )
    _resolvingWithPendingAndQueued.upon(
        established.input,
        enter=_done,
        outputs=[cancelResolution1, cancelOtherPending1, cancelTimer, complete],
        collector=list,
    )
    _resolvingWithPendingAndQueued.upon(
        attemptDelayExpired.input, enter=_resolvingWithPending, outputs=[doOneAttempt0]
    )

    _pendingAndQueued.upon(
        attemptDelayExpired.input, enter=_pendingAndQueued, outputs=[doOneAttempt0]
    )
    _pendingAndQueued.upon(endpointQueueEmpty.input, enter=_justPending, outputs=[])
    _pendingAndQueued.upon(
        established.input,
        enter=_done,
        outputs=[cancelOtherPending1, cancelTimer, complete],
        collector=list,
    )

    _resolvingWithPending.upon(
        established.input, enter=_done, outputs=[cancelResolution1, complete]
    )
    _resolvingWithPending.upon(
        resolutionComplete.input,
        enter=_justPending,
        outputs=[],
    )

    _justPending.upon(
        moreQueuedEndpoints.input,
        enter=_pendingAndQueued,
        outputs=[
            oneAttemptLater0,
        ],
    )
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

    _done.upon(noPendingConnections.input, enter=_done, outputs=[], collector=list)
