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

from twisted.web import microdom, domhelpers
from twisted.python import text
import os, re
from cStringIO import StringIO

import urlparse

import tree

escapingRE = re.compile(r'([#$%&_{}^~\\])')
lowerUpperRE = re.compile(r'([a-z])([A-Z])')

def latexEscape(text):
    text = escapingRE.sub(lambda x: (x.group()=='\\' and '$\\backslash$') or
                                    '\\'+x.group(), text)
    return text.replace('\n', ' ')

entities = { 'amp': '&', 'gt': '>', 'lt': '<', 'quot': '"',
             'copy': '\\copyright'}

def getLatexText(node, writer, filter=lambda x:x, entities=entities):
    if hasattr(node, 'eref'):
        return writer(entities.get(node.eref, ''))
    if hasattr(node, 'data'):
        return writer(filter(node.data))
    for child in node.childNodes:
        getLatexText(child, writer, filter, entities)

class BaseLatexSpitter:

    def __init__(self, writer, currDir='.', filename=''):
        self.writer = writer
        self.currDir = currDir
        self.filename = filename

    def visitNode(self, node):
        if not hasattr(node, 'tagName'):
            self.writeNodeData(node)
            return
        getattr(self, 'visitNode_'+node.tagName, self.visitNodeDefault)(node)

    def visitNodeDefault(self, node):
        self.writer(getattr(self, 'start_'+node.tagName, None) or '')
        for child in node.childNodes:
            self.visitNode(child)
        self.writer(getattr(self, 'end_'+node.tagName, None) or '')

    def visitNode_a(self, node):
        if node.hasAttribute('class'):
            if node.getAttribute('class').endswith('listing'):
                return self.visitNode_a_listing(node)
        if node.hasAttribute('href'):
            return self.visitNode_a_href(node)
        if node.hasAttribute('name'):
            return self.visitNode_a_name(node)
        self.visitNodeDefault(node)

    def visitNode_span(self, node):
        if not node.hasAttribute('class'):
            return self.visitNodeDefault(node)
        node.tagName += '_'+node.getAttribute('class')
        self.visitNode(node)

    visitNode_div = visitNode_span

    def visitNode_h1(self, node):
        pass

    def visitNode_style(self, node):
        pass


