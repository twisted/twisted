# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.lint}.
"""

import sys
from xml.dom import minidom
from cStringIO import StringIO

from twisted.trial.unittest import TestCase
from twisted.lore.lint import getDefaultChecker
from twisted.lore.process import ProcessingFailure



class DefaultTagCheckerTests(TestCase):
    """
    Tests for L{twisted.lore.lint.DefaultTagChecker}.
    """
    def test_quote(self):
        """
        If a non-comment node contains a quote (C{'"'}), the checker returned
        by L{getDefaultChecker} reports an error and raises
        L{ProcessingFailure}.
        """
        documentSource = (
            '<html>'
            '<head><title>foo</title></head>'
            '<body><h1>foo</h1><div>"</div></body>'
            '</html>')
        document = minidom.parseString(documentSource)
        filename = self.mktemp()
        checker = getDefaultChecker()

        output = StringIO()
        patch = self.patch(sys, 'stdout', output)
        self.assertRaises(ProcessingFailure, checker.check, document, filename)
        patch.restore()

        self.assertIn("contains quote", output.getvalue())


    def test_quoteComment(self):
        """
        If a comment node contains a quote (C{'"'}), the checker returned by
        L{getDefaultChecker} does not report an error.
        """
        documentSource = (
            '<html>'
            '<head><title>foo</title></head>'
            '<body><h1>foo</h1><!-- " --></body>'
            '</html>')
        document = minidom.parseString(documentSource)
        filename = self.mktemp()
        checker = getDefaultChecker()

        output = StringIO()
        patch = self.patch(sys, 'stdout', output)
        checker.check(document, filename)
        patch.restore()

        self.assertEqual(output.getvalue(), "")


    def test_aNode(self):
        """
        If there is an <a> tag in the document, the checker returned by
        L{getDefaultChecker} does not report an error.
        """
        documentSource = (
            '<html>'
            '<head><title>foo</title></head>'
            '<body><h1>foo</h1><a>A link.</a></body>'
            '</html>')

        self.assertEquals(self._lintCheck(True, documentSource), "")


    def test_textMatchesRef(self):
        """
        If an I{a} node has a link with a scheme as its contained text, a
        warning is emitted if that link does not match the value of the
        I{href} attribute.
        """
        documentSource = (
            '<html>'
            '<head><title>foo</title></head>'
            '<body><h1>foo</h1>'
            '<a href="http://bar/baz">%s</a>'
            '</body>'
            '</html>')
        self.assertEquals(
            self._lintCheck(True, documentSource % ("http://bar/baz",)), "")
        self.assertIn(
            "link text does not match href",
            self._lintCheck(False, documentSource % ("http://bar/quux",)))


    def _lintCheck(self, expectSuccess, source):
        """
        Lint the given document source and return the output.

        @param expectSuccess: A flag indicating whether linting is expected
            to succeed or not.

        @param source: The document source to lint.

        @return: A C{str} of the output of linting.
        """
        document = minidom.parseString(source)
        filename = self.mktemp()
        checker = getDefaultChecker()

        output = StringIO()
        patch = self.patch(sys, 'stdout', output)
        try:
            try:
                checker.check(document, filename)
            finally:
                patch.restore()
        except ProcessingFailure, e:
            if expectSuccess:
                raise
        else:
            if not expectSuccess:
                self.fail(
                    "Expected checker to fail, but it did not.  "
                    "Output was: %r" % (output.getvalue(),))

        return output.getvalue()
