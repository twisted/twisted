"""
Tests for L{twisted.internet._signals}.
"""

from typing import List, Set

from attrs import Factory, define
from hamcrest import assert_that, equal_to

from ...trial.unittest import SynchronousTestCase
from .._signals import _ChildSignalHandling, _MultiSignalHandling


@define
class RecorderHandling:
    """
    A L{SignalHandling} implementation that merely records calls made on it.
    """

    events: List[str] = Factory(list)

    def install(self) -> None:
        self.events.append("install")

    def uninstall(self) -> None:
        self.events.append("uninstall")


class WithChildSignalHandlingTests(SynchronousTestCase):
    """
    Tests for L{_ChildSignalHandling}.
    """

    def test_fileDescriptorsCleanedUp(self) -> None:
        """
        L{_ChildSignalHandling.uninstall} releases any file descriptors
        allocated by L{_ChildSignalHandling.install}.
        """
        readers: Set[object] = set()
        handling = _ChildSignalHandling(readers.add, readers.remove)

        # If it leaks file descriptors then we'll run out eventually.
        for n in range(8192):
            handling.install()
            handling.uninstall()

        assert_that(readers, equal_to(set()))


class MultiSignalHandling(SynchronousTestCase):
    """
    Tests for L{_MultiSignalHandling}.
    """

    def test_delegated(self) -> None:
        """
        L{_MultiSignalHandling} propagates L{SignalHandling.install} and
        C{SignalHandling.uninstall} calls to all of the L{SignalHandling}
        instances it is initialized with.
        """
        a = RecorderHandling()
        b = RecorderHandling()
        c = _MultiSignalHandling((a, b))
        c.install()
        c.uninstall()
        assert_that(a.events, equal_to(["install", "uninstall"]))
        assert_that(b.events, equal_to(["install", "uninstall"]))
