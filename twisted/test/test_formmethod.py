# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Test cases for formmethod module.
"""

from twisted.trial import unittest

from twisted.python import formmethod


class ArgumentTestCase(unittest.TestCase):

    def argTest(self, argKlass, testPairs, badValues, *args, **kwargs):
        arg = argKlass("name", *args, **kwargs)
        for val, result in testPairs:
            self.assertEquals(arg.coerce(val), result)
        for val in badValues:
            self.assertRaises(formmethod.InputError, arg.coerce, val)
    
    def testString(self):
        self.argTest(formmethod.String, [("a", "a"), (1, "1")], ())

    def testInt(self):
        self.argTest(formmethod.Integer, [("3", 3), ("-2", -2)], ("q", "2.3"))

    def testFloat(self):
        self.argTest(formmethod.Float, [("3", 3.0), ("-2.3", -2.3)], ("q", "2.3z"))

    def testChoice(self):
        choices = [("a", "apple", "an apple"),
                   ("b", "banana", "ook")]
        self.argTest(formmethod.Choice, [("a", "apple"), ("b", "banana")],
                     ("c", 1), choices=choices)

    def testFlags(self):
        flags =  [("a", "apple", "an apple"),
                  ("b", "banana", "ook")]
        self.argTest(formmethod.Flags,
                     [(["a"], ["apple"]), (["b", "a"], ["banana", "apple"])],
                     (["a", "c"], ["fdfs"]),
                     flags=flags)

    def testBoolean(self):
        tests =  [("yes", 1), ("", 0), ("False", 0), ("no", 0)]
        self.argTest(formmethod.Boolean, tests, ())

    
