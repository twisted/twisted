# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# 

from cStringIO import StringIO
import os, re, cgi
from twisted.python import text
from twisted.web import domhelpers, microdom
import latex, tree

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
                new = microdom.Element('p')
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
