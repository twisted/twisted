"""
Tests for the insults windowing module, L{twisted.conch.insults.window}.
"""
from __future__ import annotations

from typing import Callable

from twisted.conch.insults.insults import FUNCTION_KEYS
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
    Tests for L{Selection}, a widget which allows to select item from
    list of items.
    """

    seq = [f"{x}".encode("ascii") for x in range(10)]
    keys = {
        "up": b"[UP_ARROW]",
        "down": b"[DOWN_ARROW]",
        "pgup": b"[PGUP]",
        "pgdn": b"[PGDN]",
    }

    def test_defined_keynames(self) -> None:
        """
        Test if expected key names are still defined in t.c.i.i.FUNCTION_KEYS
        """
        self.assertTrue(set(self.keys.values()).issubset(set(FUNCTION_KEYS)))

    def test_selection(self) -> None:
        """
        Test if sending function key codes actually changes focus
        """

        widget = Selection(self.seq, None)
        widget.height = 10  # type: ignore[assignment]
        self.assertIs(widget.focusedIndex, 0)

        # Move down by one, second element should be selected
        widget.keystrokeReceived(self.keys["down"], None)
        self.assertIs(widget.focusedIndex, 1)

        # Move down by page, last element should be selected
        widget.keystrokeReceived(self.keys["pgdn"], None)
        self.assertIs(widget.focusedIndex, 9)

        # Move up by one, second to last element should be selected
        widget.keystrokeReceived(self.keys["up"], None)
        self.assertIs(widget.focusedIndex, 8)

        # Move up by page, first element should be selected
        widget.keystrokeReceived(self.keys["pgup"], None)
        self.assertIs(widget.focusedIndex, 0)
