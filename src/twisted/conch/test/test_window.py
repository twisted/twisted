"""
Tests for the insults windowing module, L{twisted.conch.insults.window}.
"""
from __future__ import annotations

from typing import Callable

from twisted.conch.insults.insults import ServerProtocol
from twisted.conch.insults.window import (
    ScrolledArea,
    Selection,
    TextOutput,
    TopWindow,
    Widget,
)
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

    def setUp(self) -> None:
        """
        Create L{ScrolledArea} widget with 10 elements and position selection to 5th element
        """

        seq: list[bytes] = [f"{_num}".encode("ascii") for _num in range(10)]
        self.widget = Selection(seq, None)
        self.widget.height = 10  # type: ignore[assignment]
        self.widget.focusedIndex = 5

    def test_selection_down_arrow(self) -> None:
        """
        Send DOWN_ARROW to select element just below the current one
        """
        self.widget.keystrokeReceived(ServerProtocol.DOWN_ARROW, None)  # type: ignore[attr-defined]
        self.assertIs(self.widget.focusedIndex, 6)

    def test_selection_up_arrow(self) -> None:
        """
        Send UP_ARROW to select element just above the current one
        """
        self.widget.keystrokeReceived(ServerProtocol.UP_ARROW, None)  # type: ignore[attr-defined]
        self.assertIs(self.widget.focusedIndex, 4)

    def test_selection_pgdn(self) -> None:
        """
        Send PGDN to select element one page down (here: last element)
        """
        self.widget.keystrokeReceived(ServerProtocol.PGDN, None)  # type: ignore[attr-defined]
        self.assertIs(self.widget.focusedIndex, 9)

    def test_selection_pgup(self) -> None:
        """
        Send PGUP to select element one page up (here: first element)
        """
        self.widget.keystrokeReceived(ServerProtocol.PGUP, None)  # type: ignore[attr-defined]
        self.assertIs(self.widget.focusedIndex, 0)


class TestWidget(Widget):
    triggered: dict[str, bool] = dict()

    def func_F1(self, modifier) -> None:  # type: ignore[no-untyped-def]
        self.triggered["F1"] = True

    def func_HOME(self, modifier) -> None:  # type: ignore[no-untyped-def]
        self.triggered["HOME"] = True

    def func_DOWN_ARROW(self, modifier) -> None:  # type: ignore[no-untyped-def]
        self.triggered["DOWN_ARROW"] = True

    def func_UP_ARROW(self, modifier) -> None:  # type: ignore[no-untyped-def]
        self.triggered["UP_ARROW"] = True

    def func_PGDN(self, modifier) -> None:  # type: ignore[no-untyped-def]
        self.triggered["PGDN"] = True

    def func_PGUP(self, modifier) -> None:  # type: ignore[no-untyped-def]
        self.triggered["PGUP"] = True


class WidgetFunctionKeyTests(TestCase):
    """
    Call functionKeyReceived with key values from insults.ServerProtocol
    """

    def setUp(self) -> None:
        """
        Make dummy widget to receive function keys
        """
        self.widget = TestWidget()

    def test_widget_function_key_f1(self) -> None:
        """
        Widget receives F1 key
        """
        self.widget.functionKeyReceived(ServerProtocol.F1, None)  # type: ignore[attr-defined]
        self.assertTrue(self.widget.triggered["F1"])

    def test_widget_function_key_home(self) -> None:
        """
        Widget receives HOME key
        """
        self.widget.functionKeyReceived(ServerProtocol.HOME, None)  # type: ignore[attr-defined]
        self.assertTrue(self.widget.triggered["HOME"])

    def test_widget_function_key_down_arrow(self) -> None:
        """
        Widget receives DOWN_ARROW key
        """
        self.widget.functionKeyReceived(ServerProtocol.DOWN_ARROW, None)  # type: ignore[attr-defined]
        self.assertTrue(self.widget.triggered["DOWN_ARROW"])

    def test_widget_function_key_up_arrow(self) -> None:
        """
        Widget receives UP_ARROW key
        """
        self.widget.functionKeyReceived(ServerProtocol.UP_ARROW, None)  # type: ignore[attr-defined]
        self.assertTrue(self.widget.triggered["UP_ARROW"])

    def test_widget_function_key_pgdn(self) -> None:
        """
        Widget receives PGDN key
        """
        self.widget.functionKeyReceived(ServerProtocol.PGDN, None)  # type: ignore[attr-defined]
        self.assertTrue(self.widget.triggered["PGDN"])

    def test_widget_function_key_pgup(self) -> None:
        """
        Widget receives PGUP key
        """
        self.widget.functionKeyReceived(ServerProtocol.PGUP, None)  # type: ignore[attr-defined]
        self.assertTrue(self.widget.triggered["PGUP"])
