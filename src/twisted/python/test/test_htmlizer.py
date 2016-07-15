# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.htmlizer}.
"""

from StringIO import StringIO

from twisted.trial.unittest import TestCase
from twisted.python.htmlizer import filter


class FilterTests(TestCase):
    """
    Tests for L{twisted.python.htmlizer.filter}.
    """
    def test_empty(self):
        """
        If passed an empty input file, L{filter} writes a I{pre} tag containing
        only an end marker to the output file.
        """
        input = StringIO("")
        output = StringIO()
        filter(input, output)
        self.assertEqual(output.getvalue(), '<pre><span class="py-src-endmarker"></span></pre>\n')


    def test_variable(self):
        """
        If passed an input file containing a variable access, L{filter} writes
        a I{pre} tag containing a I{py-src-variable} span containing the
        variable.
        """
        input = StringIO("foo\n")
        output = StringIO()
        filter(input, output)
        self.assertEqual(
            output.getvalue(),
            '<pre><span class="py-src-variable">foo</span><span class="py-src-newline">\n'
            '</span><span class="py-src-endmarker"></span></pre>\n')
