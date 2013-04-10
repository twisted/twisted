# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the insults windowing module, L{twisted.conch.insults.window}.
"""

from twisted.trial.unittest import TestCase

from twisted.conch.insults.window import (TopWindow, ScrolledArea, TextOutput,
    YieldFocus, TextOutputArea)


class TopWindowTests(TestCase):
    """
    Tests for L{TopWindow}, the root window container class.
    """

    def test_paintScheduling(self):
        """
        Verify that L{TopWindow.repaint} schedules an actual paint to occur
        using the scheduling object passed to its initializer.
        """
        paints = []
        scheduled = []
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



class DummyTerminal(object):
    """
    """
    def __init__(self, lines=[]):
        self.lines = lines


    def write(self, data):
        """
        """
        self.lines.append(data)


    def cursorPosition(self, x, y):
        """
        """
        self.x = x
        self.y = y



class TextOutputTests(TestCase):
    """
    Tests for L{TextOutput}.
    """
    def setUp(self):
        self.size = 80
        self.terminal = DummyTerminal()
        self.output = TextOutput(self.size)


    def test_size(self):
        """
        """
        self.assertEqual(self.output.size, self.size)
        self.assertEqual(self.output.sizeHint(), self.size)


    def test_focusReceived(self):
        """
        """
        try:
            focus = self.output.focusReceived()
        except Exception as e:
            self.assertIsInstance(e, YieldFocus)


    def test_setText(self):
        """
        """
        self.assertEqual(self.output.text, '')
        self.output.setText('btc')
        self.assertEqual(self.output.text, 'btc')


    def test_render(self):
        """
        """
        self.output.setText('batman')
        self.output.render(3, 4, self.terminal)

        self.assertEqual(self.terminal.x, 0)
        self.assertEqual(self.terminal.y, 0)
        self.assertEqual(self.terminal.lines, ['bat'])



class TextOutputAreaTests(TestCase):
    """
    Tests for L{TextOutputArea}.
    """
    def setUp(self):
        self.size = 80
        self.terminal = DummyTerminal([])
        self.output = TextOutputArea(self.size)


    def test_longLines(self):
        """
        """
        self.assertEqual(self.output.longLines, TextOutputArea.WRAP)


    def test_renderTruncate(self):
        """
        """
        self.output = TextOutputArea(self.size, TextOutputArea.TRUNCATE)
        self.assertEqual(self.output.longLines, TextOutputArea.TRUNCATE)

        self.output.setText('catwoman')
        self.output.render(4, 4, self.terminal)
        self.assertEqual(self.terminal.lines, ['catw'])


    def test_renderWrap(self):
        """
        """
        inString = '12345678'
        self.output.setText(inString)
        self.output.render(4, 4, self.terminal)

        self.assertEqual(self.terminal.x, 0)
        self.assertEqual(self.terminal.y, 0)
        self.assertEqual(self.terminal.lines, [inString])



class ScrolledAreaTests(TestCase):
    """
    Tests for L{ScrolledArea}, a widget which creates a viewport containing
    another widget and can reposition that viewport using scrollbars.
    """
    def test_parent(self):
        """
        The parent of the widget passed to L{ScrolledArea} is set to a new
        L{Viewport} created by the L{ScrolledArea} which itself has the
        L{ScrolledArea} instance as its parent.
        """
        widget = TextOutput()
        scrolled = ScrolledArea(widget)
        self.assertIdentical(widget.parent, scrolled._viewport)
        self.assertIdentical(scrolled._viewport.parent, scrolled)

