# -*- test-case-name: twisted.internet.test.test_endpoints -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import AsyncIterable, Callable, Generic, List, Literal, Optional, TYPE_CHECKING, Tuple, TypeVar, Union

from ._shutil import Outstanding
from twisted.internet.address import HostnameAddress, IPv4Address, IPv6Address
from twisted.internet.defer import CancelledError, Deferred, DeferredList, succeed
from twisted.internet.error import ConnectError, ConnectingCancelledError, DNSLookupError, TimeoutError
from twisted.internet.interfaces import IProtocolFactory, IReactorTime, IStreamClientEndpoint
from twisted.internet.task import deferLater
from twisted.python.failure import Failure


if TYPE_CHECKING:
    from twisted.internet.endpoints import HostnameEndpoint
from twisted.internet.interfaces import (
    IAddress,
    IHostResolution,
    IProtocol as TwistedProtocol,
)


T = TypeVar("T")
X = TypeVar("X")

class DoneSentinel(Enum):
    Done = auto()

def push2aiter() -> Tuple[Callable[[T], None], Callable[[], None], AsyncIterable[T]]:
    """
    Create a Deferred coroutine which presents an async iterable, and a
    callable that will push values into it and a callable that will stop it.
    """
    q: List[Deferred[Union[T, Literal[DoneSentinel.Done]]]] = []

    async def aiter() -> AsyncIterable[T]:
        while True:
            if not q:
                q.append(Deferred())
            out = await q.pop(0)
            if out is DoneSentinel.Done:
                return
            # 'is done' is a type guard that mypy can't see
            yield out

    def push(value: Union[T, DoneSentinel]) -> None:
        q.append(succeed(value))

    def stop() -> None:
        push(DoneSentinel.Done)

    return push, stop, aiter()


def addr2endpoint(
    hostnameEndpoint: HostnameEndpoint,
    address: IAddress,
) -> IStreamClientEndpoint | None:
    """
    Convert an address into an endpoint
    """
    # Circular imports.
    from twisted.internet.endpoints import TCP4ClientEndpoint, TCP6ClientEndpoint

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
class MultiFirer(Generic[T]):
    deferreds: Outstanding[T] = field(default_factory=Outstanding)
    activeTimeout: Optional[Deferred[None]] = None
    waiting: Optional[Deferred[Tuple[bool, Optional[T]]]] = None
    hasResult: bool = False
    hasFailure: bool = False
    finalResult: Optional[T] = None
    ended: bool = False
    failures: List[Failure] = field(default_factory=list)

    def add(self, deferred: Deferred[T]) -> None:
        """
        Add a Deferred that might be waited upon.
        """
        self.deferreds.add(deferred)

        def complete(result: T) -> T:
            self.hasResult = True
            self.finalResult = result
            self._maybeCompleteWaiting(True, self.finalResult)
            return result

        def failed(failure: Failure) -> None:
            self.failures.append(failure)
            self._maybeCompleteWaiting(False, None)
            return None

        deferred.addCallbacks(complete, failed)

    def wait(
        self, clock: IReactorTime, seconds: float
    ) -> Deferred[Union[Tuple[Literal[True], T], Tuple[Literal[False], None]]]:
        assert self.waiting is None, "no waiting while waiting"

        def cancel(d: Deferred[Tuple[bool, Optional[T]]]) -> None:
            self.deferreds.cancel()

        def timedOut(nothing: None) -> None:
            self._maybeCompleteWaiting(False, None)

        def ignoreCancel(f: Failure) -> None:
            f.trap(CancelledError)

        self.activeTimeout = deferLater(clock, seconds).addCallbacks(
            timedOut, ignoreCancel
        )
        w = self.waiting = Deferred(cancel)
        self._maybeFinallyFail()
        return w

    def end(self) -> None:
        """
        No more results will be added.
        """
        self.ended = True
        self._maybeFinallyFail()

    def cancel(self) -> None:
        self.deferreds.cancel()

    def _maybeFinallyFail(self) -> None:
        """ """
        if (
            self.waiting is not None
            and self.activeTimeout is not None
            and self.ended
            and self.deferreds.empty()
            and not self.hasResult
        ):
            self.activeTimeout.cancel()
            self.activeTimeout = None
            it, self.waiting = self.waiting, None
            e: Union[Failure, Exception]
            if len(self.failures) == 1:
                e = self.failures[0]
            else:
                e = RuntimeError(f"multiple failures {self.failures}")
            it.errback(e)

    def _maybeCompleteWaiting(self, actuallyDone: bool, value: Optional[T]) -> None:
        self._maybeFinallyFail()
        if self.waiting is not None and self.activeTimeout is not None:
            self.activeTimeout.cancel()
            self.activeTimeout = None
            it, self.waiting = self.waiting, None
            it.callback((actuallyDone, value))


async def _start(
    endpoint: HostnameEndpoint,
    pf: IProtocolFactory,
) -> TwistedProtocol:
    """
    resolver coroutine that runs
    """
    assert endpoint is not None, "Wtf"
    p: Callable[[IAddress], None]
    s: Callable[[], None]
    ai: AsyncIterable[IAddress]

    p, s, ai = push2aiter()

    class res(object):
        def resolutionBegan(self, resolutionInProgress: IHostResolution) -> None:
            pass

        def addressResolved(self, address: IAddress) -> None:
            p(address)

        def resolutionComplete(self) -> None:
            s()

    resolver = endpoint._nameResolver
    reactor = endpoint._reactor
    resolver.resolveHostName(res(), endpoint._hostStr, portNumber=endpoint._port)

    mf: MultiFirer[TwistedProtocol] = MultiFirer()
    try:
        attempts = 0
        async for addr in ai:
            ep = addr2endpoint(endpoint, addr)
            if ep is None:
                continue
            attempts += 1
            mf.add(ep.connect(pf))
            done, result = await mf.wait(reactor, endpoint._attemptDelay)
            if done:
                assert result is not None
                return result
        mf.end()
        if not attempts:
            raise DNSLookupError(f"no results for hostname lookup: {endpoint._hostStr}")
        done, result = await mf.wait(reactor, 10000)
        if done is True:
            assert result is not None
            return result
        mf.cancel()
        raise RuntimeError("unreachable")
    finally:
        ty, v, tb = exc_info()
        if ty is not GeneratorExit:
            mf.cancel()
from sys import exc_info

def start(
    endpoint: HostnameEndpoint,
    pf: IProtocolFactory,
) -> Deferred[TwistedProtocol]:
    def translateCancel(f: Failure) -> Failure:
        f.trap(CancelledError, ConnectingCancelledError)
        raise ConnectingCancelledError(
            HostnameAddress(endpoint._hostBytes, endpoint._port)
        )

    return Deferred.fromCoroutine(_start(endpoint, pf)).addErrback(translateCancel)
