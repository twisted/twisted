
from twisted.trial import unittest

import text
import insults
import helper

class Serialization(unittest.TestCase):
    def testTrivial(self):
        a = text.attributes
        attrs = helper.CharacterAttribute()
        output = a.normal['Hello, world.']

        self.assertEquals(text.flatten(output, attrs), 'Hello, world.')

