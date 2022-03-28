from dataclasses import dataclass, field
from typing import (
    AsyncIterable,
    Callable,
    Generic,
    List,
    Literal,
    Optional,
    TYPE_CHECKING,
    Tuple,
    TypeVar,
    Union,
)

from ._shutil import Outstanding
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.error import TimeoutError
from twisted.internet.interfaces import (
    IProtocolFactory,
    IReactorTime,
    IStreamClientEndpoint,
)
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


def push2aiter() -> Tuple[Callable[[T], None], Callable[[], None], AsyncIterable[T]]:
    """
    Create a Deferred coroutine which presents an async iterable, and a
    callable that will push values into it and a callable that will stop it.
    """
    each: Deferred[Union[T, object]] = Deferred()
    done = object()

    async def aiter() -> AsyncIterable[T]:
        while True:
            out = await each
            if out is done:
                return
            # 'is done' is a type guard that mypy can't see
            yield out  # type: ignore

    def push(value: T) -> None:
        nonlocal each
        old, each = each, Deferred()
        old.callback(value)

    def stop() -> None:
        each.callback(done)

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
            self._maybeFinallyFail()
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

        self.activeTimeout = deferLater(clock, seconds).addCallback(timedOut)
        self.waiting = Deferred(cancel)
        return self.waiting

    def end(self) -> None:
        """
        No more results will be added.
        """
        self.ended = True
        self._maybeFinallyFail()

    def cancel(self) -> None:
        assert self.ended
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
            it.errback(RuntimeError(f"multiple failures {self.failures}"))

    def _maybeCompleteWaiting(self, actuallyDone: bool, value: Optional[T]) -> None:
        if self.waiting is not None and self.activeTimeout is not None:
            self.activeTimeout.cancel()
            self.activeTimeout = None
            it, self.waiting = self.waiting, None
            it.callback((actuallyDone, value))


async def start(
    pf: IProtocolFactory, endpoint: HostnameEndpoint, reactor: IReactorTime
) -> TwistedProtocol:
    """
    resolver coroutine that runs
    """
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
    resolver.resolveHostName(res(), endpoint._hostStr)

    mf: MultiFirer[TwistedProtocol] = MultiFirer()
    async for addr in ai:
        ep = addr2endpoint(endpoint, addr)
        if ep is None:
            continue
        mf.add(ep.connect(pf))
        done, result = await mf.wait(reactor, endpoint._attemptDelay)
        if done:
            assert result is not None
            return result
    mf.end()
    done, result = await mf.wait(reactor, 10000)
    if done is True:
        assert result is not None
        return result
    mf.cancel()
    raise TimeoutError("final connection failed")
