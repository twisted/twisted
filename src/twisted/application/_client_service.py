# -*- test-case-name: twisted.application.test.test_internet,twisted.test.test_application,twisted.test.test_cooperator -*-

from __future__ import annotations

from dataclasses import dataclass, field
from random import random as _goodEnoughRandom
from typing import Callable, Protocol as TypingProtocol, TypeVar

from zope.interface import implementer

from automat import TypicalBuilder

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
)
from twisted.logger import Logger
from twisted.python.failure import Failure

T = TypeVar("T")


def _maybeGlobalReactor(maybeReactor: T | None) -> T:
    """
    @return: the argument, or the global reactor if the argument is L{None}.
    """
    if maybeReactor is None:
        from twisted.internet import reactor

        return reactor  # type:ignore[return-value]
    else:
        return maybeReactor


class _ClientMachineProto(TypingProtocol):
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

    def _connectionMade(self, protocol: _ReconnectingProtocolProxy, /) -> None:
        """
        A connection has been made.

        @param protocol: The protocol of the connection.
        """

    def _connectionFailed(self, f: Failure, /) -> None:
        """
        The current connection attempt failed.
        """

    def _reconnect(self) -> None:
        """
        The wait between connection attempts is done.
        """

    def _clientDisconnected(self) -> None:
        """
        The current connection has been disconnected.
        """

    def whenConnected(
        self, failAfterFailures: int | None = None
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

    def buildProtocol(self, addr: IAddress) -> IProtocol | None:
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
    for zopeSpecial in [
        "__providedBy__",
        "__provides__",
        "__implemented__",
    ]:
        delattr(o, zopeSpecial)


_deinterface(_DisconnectFactory)
_deinterface(_ReconnectingProtocolProxy)


@dataclass
class _ClientServiceStateCore:
    """
    shared for ClientService
    """

    endpoint: IStreamClientEndpoint
    factory: IProtocolFactory
    timeoutForAttempt: Callable[[int], float]
    clock: IReactorTime
    prepareConnection: Callable[[IProtocol], object] | None
    connectionInProgress: Deferred[None] | None = None
    stopWaiters: list[Deferred[None]] = field(default_factory=list)
    _currentConnection: IProtocol | None = None
    _awaitingConnected: list[tuple[Deferred[IProtocol], int | None]] = field(
        default_factory=list
    )
    _retryCall: IDelayedCall | None = None
    log: Logger = Logger()
    failedAttempts: int = 0

    def waitForStop(self) -> Deferred[None]:
        self.stopWaiters.append(Deferred())
        return self.stopWaiters[-1]

    def stopConnecting(self) -> None:
        cip = self.connectionInProgress
        assert cip is not None
        cip.cancel()

    def _deliverConnectionFailure(self, f: Failure) -> None:
        """
        Deliver connection failures to any L{ClientService.whenConnected}
        L{Deferred}s that have met their failAfterFailures threshold.

        @param f: the Failure to fire the L{Deferred}s with.
        """
        ready = []
        notReady: list[tuple[Deferred[IProtocol], int | None]] = []
        for w, remaining in self._awaitingConnected:
            if remaining is None:
                notReady.append((w, remaining))
            elif remaining <= 1:
                ready.append(w)
            else:
                notReady.append((w, remaining - 1))
        self._awaitingConnected = notReady
        for w in ready:
            w.callback(f)

    def _runPrepareConnection(
        self, protocol: _ReconnectingProtocolProxy, /
    ) -> Deferred[_ReconnectingProtocolProxy]:
        """
        Run any C{prepareConnection} callback with the connected protocol,
        ignoring its return value but propagating any failure.

        @param protocol: The protocol of the connection.
        @type protocol: L{IProtocol}

        @return: Either:

            - A L{Deferred} that succeeds with the protocol when the
              C{prepareConnection} callback has executed successfully.

            - A L{Deferred} that fails when the C{prepareConnection} callback
              throws or returns a failed L{Deferred}.

            - The protocol, when no C{prepareConnection} callback is defined.
        """
        if self.prepareConnection is not None:
            return maybeDeferred(self.prepareConnection, protocol).addCallback(
                lambda _: protocol
            )
        return succeed(protocol)

    def connect(self, proto: _ClientMachineProto) -> None:
        factoryProxy = _DisconnectFactory(
            self.factory, lambda _: proto._clientDisconnected()
        )

        connecting: Deferred[IProtocol] = self.endpoint.connect(factoryProxy)
        # endpoint.connect() is actually generic on the type of the protocol,
        # but this is not expressible via zope.interface, so we have to cast
        # https://github.com/Shoobx/mypy-zope/issues/95
        connectingProxy: Deferred[
            _ReconnectingProtocolProxy
        ] = connecting  # type:ignore[assignment]

        self.connectionInProgress = (
            connectingProxy.addCallback(self._runPrepareConnection)
            .addCallback(proto._connectionMade)
            .addErrback(proto._connectionFailed)
        )

    def disconnect(self) -> None:
        transport = getattr(self._currentConnection, "transport", None)
        if transport is not None:
            # TODO: capture the transport in
            # _ReconnectingProtocolProxy.makeConnection() instead of relying on
            # implicit / incorrect 'transport' attribute here.
            transport.loseConnection()

    def _notifyWaiters(self, proxy: _ReconnectingProtocolProxy) -> None:
        self.failedAttempts = 0
        self._currentConnection = proxy._protocol
        self._unawait(self._currentConnection)

    def _unawait(self, value: IProtocol | Failure) -> None:
        self._awaitingConnected, waiting = [], self._awaitingConnected
        for w, remaining in waiting:
            w.callback(value)

    def wait(self, proto: _ClientMachineProto) -> None:
        self.failedAttempts += 1
        delay = self.timeoutForAttempt(self.failedAttempts)
        self.log.info(
            "Scheduling retry {attempt} to connect {endpoint} " "in {delay} seconds.",
            attempt=self.failedAttempts,
            endpoint=self.endpoint,
            delay=delay,
        )
        self._retryCall = self.clock.callLater(delay, proto._reconnect)

    def cancelConnectWaiters(self) -> None:
        self._unawait(Failure(CancelledError()))

    def stopRetrying(self) -> None:
        rc = self._retryCall
        assert rc is not None
        rc.cancel()
        self._retryCall = None

    def finishStopping(self) -> None:
        self.stopWaiters, waiting = [], self.stopWaiters
        for w in waiting:
            w.callback(None)

    def forgetConnection(self) -> None:
        self._currentConnection = None

    def resetFailedAttempts(self) -> None:
        self.failedAttempts = 0


machine = TypicalBuilder(_ClientMachineProto, _ClientServiceStateCore)


@dataclass
class _HasSP(TypingProtocol):
    s: _ClientServiceStateCore
    p: _ClientMachineProto


def awaitingConnection(self: _HasSP, faf: int | None) -> Deferred[IProtocol]:
    result: Deferred[IProtocol] = Deferred()
    self.s._awaitingConnected.append((result, faf))
    return result


@machine.state()
@dataclass
class _Init:
    s: _ClientServiceStateCore
    p: _ClientMachineProto

    @machine.handle(_ClientMachineProto.start, enter=lambda: _Connecting)
    def start(self) -> None:
        self.s.connect(self.p)

    @machine.handle(_ClientMachineProto.stop, enter=lambda: _Stopped)
    def stop(self) -> Deferred[None]:
        return succeed(None)

    @machine.handle(_ClientMachineProto.whenConnected, enter=lambda: _Init)
    def whenConnected(
        self, failAfterFailures: int | None = None
    ) -> Deferred[IProtocol]:
        return awaitingConnection(self, failAfterFailures)


@machine.state()
@dataclass
class _Connecting:
    s: _ClientServiceStateCore
    p: _ClientMachineProto

    @machine.handle(_ClientMachineProto.start, enter=lambda: _Connecting)
    def start(self) -> None:
        ...

    @machine.handle(_ClientMachineProto.stop, enter=lambda: _Disconnecting)
    def stop(self) -> Deferred[None]:
        waited = self.s.waitForStop()
        self.s.stopConnecting()
        return waited

    @machine.handle(_ClientMachineProto._connectionMade, enter=lambda: _Connected)
    def _connectionMade(self, protocol: _ReconnectingProtocolProxy) -> None:
        self.s._notifyWaiters(protocol)

    @machine.handle(_ClientMachineProto._connectionFailed, enter=lambda: _Waiting)
    def _connectionFailed(self, failure: Failure) -> None:
        self.s.wait(self.p)
        self.s._deliverConnectionFailure(failure)

    @machine.handle(_ClientMachineProto.whenConnected, enter=lambda: _Connecting)
    def whenConnected(
        self, failAfterFailures: int | None = None
    ) -> Deferred[IProtocol]:
        return awaitingConnection(self, failAfterFailures)


@machine.state()
@dataclass
class _Waiting:
    s: _ClientServiceStateCore
    p: _ClientMachineProto

    @machine.handle(_ClientMachineProto.start, enter=lambda: _Waiting)
    def start(self) -> None:
        ...

    @machine.handle(_ClientMachineProto.stop, enter=lambda: _Stopped)
    def stop(self) -> Deferred[None]:
        waited = self.s.waitForStop()
        self.s.cancelConnectWaiters()
        self.s.stopRetrying()
        self.s.finishStopping()
        return waited

    @machine.handle(_ClientMachineProto._reconnect, enter=lambda: _Connecting)
    def _reconnect(self) -> None:
        self.s.connect(self.p)

    @machine.handle(_ClientMachineProto.whenConnected, enter=lambda: _Waiting)
    def whenConnected(
        self, failAfterFailures: int | None = None
    ) -> Deferred[IProtocol]:
        return awaitingConnection(self, failAfterFailures)


@machine.state()
@dataclass
class _Connected:
    s: _ClientServiceStateCore
    p: _ClientMachineProto

    @machine.handle(_ClientMachineProto.start, enter=lambda: _Connected)
    def start(self) -> None:
        ...

    @machine.handle(_ClientMachineProto.stop, enter=lambda: _Disconnecting)
    def stop(self) -> Deferred[None]:
        waited = self.s.waitForStop()
        self.s.disconnect()
        return waited

    @machine.handle(_ClientMachineProto._clientDisconnected, enter=lambda: _Waiting)
    def _clientDisconnected(self) -> None:
        self.s.forgetConnection()
        self.s.wait(self.p)

    @machine.handle(_ClientMachineProto.whenConnected, enter=lambda: _Connected)
    def whenConnected(
        self, failAfterFailures: int | None = None
    ) -> Deferred[IProtocol]:
        cc = self.s._currentConnection
        assert cc is not None
        return succeed(cc)


@machine.state()
@dataclass
class _Disconnecting:
    s: _ClientServiceStateCore
    p: _ClientMachineProto

    @machine.handle(_ClientMachineProto.start, enter=lambda: _Restarting)
    def start(self) -> None:
        self.s.resetFailedAttempts()

    @machine.handle(_ClientMachineProto.stop, enter=lambda: _Disconnecting)
    def stop(self) -> Deferred[None]:
        return self.s.waitForStop()

    @machine.handle(_ClientMachineProto._clientDisconnected, enter=lambda: _Stopped)
    def _clientDisconnected(self) -> None:
        self.s.cancelConnectWaiters()
        self.s.finishStopping()
        self.s.forgetConnection()

    @machine.handle(_ClientMachineProto._connectionFailed, enter=lambda: _Stopped)
    def _connectionFailed(self, failure: Failure) -> None:
        self.s.cancelConnectWaiters()
        self.s.finishStopping()

    @machine.handle(_ClientMachineProto.whenConnected, enter=lambda: _Disconnecting)
    def whenConnected(
        self, failAfterFailures: int | None = None
    ) -> Deferred[IProtocol]:
        return awaitingConnection(self, failAfterFailures)


@machine.state()
@dataclass
class _Restarting:
    s: _ClientServiceStateCore
    p: _ClientMachineProto

    @machine.handle(_ClientMachineProto.start, enter=lambda: _Restarting)
    def start(self) -> None:
        ...

    @machine.handle(_ClientMachineProto.stop, enter=lambda: _Disconnecting)
    def stop(self) -> Deferred[None]:
        return self.s.waitForStop()

    @machine.handle(_ClientMachineProto._clientDisconnected, enter=lambda: _Connecting)
    def _clientDisconnected(self) -> None:
        self.s.finishStopping()
        self.s.connect(self.p)

    @machine.handle(_ClientMachineProto.whenConnected, enter=lambda: _Restarting)
    def whenConnected(
        self, failAfterFailures: int | None = None
    ) -> Deferred[IProtocol]:
        return awaitingConnection(self, failAfterFailures)


@machine.state()
@dataclass
class _Stopped:
    s: _ClientServiceStateCore
    p: _ClientMachineProto

    @machine.handle(_ClientMachineProto.start, enter=lambda: _Connecting)
    def start(self) -> None:
        self.s.connect(self.p)

    @machine.handle(_ClientMachineProto.stop, enter=lambda: _Stopped)
    def stop(self) -> Deferred[None]:
        return succeed(None)

    @machine.handle(_ClientMachineProto.whenConnected, enter=lambda: _Stopped)
    def whenConnected(
        self, failAfterFailures: int | None = None
    ) -> Deferred[IProtocol]:
        return fail(CancelledError())


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
        retryPolicy: Callable[[int], float] | None = None,
        clock: IReactorTime | None = None,
        prepareConnection: Callable[[IProtocol], object] | None = None,
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

        self._machine: _ClientMachineProto = ClientMachine(
            endpoint,
            factory,
            retryPolicy,
            clock,
            prepareConnection=prepareConnection,
            log=self._log,
        )

    def whenConnected(
        self, failAfterFailures: int | None = None
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


ClientMachine = machine.buildClass()
