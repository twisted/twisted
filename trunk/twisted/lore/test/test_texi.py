# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.texi}.
"""

from xml.dom.minidom import Element, Text

from twisted.trial.unittest import TestCase
from twisted.lore.texi import TexiSpitter


class TexiSpitterTests(TestCase):
    """
    Tests for L{TexiSpitter}.
    """
    def setUp(self):
        self.filename = self.mktemp()
        self.output = []
        self.spitter = TexiSpitter(self.output.append, filename=self.filename)


    def test_title(self):
        """
        L{TexiSpitter.visitNode} emits I{@node} and I{@section} blocks when it
        encounters a I{title} element.
        """
        titleElement = Element('title')
        text = Text()
        text.data = u'bar'
        titleElement.appendChild(text)

        self.spitter.visitNode(titleElement)
        self.assertEqual(''.join(self.output), '@node bar\n@section bar\n')


    def test_titleWithHeader(self):
        """
        L{TexiSpitter.visitNode} emits I{@subsection} and I{@menu} blocks when
        it encounters a header (h2 or h3) in a I{title} element.
        """
        titleElement = Element('title')
        text = Text()
        text.data = u'bar'
        titleElement.appendChild(text)

        head = Element('h2')
        first = Text()
        first.data = u'header1'
        head.appendChild(first)
        titleElement.appendChild(head)

        self.spitter.visitNode(titleElement)
        self.assertEqual(''.join(self.output),
            '@node bar\n\n@node header1\n\n\n@subsection header1\n\n'
            '@section bar\n\n@node header1\n\n\n@subsection header1\n\n'
            '@menu\n* header1::\n@end menu\n')


    def test_pre(self):
        """
        L{TexiSpitter.visitNode} emits a verbatim block when it encounters a
        I{pre} element.
        """
        preElement = Element('pre')
        text = Text()
        text.data = u'foo'
        preElement.appendChild(text)

        self.spitter.visitNode(preElement)
        self.assertEqual(''.join(self.output),
            '@verbatim\nfoo\n@end verbatim\n')


    def test_code(self):
        """
        L{TexiSpitter.visitNode} emits a C{@code} block when it encounters a
        I{code} element.
        """
        codeElement = Element('code')
        text = Text()
        text.data = u'print'
        codeElement.appendChild(text)

        self.spitter.visitNode(codeElement)
        self.assertEqual(''.join(self.output), "@code{print}")

