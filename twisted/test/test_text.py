
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest
from twisted.python import text
from cStringIO import StringIO


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
        self.sampleSplitText = sampleText.split()

        self.output = text.wordWrap(sampleText, lineWidth)

    def test_wordCount(self):
        """Compare the number of words."""
        words = []
        for line in self.output:
            words.extend(line.split())
        wordCount = len(words)
        sampleTextWordCount = len(self.sampleSplitText)

        self.assertEqual(wordCount, sampleTextWordCount)

    def test_wordMatch(self):
        """Compare the lists of words."""

        words = []
        for line in self.output:
            words.extend(line.split())

        # Using assertEqual here prints out some
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


class SplitTest(unittest.TestCase):
    """Tests for text.splitQuoted()"""

    def test_oneWord(self):
        """Splitting strings with one-word phrases."""
        s = 'This code "works."'
        r = text.splitQuoted(s)
        self.assertEqual(['This', 'code', 'works.'], r)

    def test_multiWord(self):
        s = 'The "hairy monkey" likes pie.'
        r = text.splitQuoted(s)
        self.assertEqual(['The', 'hairy monkey', 'likes', 'pie.'], r)

    # Some of the many tests that would fail:

    #def test_preserveWhitespace(self):
    #    phrase = '"MANY     SPACES"'
    #    s = 'With %s between.' % (phrase,)
    #    r = text.splitQuoted(s)
    #    self.assertEqual(['With', phrase, 'between.'], r)

    #def test_escapedSpace(self):
    #    s = r"One\ Phrase"
    #    r = text.splitQuoted(s)
    #    self.assertEqual(["One Phrase"], r)

class StrFileTest(unittest.TestCase):
    def setUp(self):
        self.io = StringIO("this is a test string")

    def tearDown(self):
        pass

    def test_1_f(self):
        self.assertEqual(False, text.strFile("x", self.io))

    def test_1_1(self):
        self.assertEqual(True, text.strFile("t", self.io))

    def test_1_2(self):
        self.assertEqual(True, text.strFile("h", self.io))

    def test_1_3(self):
        self.assertEqual(True, text.strFile("i", self.io))

    def test_1_4(self):
        self.assertEqual(True, text.strFile("s", self.io))

    def test_1_5(self):
        self.assertEqual(True, text.strFile("n", self.io))

    def test_1_6(self):
        self.assertEqual(True, text.strFile("g", self.io))

    def test_3_1(self):
        self.assertEqual(True, text.strFile("thi", self.io))

    def test_3_2(self):
        self.assertEqual(True, text.strFile("his", self.io))

    def test_3_3(self):
        self.assertEqual(True, text.strFile("is ", self.io))

    def test_3_4(self):
        self.assertEqual(True, text.strFile("ing", self.io))

    def test_3_f(self):
        self.assertEqual(False, text.strFile("bla", self.io))

    def test_large_1(self):
        self.assertEqual(True, text.strFile("this is a test", self.io))

    def test_large_2(self):
        self.assertEqual(True, text.strFile("is a test string", self.io))

    def test_large_f(self):
        self.assertEqual(False, text.strFile("ds jhfsa k fdas", self.io))

    def test_overlarge_f(self):
        self.assertEqual(False, text.strFile("djhsakj dhsa fkhsa s,mdbnfsauiw bndasdf hreew", self.io))

    def test_self(self):
        self.assertEqual(True, text.strFile("this is a test string", self.io))

    def test_insensitive(self):
        self.assertEqual(True, text.strFile("ThIs is A test STRING", self.io, False))



class DeprecationTest(unittest.TestCase):
    """
    Tests for deprecations in L{twisted.python.text}
    """

    def test_docstringLStrip(self):
        """
        L{docstringLStrip} is deprecated as of 10.2.0
        """
        text.docstringLStrip("")
        warningsShown = self.flushWarnings([self.test_docstringLStrip])
        self.assertEqual(1, len(warningsShown))
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(warningsShown[0]['message'],
                          "twisted.python.text.docstringLStrip was "
                          "deprecated in Twisted 10.2.0: Please use "
                          "inspect.getdoc instead.")



testCases = [WrapTest, SplitTest, StrFileTest]
