"""
Tests for the insults windowing module, L{twisted.conch.insults.window}.
"""
from __future__ import annotations

from typing import Callable

from twisted.conch.insults.insults import ServerProtocol
from twisted.conch.insults.window import ScrolledArea, Selection, TextOutput, TopWindow
from twisted.trial.unittest import TestCase


class TopWindowTests(TestCase):
    """
    Tests for L{TopWindow}, the root window container class.
    """

    def test_paintScheduling(self) -> None:
        """
        Verify that L{TopWindow.repaint} schedules an actual paint to occur
        using the scheduling object passed to its initializer.
        """
        paints: list[None] = []
        scheduled: list[Callable[[], object]] = []
        root = TopWindow(lambda: paints.append(None), scheduled.append)

        # Nothing should have happened yet.
        self.assertEqual(paints, [])
        self.assertEqual(scheduled, [])

        # Cause a paint to be scheduled.
        root.repaint()
        self.assertEqual(paints, [])
        self.assertEqual(len(scheduled), 1)

        # Do another one to verify nothing else happens as long as the previous
        # one is still pending.
        root.repaint()
        self.assertEqual(paints, [])
        self.assertEqual(len(scheduled), 1)

        # Run the actual paint call.
        scheduled.pop()()
        self.assertEqual(len(paints), 1)
        self.assertEqual(scheduled, [])

        # Do one more to verify that now that the previous one is finished
        # future paints will succeed.
        root.repaint()
        self.assertEqual(len(paints), 1)
        self.assertEqual(len(scheduled), 1)


class ScrolledAreaTests(TestCase):
    """
    Tests for L{ScrolledArea}, a widget which creates a viewport containing
    another widget and can reposition that viewport using scrollbars.
    """

    def test_parent(self) -> None:
        """
        The parent of the widget passed to L{ScrolledArea} is set to a new
        L{Viewport} created by the L{ScrolledArea} which itself has the
        L{ScrolledArea} instance as its parent.
        """
        widget = TextOutput()
        scrolled = ScrolledArea(widget)
        self.assertIs(widget.parent, scrolled._viewport)
        self.assertIs(scrolled._viewport.parent, scrolled)


class SelectionTests(TestCase):
    """
    Change focused entry in L{Selection} using function keys
    """

    def test_selection_change(self) -> None:
        """
        Send function key codes to change focused entry
        """

        seq: list[bytes] = [f"{_num}".encode("ascii") for _num in range(10)]

        widget = Selection(seq, None)
        widget.height = 10  # type: ignore[assignment]
        self.assertIs(widget.focusedIndex, 0)

        # Move down by one, second element is selected
        widget.keystrokeReceived(ServerProtocol.DOWN_ARROW, None)  # type: ignore[attr-defined]
        self.assertIs(widget.focusedIndex, 1)

        # Move down by page, last element is selected
        widget.keystrokeReceived(ServerProtocol.PGDN, None)  # type: ignore[attr-defined]
        self.assertIs(widget.focusedIndex, 9)

        # Move up by one, second to last element is selected
        widget.keystrokeReceived(ServerProtocol.UP_ARROW, None)  # type: ignore[attr-defined]
        self.assertIs(widget.focusedIndex, 8)

        # Move up by page, first element is selected
        widget.keystrokeReceived(ServerProtocol.PGUP, None)  # type: ignore[attr-defined]
        self.assertIs(widget.focusedIndex, 0)
