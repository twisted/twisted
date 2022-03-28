
from typing import AsyncIterable, Callable, TYPE_CHECKING, Tuple, TypeVar, Union

from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IProtocolFactory, IReactorTime, IStreamClientEndpoint


if TYPE_CHECKING:
    from twisted.internet.endpoints import HostnameEndpoint
from twisted.internet.interfaces import IAddress, IHostResolution, IProtocol as TwistedProtocol


T = TypeVar("T")

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
            yield out           # type: ignore
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

async def start(pf: IProtocolFactory, endpoint: HostnameEndpoint, reactor: IReactorTime) -> TwistedProtocol:
    """
    resolver coroutine that runs
    """
    p: Callable[[IAddress], None]
    s: Callable[[], None]
    ai: AsyncIterable[IAddress]

    p, s, ai = push2aiter()

    class res:
        def resolutionBegan(self, resolutionInProgress: IHostResolution) -> None:
            pass

        def addressResolved(self, address: IAddress) -> None:
            p(address)

        def resolutionComplete(self) -> None:
            s()

    resolver = endpoint._nameResolver
    resolver.resolveHostName(res(), endpoint._hostStr)

    async for addr in ai:
        ep = addr2endpoint(endpoint, addr)
        if ep is not None:
            try:
                return await ep.connect(pf).addTimeout(endpoint._attemptDelay, reactor)
            except TimeoutError:
                pass

    raise RuntimeError("Failed connection")


