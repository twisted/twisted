# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.latex}.
"""

import os.path
from xml.dom.minidom import Comment, Element, Text

from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase
from twisted.lore.latex import LatexSpitter, getLatexText


class LatexHelperTests(TestCase):
    """
    Tests for free functions in L{twisted.lore.latex}.
    """
    def test_getLatexText(self):
        """
        L{getLatexText} calls the writer function with all of the text at or
        beneath the given node.  Non-ASCII characters are encoded using
        UTF-8.
        """
        node = Element('foo')
        text = Text()
        text.data = u"foo \N{SNOWMAN}"
        node.appendChild(text)
        result = []
        getLatexText(node, result.append)
        self.assertEqual(result, [u"foo \N{SNOWMAN}".encode('utf-8')])



class LatexSpitterTests(TestCase):
    """
    Tests for L{LatexSpitter}.
    """
    def setUp(self):
        self.filename = self.mktemp()
        self.output = []
        self.spitter = LatexSpitter(self.output.append, filename=self.filename)


    def test_head(self):
        """
        L{LatexSpitter.visitNode} writes out author information for each
        I{link} element with a I{rel} attribute set to I{author}.
        """
        head = Element('head')
        first = Element('link')
        first.setAttribute('rel', 'author')
        first.setAttribute('title', 'alice')
        second = Element('link')
        second.setAttribute('rel', 'author')
        second.setAttribute('href', 'http://example.com/bob')
        third = Element('link')
        third.setAttribute('rel', 'author')
        third.setAttribute('href', 'mailto:carol@example.com')
        head.appendChild(first)
        head.appendChild(second)
        head.appendChild(third)

        self.spitter.visitNode(head)

        self.assertEqual(
            ''.join(self.output),
            '\\author{alice \\and $<$http://example.com/bob$>$ \\and $<$carol@example.com$>$}')


    def test_pre(self):
        """
        L{LatexSpitter.visitNode} emits a verbatim block when it encounters a
        I{pre} element.
        """
        pre = Element('pre')
        text = Text()
        text.data = u"\n\n\nfoo\nbar\n\n\n"
        pre.appendChild(text)

        self.spitter.visitNode(pre)
        self.assertEqual(
            ''.join(self.output),
            '\\begin{verbatim}\nfoo\nbar\n\\end{verbatim}\n')


    def test_code(self):
        """
        L{LatexSpitter.visitNode} emits a C{texttt} block when it encounters a
        I{code} element and inserts optional linebreaks at sensible places in
        absolute python names.
        """
        code = Element('code')
        text = Text()
        text.data = u"print this: twisted.lore.latex"
        code.appendChild(text)

        self.spitter.visitNode(code)
        self.assertEqual(
            ''.join(self.output),
            "\\texttt{print this: twisted.\\linebreak[1]lore.\\"
            "linebreak[1]latex}")


    def test_skipComments(self):
        """
        L{LatexSpitter.visitNode} writes nothing to its output stream for
        comments.
        """
        self.spitter.visitNode(Comment('foo'))
        self.assertNotIn('foo', ''.join(self.output))


    def test_anchorListing(self):
        """
        L{LatexSpitter.visitNode} emits a verbatim block when it encounters a
        code listing (represented by an I{a} element with a I{listing} class).
        """
        path = FilePath(self.mktemp())
        path.setContent('\n\nfoo\nbar\n\n\n')
        listing = Element('a')
        listing.setAttribute('class', 'listing')
        listing.setAttribute('href', path.path)
        self.spitter.visitNode(listing)
        self.assertEqual(
            ''.join(self.output),
            "\\begin{verbatim}\n"
            "foo\n"
            "bar\n"
            "\\end{verbatim}\\parbox[b]{\\linewidth}{\\begin{center} --- "
            "\\begin{em}temp\\end{em}\\end{center}}")


    def test_anchorListingSkipLines(self):
        """
        When passed an I{a} element with a I{listing} class and an I{skipLines}
        attribute, L{LatexSpitter.visitNode} emits a verbatim block which skips
        the indicated number of lines from the beginning of the source listing.
        """
        path = FilePath(self.mktemp())
        path.setContent('foo\nbar\n')
        listing = Element('a')
        listing.setAttribute('class', 'listing')
        listing.setAttribute('skipLines', '1')
        listing.setAttribute('href', path.path)
        self.spitter.visitNode(listing)
        self.assertEqual(
            ''.join(self.output),
            "\\begin{verbatim}\n"
            "bar\n"
            "\\end{verbatim}\\parbox[b]{\\linewidth}{\\begin{center} --- "
            "\\begin{em}temp\\end{em}\\end{center}}")


    def test_anchorRef(self):
        """
        L{LatexSpitter.visitNode} emits a footnote when it encounters an I{a}
        element with an I{href} attribute with a network scheme.
        """
        listing = Element('a')
        listing.setAttribute('href', 'http://example.com/foo')
        self.spitter.visitNode(listing)
        self.assertEqual(
            ''.join(self.output),
            "\\footnote{http://example.com/foo}")


    def test_anchorName(self):
        """
        When passed an I{a} element with a I{name} attribute,
        L{LatexSpitter.visitNode} emits a label.
        """
        listing = Element('a')
        listing.setAttribute('name', 'foo')
        self.spitter.visitNode(listing)
        self.assertEqual(
            ''.join(self.output),
            "\\label{%sHASHfoo}" % (
                os.path.abspath(self.filename).replace('\\', '/'),))
