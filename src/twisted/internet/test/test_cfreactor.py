from typing import TYPE_CHECKING, List

from twisted.trial.unittest import SynchronousTestCase
from .reactormixins import ReactorBuilder

if TYPE_CHECKING:
    fakeBase = SynchronousTestCase
else:
    fakeBase = object

from twisted.logger import Logger

l = Logger()


class CoreFoundationSpecificTests(ReactorBuilder, fakeBase):
    """
    Tests for platform interactions of the CoreFoundation-based reactor.
    """

    _reactors = ["twisted.internet.cfreactor.CFReactor"]

    def test_whiteboxStopSimulating(self) -> None:
        """
        CFReactor's simulation timer is None after CFReactor crashes.
        """
        r = self.buildReactor()
        r.callLater(0, r.crash)
        r.callLater(100, lambda: None)
        self.runReactor(r)
        self.assertIs(r._currentSimulator, None)

    def test_callLaterLeakage(self) -> None:
        """
        callLater should not leak global state into CoreFoundation which will
        be invoked by a different reactor running the main loop.

        @note: this test may actually be usable for other reactors as well, so
            we may wish to promote it to ensure this invariant across other
            foreign-main-loop reactors.
        """
        l.info("building reactor 1")
        r = self.buildReactor()
        l.info("scheduling delay 1")
        delayed = r.callLater(0, lambda: None)
        l.info("building reactor 2")
        r2 = self.buildReactor()
        l.info("scheduling delay 2")

        def stopBlocking() -> None:
            l.info("scheduling r2stop")
            r2.callLater(0, r2stop)

        def r2stop() -> None:
            l.info("r2 stop happening")
            r2.stop()

        r2.callLater(0, stopBlocking)
        l.info("blocking")
        self.runReactor(r2)
        l.info("asserting")
        self.assertEqual(r.getDelayedCalls(), [delayed])
        l.info("done")

    def test_whiteboxIterate(self) -> None:
        """
        C{.iterate()} starts the main loop, then crashes the reactor.
        """
        r = self.buildReactor()
        x: List[int] = []
        r.callLater(0, x.append, 1)
        delayed = r.callLater(100, lambda: None)
        r.iterate()
        self.assertIs(r._currentSimulator, None)
        self.assertEqual(r.getDelayedCalls(), [delayed])
        self.assertEqual(x, [1])


globals().update(CoreFoundationSpecificTests.makeTestCaseClasses())
