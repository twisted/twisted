
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

from pyunit import unittest
from twisted.python import text
import string

sampleText = \
"""Every attempt to employ mathematical methods in the study of chemical
questions must be considered profoundly irrational and contrary to the
spirit of chemistry ...  If mathematical analysis should ever hold a
prominent place in chemistry - an aberration which is happily almost
impossible - it would occasion a rapid and widespread degeneration of that
science.
           --  Auguste Comte, Philosophie Positive, Paris, 1838
"""

lineWidth = 72

def set_lineWidth(n):
    global lineWidth
    lineWidth = n

class WrapTest(unittest.TestCase):
    def setUp(self):
        self.sampleSplitText = string.split(sampleText)

        self.output = text.wordWrap(sampleText, lineWidth)

    def test_wordCount(self):
        """Compare the number of words."""
        words = []
        for line in self.output:
            words.extend(string.split(line))
        wordCount = len(words)
        sampleTextWordCount = len(self.sampleSplitText)

        self.failUnlessEqual(wordCount, sampleTextWordCount)

    def test_wordMatch(self):
        """Compare the lists of words."""

        words = []
        for line in self.output:
            words.extend(string.split(line))

        # Using failUnlessEqual here prints out some
        # rather too long lists.
        self.failUnless(self.sampleSplitText == words)

    def test_lineLength(self):
        """Check the length of the lines."""
        failures = []
        for line in self.output:
            if not len(line) <= lineWidth:
                failures.append(len(line))

        if failures:
            self.fail("%d of %d lines were too long.\n"
                      "%d < %s" % (len(failures), len(self.output),
                                   lineWidth, failures))


testCases = [WrapTest]
