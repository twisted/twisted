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
        L{TexiSpitter.visitNode} writes out title information.
        """
        titleElement = Element('title')
        text = Text()
        text.data = u'bar'
        titleElement.appendChild(text)

        self.spitter.visitNode(titleElement)
        self.assertEqual(''.join(self.output), '@node bar\n@section bar\n')


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

