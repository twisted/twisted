# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
DocBook output support for Lore.
"""

import os, cgi
from xml.dom import minidom as dom

from twisted.lore import latex


class DocbookSpitter(latex.BaseLatexSpitter):

    currentLevel = 1

    def writeNodeData(self, node):
        self.writer(node.data)

    def visitNode_body(self, node):
        self.visitNodeDefault(node)
        self.writer('</section>'*self.currentLevel)

    def visitNodeHeader(self, node):
        level = int(node.tagName[1])
        difference, self.currentLevel = level-self.currentLevel, level
        self.writer('<section>'*difference+'</section>'*-difference)
        if difference<=0:
            self.writer('</section>\n<section>')
        self.writer('<title>')
        self.visitNodeDefault(node)

    def visitNode_a_listing(self, node):
        fileName = os.path.join(self.currDir, node.getAttribute('href'))
        self.writer('<programlisting>\n')
        self.writer(cgi.escape(open(fileName).read()))
        self.writer('</programlisting>\n')

    def visitNode_a_href(self, node):
        self.visitNodeDefault(node)

    def visitNode_a_name(self, node):
        self.visitNodeDefault(node)

    def visitNode_li(self, node):
        for child in node.childNodes:
            if getattr(child, 'tagName', None) != 'p':
                new = dom.Element('p')
                new.childNodes = [child]
                node.replaceChild(new, child)
        self.visitNodeDefault(node)

    visitNode_h2 = visitNode_h3 = visitNode_h4 = visitNodeHeader
    end_h2 = end_h3 = end_h4 = '</title><para />'
    start_title, end_title = '<section><title>', '</title><para />'
    start_p, end_p = '<para>', '</para>'
    start_strong, end_strong = start_em, end_em = '<emphasis>', '</emphasis>'
    start_span_footnote, end_span_footnote = '<footnote><para>', '</para></footnote>'
    start_q = end_q = '"'
    start_pre, end_pre = '<programlisting>', '</programlisting>'
    start_div_note, end_div_note = '<note>', '</note>'
    start_li, end_li = '<listitem>', '</listitem>'
    start_ul, end_ul = '<itemizedlist>', '</itemizedlist>'
    start_ol, end_ol = '<orderedlist>', '</orderedlist>'
    start_dl, end_dl = '<variablelist>', '</variablelist>'
    start_dt, end_dt = '<varlistentry><term>', '</term>'
    start_dd, end_dd = '<listitem><para>', '</para></listitem></varlistentry>'
