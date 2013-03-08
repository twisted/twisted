# -*- test-case-name: twisted.conch.test.test_text -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest

from twisted.conch.insults import helper, text

A = text.attributes

class Serialization(unittest.TestCase):
    def setUp(self):
        self.attrs = helper.CharacterAttribute()

    def testTrivial(self):
        self.assertEqual(
            text.flatten(A.normal['Hello, world.'], self.attrs),
            'Hello, world.')

    def testBold(self):
        self.assertEqual(
            text.flatten(A.bold['Hello, world.'], self.attrs),
            '\x1b[1mHello, world.')

    def testUnderline(self):
        self.assertEqual(
            text.flatten(A.underline['Hello, world.'], self.attrs),
            '\x1b[4mHello, world.')

    def testBlink(self):
        self.assertEqual(
            text.flatten(A.blink['Hello, world.'], self.attrs),
            '\x1b[5mHello, world.')

    def testReverseVideo(self):
        self.assertEqual(
            text.flatten(A.reverseVideo['Hello, world.'], self.attrs),
            '\x1b[7mHello, world.')

    def testMinus(self):
        self.assertEqual(
            text.flatten(
                A.bold[A.blink['Hello', -A.bold[' world'], '.']],
                self.attrs),
            '\x1b[1;5mHello\x1b[0;5m world\x1b[1;5m.')

    def testForeground(self):
        self.assertEqual(
            text.flatten(
                A.normal[A.fg.red['Hello, '], A.fg.green['world!']],
                self.attrs),
            '\x1b[31mHello, \x1b[32mworld!')

    def testBackground(self):
        self.assertEqual(
            text.flatten(
                A.normal[A.bg.red['Hello, '], A.bg.green['world!']],
                self.attrs),
            '\x1b[41mHello, \x1b[42mworld!')


class EfficiencyTestCase(unittest.TestCase):
    todo = ("flatten() isn't quite stateful enough to avoid emitting a few extra bytes in "
            "certain circumstances, so these tests fail.  The failures take the form of "
            "additional elements in the ;-delimited character attribute lists.  For example, "
            "\\x1b[0;31;46m might be emitted instead of \\x[46m, even if 31 has already been "
            "activated and no conflicting attributes are set which need to be cleared.")

    def setUp(self):
        self.attrs = helper.CharacterAttribute()

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
