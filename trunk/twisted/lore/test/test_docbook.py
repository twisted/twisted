# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.docbook}.
"""

from xml.dom.minidom import Element, Text

from twisted.trial.unittest import TestCase
from twisted.lore.docbook import DocbookSpitter


class DocbookSpitterTests(TestCase):
    """
    Tests for L{twisted.lore.docbook.DocbookSpitter}.
    """
    def test_li(self):
        """
        L{DocbookSpitter} wraps any non-I{p} elements found intside any I{li}
        elements with I{p} elements.
        """
        output = []
        spitter = DocbookSpitter(output.append)

        li = Element('li')
        li.appendChild(Element('p'))
        text = Text()
        text.data = 'foo bar'
        li.appendChild(text)

        spitter.visitNode(li)
        self.assertEqual(
            ''.join(output),
            '<listitem><para></para><para>foo bar</para></listitem>')
