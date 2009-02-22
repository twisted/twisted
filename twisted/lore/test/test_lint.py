# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.lint}.
"""

import sys
from xml.dom import minidom
from StringIO import StringIO

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
