# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.asyncioreactor}.
"""
import gc

from twisted.internet import defer
from twisted.python.reflect import requireModule
from twisted.trial.unittest import SynchronousTestCase
from .reactormixins import ReactorBuilder

try:
    from twisted.internet.asyncioreactor import AsyncioSelectorReactor
    import asyncio
except ImportError:
    AsyncioSelectorReactor = None
    skipReason = "Requires asyncio."


contextvars = requireModule('contextvars')
if contextvars:
    contextvarsSkip = None
else:
    contextvarsSkip = "contextvars is not available"


sniffio = requireModule('sniffio')
if sniffio:
    sniffioSkip = contextvarsSkip
else:
    sniffioSkip = "sniffio is not available"



class AsyncioSelectorReactorTests(ReactorBuilder, SynchronousTestCase):
    """
    L{AsyncioSelectorReactor} tests.
    """
    if AsyncioSelectorReactor is None:
        skip = skipReason


    def test_defaultEventLoopFromGlobalPolicy(self):
        """
        L{AsyncioSelectorReactor} wraps the global policy's event loop
        by default.  This ensures that L{asyncio.Future}s and
        coroutines created by library code that uses
        L{asyncio.get_event_loop} are bound to the same loop.
        """
        reactor = AsyncioSelectorReactor()
        future = asyncio.Future()
        result = []

        def completed(future):
            result.append(future.result())
            reactor.stop()

        future.add_done_callback(completed)
        future.set_result(True)

        self.assertEqual(result, [])
        self.runReactor(reactor, timeout=1)
        self.assertEqual(result, [True])


    def test_seconds(self):
        """L{seconds} should return a plausible epoch time."""
        reactor = AsyncioSelectorReactor()
        result = reactor.seconds()

        # greater than 2020-01-01
        self.assertGreater(result, 1577836800)

        # less than 2120-01-01
        self.assertLess(result, 4733510400)


    def test_delayedCallResetToLater(self):
        """
        L{DelayedCall.reset()} properly reschedules timer to later time
        """
        reactor = AsyncioSelectorReactor()

        timer_called_at = [None]

        def on_timer():
            timer_called_at[0] = reactor.seconds()

        start_time = reactor.seconds()
        dc = reactor.callLater(0, on_timer)
        dc.reset(0.5)
        reactor.callLater(1, reactor.stop)
        reactor.run()

        self.assertIsNotNone(timer_called_at[0])
        self.assertGreater(timer_called_at[0] - start_time, 0.4)


    def test_delayedCallResetToEarlier(self):
        """
        L{DelayedCall.reset()} properly reschedules timer to earlier time
        """
        reactor = AsyncioSelectorReactor()

        timer_called_at = [None]

        def on_timer():
            timer_called_at[0] = reactor.seconds()

        start_time = reactor.seconds()
        dc = reactor.callLater(0.5, on_timer)
        dc.reset(0)
        reactor.callLater(1, reactor.stop)

        import io
        from contextlib import redirect_stderr
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            reactor.run()

        self.assertEqual(stderr.getvalue(), '')
        self.assertIsNotNone(timer_called_at[0])
        self.assertLess(timer_called_at[0] - start_time, 0.4)


    def test_noCycleReferencesInCallLater(self):
        """
        L{AsyncioSelectorReactor.callLater()} doesn't leave cyclic references
        """
        gc_was_enabled = gc.isenabled()
        gc.disable()
        try:
            objects_before = len(gc.get_objects())
            timer_count = 1000

            reactor = AsyncioSelectorReactor()
            for _ in range(timer_count):
                reactor.callLater(0, lambda: None)
            reactor.runUntilCurrent()

            objects_after = len(gc.get_objects())
            self.assertLess((objects_after - objects_before) / timer_count, 1)
        finally:
            if gc_was_enabled:
                gc.enable()



class AsyncioSelectorReactorSniffioTests(ReactorBuilder, SynchronousTestCase):

    skip = sniffioSkip

    def testSniffioNotFoundWhenOutside(self):
        reactor = AsyncioSelectorReactor()

        self.assertRaises(
            sniffio.AsyncLibraryNotFoundError,
            sniffio.current_async_library,
        )


    def testSniffioFindsAsyncioInCoroutine(self):
        async def inAsyncio():
            reactor.stop()

            return sniffio.current_async_library()

        reactor = AsyncioSelectorReactor()
        future = asyncio.ensure_future(inAsyncio())
        d = defer.Deferred.fromFuture(future)

        reactor.run()

        self.assertEqual(self.successResultOf(d), "asyncio")


    def testSniffioFindsNothingAfterCoroutine(self):
        async def inAsyncio():
            reactor.stop()

        reactor = AsyncioSelectorReactor()
        future = asyncio.ensure_future(inAsyncio())

        reactor.run()

        self.assertRaises(
            sniffio.AsyncLibraryNotFoundError,
            sniffio.current_async_library,
        )


    def testSniffioFindsTwistedCoroutineInsideAsyncioCoroutine(self):
        reactor = AsyncioSelectorReactor()

        async def innerTwisted():
            return [sniffio.current_async_library()]

        async def outerAsyncio():
            d = defer.ensureDeferred(innerTwisted())
            future = d.asFuture(loop=asyncio.get_event_loop())
            inner = await future

            reactor.stop()

            return [sniffio.current_async_library(), *inner]

        future = asyncio.ensure_future(outerAsyncio())
        d = defer.Deferred.fromFuture(future)

        reactor.run()

        self.assertEqual(self.successResultOf(d), ["asyncio", "twisted"])

        self.assertRaises(
            sniffio.AsyncLibraryNotFoundError,
            sniffio.current_async_library,
        )


    def testSniffioFindsNothingAfterTwistedCoroutineInsideAsyncioCoroutine(self):
        reactor = AsyncioSelectorReactor()

        async def innerTwisted():
            pass

        async def outerAsyncio():
            d = defer.ensureDeferred(innerTwisted())
            future = d.asFuture(loop=asyncio.get_event_loop())
            await future

            reactor.stop()

        future = asyncio.ensure_future(outerAsyncio())

        reactor.run()

        self.assertRaises(
            sniffio.AsyncLibraryNotFoundError,
            sniffio.current_async_library,
        )


    def testSniffioFindsAsyncioCoroutineInsideTwistedCoroutine(self):
        reactor = AsyncioSelectorReactor()

        async def innerAsyncio():
            return [sniffio.current_async_library()]

        async def outerTwisted():
            future = asyncio.ensure_future(innerAsyncio())
            d = defer.Deferred.fromFuture(future)
            inner = await d

            reactor.stop()

            return [sniffio.current_async_library(), *inner]

        d = defer.ensureDeferred(outerTwisted())

        reactor.run()

        self.assertEqual(self.successResultOf(d), ["twisted", "asyncio"])


    def testSniffioFindsNothingAfterAsyncioCoroutineInsideTwistedCoroutine(
            self,
    ):
        reactor = AsyncioSelectorReactor()

        async def innerAsyncio():
            pass

        async def outerTwisted():
            future = asyncio.ensure_future(innerAsyncio())
            d = defer.Deferred.fromFuture(future)
            await d

            reactor.stop()

        d = defer.ensureDeferred(outerTwisted())

        reactor.run()

        self.assertRaises(
            sniffio.AsyncLibraryNotFoundError,
            sniffio.current_async_library,
        )
