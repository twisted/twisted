from twisted.internet.defer import Deferred, ensureDeferred, succeed


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


def test_deferred_chained_already_fired(benchmark):
    """
    Measure speed of chained Deferred, where the chained Deferred fires before
    the callback returning it is added.
    """

    def go():
        d = Deferred()
        d2 = Deferred()
        d3 = Deferred()
        d2.callback(123)
        d3.callback(456)
        d.addCallback(lambda _: d2)
        d.addCallback(lambda _: d3)
        d.callback(123)

    benchmark(go)


def test_deferred_chained_not_fired(benchmark):
    """
    Measure speed of chained Deferred, where the chained Deferred fires after
    the callback returning it is added.
    """

    def go():
        d = Deferred()
        d2 = Deferred()
        # d3 has its own chained result:
        d3 = Deferred()
        d4 = Deferred()
        d3.addCallback(lambda _: d4)
        d3.callback(123)
        d.addCallback(lambda _: d2)
        d.addCallback(lambda _: d3)
        d2.callback(123)
        d4.callback(57)
        d.callback(7)

    benchmark(go)
