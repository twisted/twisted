from typing import TYPE_CHECKING

from twisted.trial.unittest import SynchronousTestCase
from .reactormixins import ReactorBuilder

if TYPE_CHECKING:
    fakeBase = SynchronousTestCase
else:
    fakeBase = object


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
        r = self.buildReactor()
        delayed = r.callLater(0, lambda: None)
        r2 = self.buildReactor()
        r2.callLater(0, r2.callLater, 0, r2.stop)
        self.runReactor(r2)
        self.assertEqual(r.getDelayedCalls(), [delayed])


globals().update(CoreFoundationSpecificTests.makeTestCaseClasses())
