
from twisted.internet.defer import Deferred

d = Deferred()

def push2aiter():
    each = Deferred()
    done = object()
    async def aiter():
        while True:
            out = await each
            if out is done:
                return
            yield out
    def push(value):
        nonlocal each
        old, each = each, Deferred()
        old.callback(value)
    def stop():
        each.callback(done)
    return push, stop, aiter()

async def x(ai) -> None:
    """
    blubwhat
    """
    async for val in ai():
        print("got", val)


# p, s, ai = push2aiter()
# Deferred.fromCoroutine(x(ai))

# p(3)
# p(4)
# p(5)

async def resolver() -> TwistedProtocol:
    """
    
    """
    p, s, ai = push2aiter()
    class res(object):
        def resolutionBegan(self, resolutionInProgress: IHostResolution) -> None:
            pass

        def addressResolved(self, address: IAddress) -> None:
            p(address)

        def resolutionComplete(self) -> None:
            s()

    resolver.resolveHostName(res(), hostname)

    async for addr in ai:
        ep = addr2endpoint(addr)
        if ep is not None:
            try:
                result = await timeout(ep.connect(pf), attemptDelay)
            except TimeoutError:
                pass


async def connector():
    async for resolved in resolver():
        pass


async def connect():
    """
    
    """
    
