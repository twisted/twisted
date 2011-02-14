# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.lore.lmath}.
"""

from xml.dom.minidom import Element, Text

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath

from twisted.lore.lmath import formulaeToImages


class FormulaeTests(TestCase):
    """
    Tests for L{formulaeToImages}.
    """
    def test_insertImages(self):
        """
        L{formulaeToImages} replaces any elements with the I{latexformula}
        class with I{img} elements which refer to external images generated
        based on the latex in the original elements.
        """
        parent = Element('div')
        base = FilePath(self.mktemp())
        base.makedirs()

        macros = Element('span')
        macros.setAttribute('class', 'latexmacros')
        text = Text()
        text.data = 'foo'
        macros.appendChild(text)
        parent.appendChild(macros)

        formula = Element('span')
        formula.setAttribute('class', 'latexformula')
        text = Text()
        text.data = 'bar'
        formula.appendChild(text)
        parent.appendChild(formula)

        # Avoid actually executing the commands to generate images from the
        # latex.  It might be nice to have some assertions about what commands
        # are executed, or perhaps even execute them and make sure an image
        # file is created, but that is a task for another day.
        commands = []
        formulaeToImages(parent, base.path, _system=commands.append)

        self.assertEqual(
            parent.toxml(),
            '<div><span><br/><img src="latexformula0.png"/><br/></span></div>')
