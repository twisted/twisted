# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#
from twisted.application import tapconvert
from twisted.trial import unittest
from twisted.python import usage

class TestOptions(unittest.TestCase):

    def testNull(self):
        options = tapconvert.ConvertOptions()
        self.assertRaises(usage.UsageError, options.parseOptions, [])

    def testUnrecognizedType(self):
        options = tapconvert.ConvertOptions()
        self.assertRaises(usage.UsageError, options.parseOptions,
                          ['-i', 'foo.lala'])

    def testShortGuess(self):
        options = tapconvert.ConvertOptions()
        options.parseOptions('-i foo.tap -o foo.tax -t xml'.split())
        self.assertEqual(options['typein'], 'pickle')
        self.assertEqual(options['typeout'], 'xml')
        self.assertEqual(options['in'], 'foo.tap')
        self.assertEqual(options['out'], 'foo.tax')
        self.failIf(options['decrypt'])
        self.failIf(options['encrypt'])

    def testShortExplicit(self):
        options = tapconvert.ConvertOptions()
        options.parseOptions('-f source -i foo.tap -o foo.tax -t xml'.split())
        self.assertEqual(options['typein'], 'source')
        self.assertEqual(options['typeout'], 'xml')
        self.assertEqual(options['in'], 'foo.tap')
        self.assertEqual(options['out'], 'foo.tax')
        self.failIf(options['decrypt'])
        self.failIf(options['encrypt'])

    def testLongGuess(self):
        options = tapconvert.ConvertOptions()
        options.parseOptions('--in foo.tap --out foo.tax --typeout xml'.split())
        self.assertEqual(options['typein'], 'pickle')
        self.assertEqual(options['typeout'], 'xml')
        self.assertEqual(options['in'], 'foo.tap')
        self.assertEqual(options['out'], 'foo.tax')
        self.failIf(options['decrypt'])
        self.failIf(options['encrypt'])

    def testLongExplicit(self):
        options = tapconvert.ConvertOptions()
        options.parseOptions('--typein source '
                             '--in foo.tap --out foo.tax --typeout xml'.split())
        self.assertEqual(options['typein'], 'source')
        self.assertEqual(options['typeout'], 'xml')
        self.assertEqual(options['in'], 'foo.tap')
        self.assertEqual(options['out'], 'foo.tax')
        self.failIf(options['decrypt'])
        self.failIf(options['encrypt'])
