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
    Fake terminal, used for storing lines and position.

    @ivar lines: List with three-tuples of C{(text, column, line)}.
    @type lines: C{list}
    """
    def __init__(self):
        self.lines = []


    def write(self, data):
        """
        Stores a new line.

        @param data: A new line.
        @type data: C{str}
        """
        self.lines.append((data, self.column, self.line))


    def cursorPosition(self, column, line):
        """
        Move the cursor to the given C{line} and C{column}.

        @param column: Column position of the cursor.
        @type column: C{int}
        @param line: Line position of the cursor.
        @type line: C{str}
        """
        self.column = column
        self.line = line



class TextOutputTests(TestCase):
    """
    Tests for L{TextOutput}.
    """
    def setUp(self):
        self.size = 80
        self.inputString = '12345 btc'
        self.terminal = DummyTerminal()
        self.output = TextOutput(self.size)


    def test_size(self):
        """
        L{TextOutput.sizeHint} and L{TextOutput.size} should be equal.
        """
        self.assertEqual(self.output.size, self.size)
        self.assertEqual(self.output.sizeHint(), self.output.size)


    def test_focusReceived(self):
        """
        L{TextOutput.focusReceived} returns a L{YieldFocus} instance.
        """
        self.assertRaises(YieldFocus, self.output.focusReceived)


    def test_setText(self):
        """
        Passing a string to L{TextOutput.setText} stores it in the
        L{TextOutput.text} attribute.
        """
        self.assertEqual(self.output.text, '')
        self.output.setText(self.inputString)
        self.assertEqual(self.output.text, self.inputString)


    def test_render(self):
        """
        L{TextOutput.render} writes input text in a single line to it's
        terminal.
        """
        self.output.setText(self.inputString)
        self.output.render(len(self.inputString), 1, self.terminal)

        self.assertEqual(self.terminal.column, 0)
        self.assertEqual(self.terminal.line, 0)
        self.assertEqual(self.terminal.lines, [(self.inputString, 0, 0)])


    def test_renderWithPadding(self):
        """
        L{TextOutput.render} adds padding if the column width is greater than
        the length of the input string.
        """
        padding = 5
        columnWidth = len(self.inputString) + padding
        outputText = self.inputString + ' ' * padding

        self.output.setText(self.inputString)
        self.output.render(columnWidth, 1, self.terminal)

        self.assertEqual(self.terminal.lines, [(outputText, 0, 0)])


    def test_renderTruncated(self):
        """
        L{TextOutput.render} truncates the input string if the column width is
        smaller than the length of the input string.
        """
        self.output.setText(self.inputString)
        self.output.render(3, 1, self.terminal)

        self.assertEqual(self.terminal.lines, [('123', 0, 0)])



class TextOutputAreaTests(TestCase):
    """
    Tests for L{TextOutputArea}.
    """
    def setUp(self):
        self.size = 80
        self.inputString = 'this is a test'
        self.terminal = DummyTerminal()
        self.output = TextOutputArea(self.size)


    def test_longLines(self):
        """
        L{TextOutputArea.longLines} is set to L{TextOutputArea.WRAP} by
        default.
        """
        self.assertEqual(self.output.longLines, TextOutputArea.WRAP)


    def test_renderWrap(self):
        """
        L{TextOutputArea.render} wraps the lines by default.
        """
        self.output.setText(self.inputString)
        self.output.render(4, 10, self.terminal)

        self.assertEqual(self.terminal.lines, [
            ('this', 0, 0), ('is a', 0, 1), ('test', 0, 2)])
        self.assertEqual(self.terminal.column, 0)
        self.assertEqual(self.terminal.line, 2)


    def test_renderTruncate(self):
        """
        Setting L{TextOutputArea.longLines} to L{TextOutputArea.TRUNCATE}
        renders lines with a maximum length of C{width}.
        """
        self.output = TextOutputArea(self.size, TextOutputArea.TRUNCATE)
        self.assertEqual(self.output.longLines, TextOutputArea.TRUNCATE)

        self.output.setText(self.inputString)
        self.output.render(4, 10, self.terminal)
        self.assertEqual(self.terminal.lines, [('this', 0, 0)])
        self.assertEqual(self.terminal.column, 0)
        self.assertEqual(self.terminal.line, 0)



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
        self.assertIs(widget.parent, scrolled._viewport)
        self.assertIs(scrolled._viewport.parent, scrolled)