class LatexSpitter(BaseLatexSpitter):

    baseLevel = 0

    def writeNodeData(self, node):
        buf = StringIO()
        getLatexText(node, buf.write, latexEscape)
        self.writer(buf.getvalue().replace('<', '$<$').replace('>', '$>$'))

    def visitNode_pre(self, node):
        self.writer('\\begin{verbatim}\n')
        buf = StringIO()
        getLatexText(node, buf.write)
        self.writer(text.removeLeadingTrailingBlanks(buf.getvalue()))
        self.writer('\\end{verbatim}\n')

    def visitNode_code(self, node):
        fout = StringIO()
        getLatexText(node, fout.write, latexEscape)
        data = lowerUpperRE.sub(r'\1\\linebreak[1]\2', fout.getvalue())
        data = data[:1] + data[1:].replace('.', '.\\linebreak[1]')
        self.writer('\\texttt{'+data+'}')

    def visitNode_img(self, node):
        fileName = os.path.join(self.currDir, node.getAttribute('src'))
        target, ext = os.path.splitext(fileName)
        m = getattr(self, 'convert_'+ext[1:], None)
        if not m:
            return
        target = os.path.join(self.currDir, os.path.basename(target)+'.eps')
        m(fileName, target)
        target = os.path.basename(target)
        self.writer('\\includegraphics{%s}\n' % target)

    def convert_png(self, src, target):
        os.system("pngtopnm %s | pnmtops > %s" % (src, target))

    def visitNodeHeader(self, node):
        level = (int(node.tagName[1])-2)+self.baseLevel
        self.writer('\n\n\\'+level*'sub'+'section{')
        spitter = HeadingLatexSpitter(self.writer, self.currDir, self.filename)
        spitter.visitNodeDefault(node)
        self.writer('}\n')

    def visitNode_a_listing(self, node):
        fileName = os.path.join(self.currDir, node.getAttribute('href'))
        self.writer('\\begin{verbatim}\n')
        self.writer(open(fileName).read())
        self.writer('\\end{verbatim}')
        # Write a caption for this source listing
        self.writer('\\begin{center}\\raisebox{1ex}[1ex]{Source listing for '
                    '\\begin{em}%s\\end{em}}\\end{center}' 
                    % latexEscape(os.path.basename(fileName)))

    def visitNode_a_href(self, node):
        supported_schemes=['http', 'https', 'ftp', 'mailto']
        self.visitNodeDefault(node)
        href = node.getAttribute('href')
        if urlparse.urlparse(href)[0] in supported_schemes:
            if node.childNodes[0].data != href:
                self.writer('\\footnote{%s}' % latexEscape(href))
        else:
            if href.startswith('#'):
                href = self.filename + href
            ref = href.replace('#', 'HASH')
            self.writer(' (page \\pageref{%s})' % ref)

    def visitNode_a_name(self, node):
        self.writer('\\label{%sHASH%s}' % (self.filename,
                                           node.getAttribute('name')))
        self.visitNodeDefault(node)

    def visitNode_table(self, node):
        rows = [[col for col in row.childNodes 
                     if getattr(col, 'tagName', None) in ('th', 'td')]
            for row in node.childNodes if getattr(row, 'tagName', None)=='tr']
        numCols = 1+max([len(row) for row in rows])
        self.writer('\\begin{table}[ht]\\begin{center}')
        self.writer('\\begin{tabular}{@{}'+'l'*numCols+'@{}}')
        for row in rows:
            th = 0
            for col in row:
                self.visitNode(col)
                self.writer('&')
                if col.tagName == 'th':
                    th = 1
            self.writer('\\\\\n') #\\ ends lines
            if th:
                self.writer('\\hline\n')
        self.writer('\\end{tabular}\n')
        if node.hasAttribute('title'):
            self.writer('\\caption{%s}' 
                        % latexEscape(node.getAttribute('title')))
        self.writer('\\end{center}\\end{table}\n')
         
    visitNode_h2 = visitNode_h3 = visitNode_h4 = visitNodeHeader

    start_title = '\\title{'
    end_title = '}\n'

    start_html = '\\documentclass{article}\n'
    start_body = '\\begin{document}\n\\maketitle\n'
    end_body = '\\end{document}'

    start_dl = '\\begin{description}\n'
    end_dl = '\\end{description}\n'
    start_ul = '\\begin{itemize}\n'
    end_ul = '\\end{itemize}\n'

    start_ol = '\\begin{enumerate}\n'
    end_ol = '\\end{enumerate}\n'

    start_li = '\\item '
    end_li = '\n'

    start_dt = '\\item['
    end_dt = ']'
    end_dd = '\n'

    start_p = '\n\n'

    start_strong = start_em = '\\begin{em}'
    end_strong = end_em = '\\end{em}'

    start_q = "``"
    end_q = "''"

    start_span_footnote = '\\footnote{'
    end_span_footnote = '}'

    start_div_note = '\\begin{quotation}\\textbf{Note:}'
    end_div_note = '\\end{quotation}'

    start_th = '\\textbf{'
    end_th = '}'


class SectionLatexSpitter(LatexSpitter):

    baseLevel = 1

    def visitNode_title(self, node):
        self.writer('\\section{')
        self.visitNodeDefault(node)
        self.writer('\\label{%s}}\n' % self.filename)

    start_title = end_title = end_body = start_body = start_html = None


class HeadingLatexSpitter(BaseLatexSpitter):
    start_q = "``"
    end_q = "''"

    writeNodeData = LatexSpitter.writeNodeData.im_func
    

def processFile(spitter, fin):
    dom = microdom.parse(fin).documentElement
    tree.expandAPI(dom)
    spitter.visitNode(dom)
