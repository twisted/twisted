# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.slides}.
"""

from xml.dom.minidom import Element, Text

from twisted.trial.unittest import TestCase
from twisted.lore.slides import (
    HTMLSlide, splitIntoSlides, insertPrevNextLinks, MagicpointOutput)


class SlidesTests(TestCase):
    """
    Tests for functions in L{twisted.lore.slides}.
    """
    def test_splitIntoSlides(self):
        """
        L{splitIntoSlides} accepts a document and returns a list of two-tuples,
        each element of which contains the title of a slide taken from an I{h2}
        element and the body of that slide.
        """
        parent = Element('html')
        body = Element('body')
        parent.appendChild(body)

        first = Element('h2')
        text = Text()
        text.data = 'first slide'
        first.appendChild(text)
        body.appendChild(first)
        body.appendChild(Element('div'))
        body.appendChild(Element('span'))

        second = Element('h2')
        text = Text()
        text.data = 'second slide'
        second.appendChild(text)
        body.appendChild(second)
        body.appendChild(Element('p'))
        body.appendChild(Element('br'))

        slides = splitIntoSlides(parent)

        self.assertEqual(slides[0][0], 'first slide')
        firstContent = slides[0][1]
        self.assertEqual(firstContent[0].tagName, 'div')
        self.assertEqual(firstContent[1].tagName, 'span')
        self.assertEqual(len(firstContent), 2)

        self.assertEqual(slides[1][0], 'second slide')
        secondContent = slides[1][1]
        self.assertEqual(secondContent[0].tagName, 'p')
        self.assertEqual(secondContent[1].tagName, 'br')
        self.assertEqual(len(secondContent), 2)

        self.assertEqual(len(slides), 2)


    def test_insertPrevNextText(self):
        """
        L{insertPrevNextLinks} appends a text node with the title of the
        previous slide to each node with a I{previous} class and the title of
        the next slide to each node with a I{next} class.
        """
        next = Element('span')
        next.setAttribute('class', 'next')
        container = Element('div')
        container.appendChild(next)
        slideWithNext = HTMLSlide(container, 'first', 0)

        previous = Element('span')
        previous.setAttribute('class', 'previous')
        container = Element('div')
        container.appendChild(previous)
        slideWithPrevious = HTMLSlide(container, 'second', 1)

        insertPrevNextLinks(
            [slideWithNext, slideWithPrevious], None, None)

        self.assertEqual(
            next.toxml(), '<span class="next">second</span>')
        self.assertEqual(
            previous.toxml(), '<span class="previous">first</span>')



class MagicpointOutputTests(TestCase):
    """
    Tests for L{lore.slides.MagicpointOutput}.
    """
    def setUp(self):
        self.filename = self.mktemp()
        self.output = []
        self.spitter = MagicpointOutput(self.output.append,
            filename=self.filename)

        self.parent = Element('html')
        title = Element('title')
        text = Text()
        text.data = "My Title"
        title.appendChild(text)
        self.body = Element('body')
        self.parent.appendChild(title)
        self.parent.appendChild(self.body)


    def test_body(self):
        """
        L{MagicpointOutput.visitNode} emits a verbatim block when it encounters
        a I{body} element.
        """
        link = Element('link')
        link.setAttribute('class', 'author')
        text = Text()
        text.data = u"John Doe"
        link.appendChild(text)
        self.body.appendChild(link)

        head = Element('h2')
        first = Text()
        first.data = u'My Header'
        head.appendChild(first)
        self.body.appendChild(head)

        self.spitter.visitNode(self.parent)
        self.assertEqual(
            ''.join(self.output),
            '%page\n\nMy Title\n\n\n%center\n\n\n\n\nJohn Doe\n%page\n\n'
            'My Title\n\n\n\tMy Header\nJohn Doe%page\n\nMy Header\n\n\n')


    def test_pre(self):
        """
        L{MagicpointOutput.visitNode} emits the 'typewriter' font when it
        encounters a I{pre} element.
        """
        pre = Element('pre')
        text = Text()
        text.data = u"\nfirst line\nsecond line\n\n"
        pre.appendChild(text)
        self.body.appendChild(pre)

        self.spitter.visitNode(self.parent)
        self.assertEqual(
            ''.join(self.output),
            '%page\n\nMy Title\n\n\n%center\n\n\n\n\n%page\n\nMy Title\n\n\n'
            '%font "typewriter", size 4\n first line\n second line\n \n'
            '%font "standard"\n')


