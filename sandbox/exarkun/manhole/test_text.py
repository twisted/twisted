
from twisted.trial import unittest

import text
import insults
import helper

A = text.attributes

class Serialization(unittest.TestCase):
    def setUp(self):
        self.attrs = helper.CharacterAttribute()

    def testTrivial(self):
        self.assertEquals(
            text.flatten(A.normal['Hello, world.'], self.attrs),
            'Hello, world.')

    def testBold(self):
        self.assertEquals(
            text.flatten(A.bold['Hello, world.'], self.attrs),
            '\x1b[1mHello, world.')

    def testUnderline(self):
        self.assertEquals(
            text.flatten(A.underline['Hello, world.'], self.attrs),
            '\x1b[4mHello, world.')

    def testBlink(self):
        self.assertEquals(
            text.flatten(A.blink['Hello, world.'], self.attrs),
            '\x1b[5mHello, world.')

    def testReverseVideo(self):
        self.assertEquals(
            text.flatten(A.reverseVideo['Hello, world.'], self.attrs),
            '\x1b[7mHello, world.')

    def testNesting(self):
        self.assertEquals(
            text.flatten(A.bold['Hello, ', A.underline['world.']], self.attrs),
            '\x1b[1mHello, \x1b[4mworld.')
