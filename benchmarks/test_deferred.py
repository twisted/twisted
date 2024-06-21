from twisted.internet.defer import succeed, ensureDeferred, Deferred


def test_deferred_await(benchmark):
    """Measure the speed of awaiting and of defer.succeed()."""

    async def _run():
        for x in range(1000):
            await succeed(x)

    def go():
        ensureDeferred(_run())

    benchmark(go)


def f(x: int, a: int) -> int:
    return x + a


def test_deferred_callback_chain_fires_at_start(benchmark):
    """
    Measure speed of successful callbacks, where the Deferred fires before the
    callbacks are added.
    """

    def go():
        d = Deferred()
        d.callback(2)
        d.addCallback(f, 1)
        d.addCallback(f, 2)
        d.addCallback(f, 3)
        d.addCallback(f, 4)

    benchmark(go)


def test_deferred_callback_chain_fires_at_end(benchmark):
    """
    Measure speed of successful callbacks, where the Deferred fires after the
    callbacks are added.
    """

    def go():
        d = Deferred()
        d.addCallback(f, 1)
        d.addCallback(f, 2)
        d.addCallback(f, 3)
        d.addCallback(f, 4)
        d.callback(2)

    benchmark(go)


def test_deferred_errback_chain(benchmark):
    """
    Measure speed of error handling in callbacks.
    callbacks are added.
    """

    def go():
        d = succeed("result")

        def cbRaiseErr(_):
            raise Exception("boom!")

        d.addCallback(cbRaiseErr)

        def ebHandleErr(failure):
            failure.trap(Exception)
            raise Exception("lesser boom!")

        d.addErrback(ebHandleErr)

        def swallowErr(_):
            return None

        d.addBoth(swallowErr)

    benchmark(go)
