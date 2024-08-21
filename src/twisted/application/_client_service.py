# -*- test-case-name: twisted.application.test.test_internet,twisted.test.test_application,twisted.test.test_cooperator -*-

"""
Implementation of L{twisted.application.internet.ClientService}, particularly
its U{automat <https://automat.readthedocs.org/>} state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import random as _goodEnoughRandom
from typing import Callable, Optional, Protocol as TypingProtocol, TypeVar, Union

from zope.interface import implementer

from automat import TypeMachineBuilder, pep614

from twisted.application.service import Service
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    fail,
    maybeDeferred,
    succeed,
)
from twisted.internet.interfaces import (
    IAddress,
    IDelayedCall,
    IProtocol,
    IProtocolFactory,
    IReactorTime,
    IStreamClientEndpoint,
    ITransport,
)
from twisted.logger import Logger
from twisted.python.failure import Failure

T = TypeVar("T")


def _maybeGlobalReactor(maybeReactor: Optional[T]) -> T:
    """
    @return: the argument, or the global reactor if the argument is L{None}.
    """
    if maybeReactor is None:
        from twisted.internet import reactor

        return reactor  # type:ignore[return-value]
    else:
        return maybeReactor


class _Client(TypingProtocol):
    def start(self) -> None:
        """
        Start this L{ClientService}, initiating the connection retry loop.
        """

    def stop(self) -> Deferred[None]:
        """
        Stop trying to connect and disconnect any current connection.

        @return: a L{Deferred} that fires when all outstanding connections are
            closed and all in-progress connection attempts halted.
        """

    def _connectionMade(self, protocol: _ReconnectingProtocolProxy) -> None:
        """
        A connection has been made.

        @param protocol: The protocol of the connection.
        """

    def _connectionFailed(self, failure: Failure) -> None:
        """
        Deliver connection failures to any L{ClientService.whenConnected}
        L{Deferred}s that have met their failAfterFailures threshold.

        @param failure: the Failure to fire the L{Deferred}s with.
        """

    def _reconnect(self, failure: Optional[Failure] = None) -> None:
        """
        The wait between connection attempts is done.
        """

    def _clientDisconnected(self, failure: Optional[Failure] = None) -> None:
        """
        The current connection has been disconnected.
        """

    def whenConnected(
        self, /, failAfterFailures: Optional[int] = None
    ) -> Deferred[IProtocol]:
        """
        Retrieve the currently-connected L{Protocol}, or the next one to
        connect.

        @param failAfterFailures: number of connection failures after which the
            Deferred will deliver a Failure (None means the Deferred will only
            fail if/when the service is stopped).  Set this to 1 to make the
            very first connection failure signal an error.  Use 2 to allow one
            failure but signal an error if the subsequent retry then fails.

        @return: a Deferred that fires with a protocol produced by the factory
            passed to C{__init__}.  It may:

                - fire with L{IProtocol}

                - fail with L{CancelledError} when the service is stopped

                - fail with e.g.
                  L{DNSLookupError<twisted.internet.error.DNSLookupError>} or
                  L{ConnectionRefusedError<twisted.internet.error.ConnectionRefusedError>}
                  when the number of consecutive failed connection attempts
                  equals the value of "failAfterFailures"
        """


@implementer(IProtocol)
class _ReconnectingProtocolProxy:
    """
    A proxy for a Protocol to provide connectionLost notification to a client
    connection service, in support of reconnecting when connections are lost.
    """

    def __init__(
        self, protocol: IProtocol, lostNotification: Callable[[Failure], None]
    ) -> None:
        """
        Create a L{_ReconnectingProtocolProxy}.

        @param protocol: the application-provided L{interfaces.IProtocol}
            provider.
        @type protocol: provider of L{interfaces.IProtocol} which may
            additionally provide L{interfaces.IHalfCloseableProtocol} and
            L{interfaces.IFileDescriptorReceiver}.

        @param lostNotification: a 1-argument callable to invoke with the
            C{reason} when the connection is lost.
        """
        self._protocol = protocol
        self._lostNotification = lostNotification

    def makeConnection(self, transport: ITransport) -> None:
        self._transport = transport
        self._protocol.makeConnection(transport)

    def connectionLost(self, reason: Failure) -> None:
        """
        The connection was lost.  Relay this information.

        @param reason: The reason the connection was lost.

        @return: the underlying protocol's result
        """
        try:
            return self._protocol.connectionLost(reason)
        finally:
            self._lostNotification(reason)

    def __getattr__(self, item: str) -> object:
        return getattr(self._protocol, item)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} wrapping {self._protocol!r}>"


@implementer(IProtocolFactory)
class _DisconnectFactory:
    """
    A L{_DisconnectFactory} is a proxy for L{IProtocolFactory} that catches
    C{connectionLost} notifications and relays them.
    """

    def __init__(
        self,
        protocolFactory: IProtocolFactory,
        protocolDisconnected: Callable[[Failure], None],
    ) -> None:
        self._protocolFactory = protocolFactory
        self._protocolDisconnected = protocolDisconnected

    def buildProtocol(self, addr: IAddress) -> Optional[IProtocol]:
        """
        Create a L{_ReconnectingProtocolProxy} with the disconnect-notification
        callback we were called with.

        @param addr: The address the connection is coming from.

        @return: a L{_ReconnectingProtocolProxy} for a protocol produced by
            C{self._protocolFactory}
        """
        built = self._protocolFactory.buildProtocol(addr)
        if built is None:
            return None
        return _ReconnectingProtocolProxy(built, self._protocolDisconnected)

    def __getattr__(self, item: str) -> object:
        return getattr(self._protocolFactory, item)

    def __repr__(self) -> str:
        return "<{} wrapping {!r}>".format(
            self.__class__.__name__, self._protocolFactory
        )


def _deinterface(o: object) -> None:
    """
    Remove the special runtime attributes set by L{implementer} so that a class
    can proxy through those attributes with C{__getattr__} and thereby forward
    optionally-provided interfaces by the delegated class.
    """
    for zopeSpecial in ["__providedBy__", "__provides__", "__implemented__"]:
        delattr(o, zopeSpecial)


_deinterface(_DisconnectFactory)
_deinterface(_ReconnectingProtocolProxy)


@dataclass
class _Core:
    """
    Shared core for ClientService state machine.
    """

    # required parameters
    endpoint: IStreamClientEndpoint
    factory: IProtocolFactory
    timeoutForAttempt: Callable[[int], float]
    clock: IReactorTime
    prepareConnection: Optional[Callable[[IProtocol], object]]

    # internal state
    stopWaiters: list[Deferred[None]] = field(default_factory=list)
    awaitingConnected: list[tuple[Deferred[IProtocol], Optional[int]]] = field(
        default_factory=list
    )
    failedAttempts: int = 0
    log: Logger = Logger()

    def waitForStop(self) -> Deferred[None]:
        self.stopWaiters.append(Deferred())
        return self.stopWaiters[-1]

    def unawait(self, value: Union[IProtocol, Failure]) -> None:
        self.awaitingConnected, waiting = [], self.awaitingConnected
        for w, remaining in waiting:
            w.callback(value)

    def cancelConnectWaiters(self) -> None:
        self.unawait(Failure(CancelledError()))

    def finishStopping(self) -> None:
        self.stopWaiters, waiting = [], self.stopWaiters
        for w in waiting:
            w.callback(None)


def makeMachine() -> Callable[[_Core], _Client]:
    machine = TypeMachineBuilder(_Client, _Core)

    def waitForRetry(
        c: _Client, s: _Core, failure: Optional[Failure] = None
    ) -> IDelayedCall:
        s.failedAttempts += 1
        delay = s.timeoutForAttempt(s.failedAttempts)
        s.log.info(
            "Scheduling retry {attempt} to connect {endpoint} in {delay} seconds.",
            attempt=s.failedAttempts,
            endpoint=s.endpoint,
            delay=delay,
        )
        return s.clock.callLater(delay, c._reconnect)

    def rememberConnection(
        c: _Client, s: _Core, protocol: _ReconnectingProtocolProxy
    ) -> _ReconnectingProtocolProxy:
        s.failedAttempts = 0
        s.unawait(protocol._protocol)
        return protocol

    def attemptConnection(
        c: _Client, s: _Core, failure: Optional[Failure] = None
    ) -> Deferred[_ReconnectingProtocolProxy]:
        factoryProxy = _DisconnectFactory(s.factory, c._clientDisconnected)
        connecting: Deferred[IProtocol] = s.endpoint.connect(factoryProxy)

        def prepare(
            protocol: _ReconnectingProtocolProxy,
        ) -> Deferred[_ReconnectingProtocolProxy]:
            if s.prepareConnection is not None:
                return maybeDeferred(s.prepareConnection, protocol).addCallback(
                    lambda _: protocol
                )
            return succeed(protocol)

        # endpoint.connect() is actually generic on the type of the protocol,
        # but this is not expressible via zope.interface, so we have to cast
        # https://github.com/Shoobx/mypy-zope/issues/95
        connectingProxy: Deferred[_ReconnectingProtocolProxy]
        connectingProxy = connecting  # type:ignore[assignment]
        (
            connectingProxy.addCallback(prepare)
            .addCallback(c._connectionMade)
            .addErrback(c._connectionFailed)
        )
        return connectingProxy

    # States:
    Init = machine.state("Init")
    Connecting = machine.state("Connecting", attemptConnection)
    Stopped = machine.state("Stopped")
    Waiting = machine.state("Waiting", waitForRetry)
    Connected = machine.state("Connected", rememberConnection)
    Disconnecting = machine.state("Disconnecting")
    Restarting = machine.state("Restarting")
    Stopped = machine.state("Stopped")

    # Behavior-less state transitions:
    Init.upon(_Client.start).to(Connecting).returns(None)
    Connecting.upon(_Client.start).loop().returns(None)
    Connecting.upon(_Client._connectionMade).to(Connected).returns(None)
    Waiting.upon(_Client.start).loop().returns(None)
    Waiting.upon(_Client._reconnect).to(Connecting).returns(None)
    Connected.upon(_Client._connectionFailed).to(Waiting).returns(None)
    Connected.upon(_Client.start).loop().returns(None)
    Connected.upon(_Client._clientDisconnected).to(Waiting).returns(None)
    Disconnecting.upon(_Client.start).to(Restarting).returns(None)
    Restarting.upon(_Client.start).to(Restarting).returns(None)
    Stopped.upon(_Client.start).to(Connecting).returns(None)

    # Behavior-full state transitions:
    @pep614(Init.upon(_Client.stop).to(Stopped))
    @pep614(Stopped.upon(_Client.stop).to(Stopped))
    def immediateStop(c: _Client, s: _Core) -> Deferred[None]:
        return succeed(None)

    @pep614(Connecting.upon(_Client.stop).to(Disconnecting))
    def connectingStop(
        c: _Client, s: _Core, attempt: Deferred[_ReconnectingProtocolProxy]
    ) -> Deferred[None]:
        waited = s.waitForStop()
        attempt.cancel()
        return waited

    @pep614(Connecting.upon(_Client._connectionFailed, nodata=True).to(Waiting))
    def failedWhenConnecting(c: _Client, s: _Core, failure: Failure) -> None:
        ready = []
        notReady: list[tuple[Deferred[IProtocol], Optional[int]]] = []
        for w, remaining in s.awaitingConnected:
            if remaining is None:
                notReady.append((w, remaining))
            elif remaining <= 1:
                ready.append(w)
            else:
                notReady.append((w, remaining - 1))
        s.awaitingConnected = notReady
        for w in ready:
            w.callback(failure)

    @pep614(Waiting.upon(_Client.stop).to(Stopped))
    def stop(c: _Client, s: _Core, futureRetry: IDelayedCall) -> Deferred[None]:
        waited = s.waitForStop()
        s.cancelConnectWaiters()
        futureRetry.cancel()
        s.finishStopping()
        return waited

    @pep614(Connected.upon(_Client.stop).to(Disconnecting))
    def stopWhileConnected(
        c: _Client, s: _Core, protocol: _ReconnectingProtocolProxy
    ) -> Deferred[None]:
        waited = s.waitForStop()
        protocol._transport.loseConnection()
        return waited

    @pep614(Connected.upon(_Client.whenConnected).loop())
    def whenConnectedWhenConnected(
        c: _Client,
        s: _Core,
        protocol: _ReconnectingProtocolProxy,
        failAfterFailures: Optional[int] = None,
    ) -> Deferred[IProtocol]:
        return succeed(protocol._protocol)

    @pep614(Disconnecting.upon(_Client.stop).loop())
    @pep614(Restarting.upon(_Client.stop).to(Disconnecting))
    def discoStop(c: _Client, s: _Core) -> Deferred[None]:
        return s.waitForStop()

    @pep614(Disconnecting.upon(_Client._connectionFailed).to(Stopped))
    @pep614(Disconnecting.upon(_Client._clientDisconnected).to(Stopped))
    def disconnectingFinished(
        c: _Client, s: _Core, failure: Optional[Failure] = None
    ) -> None:
        s.cancelConnectWaiters()
        s.finishStopping()

    @pep614(Connecting.upon(_Client.whenConnected, nodata=True).loop())
    @pep614(Waiting.upon(_Client.whenConnected, nodata=True).loop())
    @pep614(Init.upon(_Client.whenConnected).to(Init))
    @pep614(Restarting.upon(_Client.whenConnected).to(Restarting))
    @pep614(Disconnecting.upon(_Client.whenConnected).to(Disconnecting))
    def awaitingConnection(
        c: _Client, s: _Core, failAfterFailures: Optional[int] = None
    ) -> Deferred[IProtocol]:
        result: Deferred[IProtocol] = Deferred()
        s.awaitingConnected.append((result, failAfterFailures))
        return result

    @pep614(Restarting.upon(_Client._clientDisconnected).to(Connecting))
    def restartDone(c: _Client, s: _Core, failure: Optional[Failure] = None) -> None:
        s.finishStopping()

    @pep614(Stopped.upon(_Client.whenConnected).to(Stopped))
    def notGoingToConnect(
        c: _Client, s: _Core, failAfterFailures: Optional[int] = None
    ) -> Deferred[IProtocol]:
        return fail(CancelledError())

    return machine.build()


def backoffPolicy(
    initialDelay: float = 1.0,
    maxDelay: float = 60.0,
    factor: float = 1.5,
    jitter: Callable[[], float] = _goodEnoughRandom,
) -> Callable[[int], float]:
    """
    A timeout policy for L{ClientService} which computes an exponential backoff
    interval with configurable parameters.

    @since: 16.1.0

    @param initialDelay: Delay for the first reconnection attempt (default
        1.0s).
    @type initialDelay: L{float}

    @param maxDelay: Maximum number of seconds between connection attempts
        (default 60 seconds, or one minute).  Note that this value is before
        jitter is applied, so the actual maximum possible delay is this value
        plus the maximum possible result of C{jitter()}.
    @type maxDelay: L{float}

    @param factor: A multiplicative factor by which the delay grows on each
        failed reattempt.  Default: 1.5.
    @type factor: L{float}

    @param jitter: A 0-argument callable that introduces noise into the delay.
        By default, C{random.random}, i.e. a pseudorandom floating-point value
        between zero and one.
    @type jitter: 0-argument callable returning L{float}

    @return: a 1-argument callable that, given an attempt count, returns a
        floating point number; the number of seconds to delay.
    @rtype: see L{ClientService.__init__}'s C{retryPolicy} argument.
    """

    def policy(attempt: int) -> float:
        try:
            delay = min(initialDelay * (factor ** min(100, attempt)), maxDelay)
        except OverflowError:
            delay = maxDelay
        return delay + jitter()

    return policy


_defaultPolicy = backoffPolicy()
ClientMachine = makeMachine()


class ClientService(Service):
    """
    A L{ClientService} maintains a single outgoing connection to a client
    endpoint, reconnecting after a configurable timeout when a connection
    fails, either before or after connecting.

    @since: 16.1.0
    """

    _log = Logger()

    def __init__(
        self,
        endpoint: IStreamClientEndpoint,
        factory: IProtocolFactory,
        retryPolicy: Optional[Callable[[int], float]] = None,
        clock: Optional[IReactorTime] = None,
        prepareConnection: Optional[Callable[[IProtocol], object]] = None,
    ):
        """
        @param endpoint: A L{stream client endpoint
            <interfaces.IStreamClientEndpoint>} provider which will be used to
            connect when the service starts.

        @param factory: A L{protocol factory <interfaces.IProtocolFactory>}
            which will be used to create clients for the endpoint.

        @param retryPolicy: A policy configuring how long L{ClientService} will
            wait between attempts to connect to C{endpoint}; a callable taking
            (the number of failed connection attempts made in a row (L{int}))
            and returning the number of seconds to wait before making another
            attempt.

        @param clock: The clock used to schedule reconnection.  It's mainly
            useful to be parametrized in tests.  If the factory is serialized,
            this attribute will not be serialized, and the default value (the
            reactor) will be restored when deserialized.

        @param prepareConnection: A single argument L{callable} that may return
            a L{Deferred}.  It will be called once with the L{protocol
            <interfaces.IProtocol>} each time a new connection is made.  It may
            call methods on the protocol to prepare it for use (e.g.
            authenticate) or validate it (check its health).

            The C{prepareConnection} callable may raise an exception or return
            a L{Deferred} which fails to reject the connection.  A rejected
            connection is not used to fire an L{Deferred} returned by
            L{whenConnected}.  Instead, L{ClientService} handles the failure
            and continues as if the connection attempt were a failure
            (incrementing the counter passed to C{retryPolicy}).

            L{Deferred}s returned by L{whenConnected} will not fire until any
            L{Deferred} returned by the C{prepareConnection} callable fire.
            Otherwise its successful return value is consumed, but ignored.

            Present Since Twisted 18.7.0
        """
        clock = _maybeGlobalReactor(clock)
        retryPolicy = _defaultPolicy if retryPolicy is None else retryPolicy

        self._machine: _Client = ClientMachine(
            _Core(
                endpoint,
                factory,
                retryPolicy,
                clock,
                prepareConnection=prepareConnection,
                log=self._log,
            )
        )

    def whenConnected(
        self, failAfterFailures: Optional[int] = None
    ) -> Deferred[IProtocol]:
        """
        Retrieve the currently-connected L{Protocol}, or the next one to
        connect.

        @param failAfterFailures: number of connection failures after which
            the Deferred will deliver a Failure (None means the Deferred will
            only fail if/when the service is stopped).  Set this to 1 to make
            the very first connection failure signal an error.  Use 2 to
            allow one failure but signal an error if the subsequent retry
            then fails.
        @type failAfterFailures: L{int} or None

        @return: a Deferred that fires with a protocol produced by the
            factory passed to C{__init__}
        @rtype: L{Deferred} that may:

            - fire with L{IProtocol}

            - fail with L{CancelledError} when the service is stopped

            - fail with e.g.
              L{DNSLookupError<twisted.internet.error.DNSLookupError>} or
              L{ConnectionRefusedError<twisted.internet.error.ConnectionRefusedError>}
              when the number of consecutive failed connection attempts
              equals the value of "failAfterFailures"
        """
        return self._machine.whenConnected(failAfterFailures)

    def startService(self) -> None:
        """
        Start this L{ClientService}, initiating the connection retry loop.
        """
        if self.running:
            self._log.warn("Duplicate ClientService.startService {log_source}")
            return
        super().startService()
        self._machine.start()

    def stopService(self) -> Deferred[None]:
        """
        Stop attempting to reconnect and close any existing connections.

        @return: a L{Deferred} that fires when all outstanding connections are
            closed and all in-progress connection attempts halted.
        """
        super().stopService()
        return self._machine.stop()
