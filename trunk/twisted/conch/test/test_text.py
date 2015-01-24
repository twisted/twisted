# -*- test-case-name: twisted.conch.test.test_text -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest

from twisted.conch.insults import helper, text
from twisted.conch.insults.text import attributes as A



class FormattedTextTests(unittest.TestCase):
    """
    Tests for assembling formatted text.
    """
    def test_trivial(self):
        """
        Using no formatting attributes produces no VT102 control sequences in
        the flattened output.
        """
        self.assertEqual(
            text.assembleFormattedText(A.normal['Hello, world.']),
            'Hello, world.')


    def test_bold(self):
        """
        The bold formatting attribute, L{A.bold}, emits the VT102 control
        sequence to enable bold when flattened.
        """
        self.assertEqual(
            text.assembleFormattedText(A.bold['Hello, world.']),
            '\x1b[1mHello, world.')


    def test_underline(self):
        """
        The underline formatting attribute, L{A.underline}, emits the VT102
        control sequence to enable underlining when flattened.
        """
        self.assertEqual(
            text.assembleFormattedText(A.underline['Hello, world.']),
            '\x1b[4mHello, world.')


    def test_blink(self):
        """
        The blink formatting attribute, L{A.blink}, emits the VT102 control
        sequence to enable blinking when flattened.
        """
        self.assertEqual(
            text.assembleFormattedText(A.blink['Hello, world.']),
            '\x1b[5mHello, world.')


    def test_reverseVideo(self):
        """
        The reverse-video formatting attribute, L{A.reverseVideo}, emits the
        VT102 control sequence to enable reversed video when flattened.
        """
        self.assertEqual(
            text.assembleFormattedText(A.reverseVideo['Hello, world.']),
            '\x1b[7mHello, world.')


    def test_minus(self):
        """
        Formatting attributes prefixed with a minus (C{-}) temporarily disable
        the prefixed attribute, emitting no VT102 control sequence to enable
        it in the flattened output.
        """
        self.assertEqual(
            text.assembleFormattedText(
                A.bold[A.blink['Hello', -A.bold[' world'], '.']]),
            '\x1b[1;5mHello\x1b[0;5m world\x1b[1;5m.')


    def test_foreground(self):
        """
        The foreground color formatting attribute, L{A.fg}, emits the VT102
        control sequence to set the selected foreground color when flattened.
        """
        self.assertEqual(
            text.assembleFormattedText(
                A.normal[A.fg.red['Hello, '], A.fg.green['world!']]),
            '\x1b[31mHello, \x1b[32mworld!')


    def test_background(self):
        """
        The background color formatting attribute, L{A.bg}, emits the VT102
        control sequence to set the selected background color when flattened.
        """
        self.assertEqual(
            text.assembleFormattedText(
                A.normal[A.bg.red['Hello, '], A.bg.green['world!']]),
            '\x1b[41mHello, \x1b[42mworld!')


    def test_flattenDeprecated(self):
        """
        L{twisted.conch.insults.text.flatten} emits a deprecation warning when
        imported or accessed.
        """
        warningsShown = self.flushWarnings([self.test_flattenDeprecated])
        self.assertEqual(len(warningsShown), 0)

        # Trigger the deprecation warning.
        text.flatten

        warningsShown = self.flushWarnings([self.test_flattenDeprecated])
        self.assertEqual(len(warningsShown), 1)
        self.assertEqual(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            'twisted.conch.insults.text.flatten was deprecated in Twisted '
            '13.1.0: Use twisted.conch.insults.text.assembleFormattedText '
            'instead.')



class EfficiencyTests(unittest.TestCase):
    todo = ("flatten() isn't quite stateful enough to avoid emitting a few extra bytes in "
            "certain circumstances, so these tests fail.  The failures take the form of "
            "additional elements in the ;-delimited character attribute lists.  For example, "
            "\\x1b[0;31;46m might be emitted instead of \\x[46m, even if 31 has already been "
            "activated and no conflicting attributes are set which need to be cleared.")

    def setUp(self):
        self.attrs = helper._FormattingState()

    def testComplexStructure(self):
        output = A.normal[
            A.bold[
                A.bg.cyan[
                    A.fg.red[
                        "Foreground Red, Background Cyan, Bold",
                        A.blink[
                            "Blinking"],
                        -A.bold[
                            "Foreground Red, Background Cyan, normal"]],
                    A.fg.green[
                        "Foreground Green, Background Cyan, Bold"]]]]

        self.assertEqual(
            text.flatten(output, self.attrs),
            "\x1b[1;31;46mForeground Red, Background Cyan, Bold"
            "\x1b[5mBlinking"
            "\x1b[0;31;46mForeground Red, Background Cyan, normal"
            "\x1b[1;32;46mForeground Green, Background Cyan, Bold")

    def testNesting(self):
        self.assertEqual(
            text.flatten(A.bold['Hello, ', A.underline['world.']], self.attrs),
            '\x1b[1mHello, \x1b[4mworld.')

        self.assertEqual(
            text.flatten(
                A.bold[A.reverseVideo['Hello, ', A.normal['world'], '.']],
                self.attrs),
            '\x1b[1;7mHello, \x1b[0mworld\x1b[1;7m.')
