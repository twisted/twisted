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

from twisted.protocols.sux import XMLParser
import os, re

escapingRE = re.compile(r'([#$%&_{}^~])')
lowerUpperRE = re.compile(r'([a-z])([A-Z])')

def latexEscape(text):
    return escapingRE.sub(r'\\\1{}', text.replace('\\', '$\\backslash$'))

class LatexSpitter(XMLParser):

    entities = { 'amp': '&', 'gt': '>', 'lt': '<', 'quot': '"',
                 'copy': '\\copyright'}

    ignoring = 0
    normalizing = 1
    escaping = 1
    baseLevel = 0
    raw = 0
    hyphenateCode = 0

    def __init__(self, writer, currDir='.'):
        self.writer = writer
        self.currDir = currDir
        self.spans = []
        self.divs = []

    def gotTagStart(self, name, attributes):
        s = getattr(self, "mapStart_"+name, None)
        if s and not self.raw:
            self.writer(s)
        m = getattr(self, "start_"+name, None)
        m and m(name, attributes)

    def gotText(self, data):
        if self.ignoring:
            return
        if self.normalizing:
            data = data.replace('\n', ' ')
        if self.escaping:
            data = latexEscape(data)
        if self.hyphenateCode:
            olddata = data
            data = lowerUpperRE.sub(r'\1\\textrm{\\-}\2', data)
            if data == olddata:
                # No hyphenation points were added, so fall back to adding
                # hyphenation points at dots (except not for leading dots)
                data = data[:1] + data[1:].replace('.', '.\\textrm{\\-}')

        self.writer(data)

    def gotEntityReference(self, entityRef):
        self.writer(self.entities.get(entityRef, ''))

    def gotTagEnd(self, name):
        s = getattr(self, "mapEnd_"+name, None)
        if s and not self.raw:
            self.writer(s)
        m = getattr(self, "end_"+name, None)
        m and m(name)

    def start_img(self, _, attributes):
        fileName = os.path.join(self.currDir, attributes['src'])
        target, ext = os.path.splitext(fileName)
        ext = ext[1:]
        m = getattr(self, 'convert_'+ext, None)
        if not m:
            return
        target = os.path.join(self.currDir, os.path.basename(target)+'.eps')
        m(fileName, target)
        target = os.path.basename(target)
        self.writer('\\includegraphics{%s}\n' % target)

    def convert_png(self, src, target):
        os.system("pngtopnm %s | pnmtops > %s" % (src, target))

    def _headerStart(self, h, attributes):
        level = int(h[1])-2
        level += self.baseLevel
        self.writer('\n\n\\'+level*'sub'+'section{')

    def start_h1(self, _, _1):
        self.ignoring = 1

    def end_h1(self, _):
        self.ignoring = 0

    def start_pre(self, _, _1):
        self.normalizing = self.escaping = 0
        self.raw = 1

    def end_pre(self, _):
        self.normalizing = self.escaping = 1
        self.raw = 0
        self.writer(self.mapEnd_pre)

    def start_code(self, _, _1):
        self.hyphenateCode = 1

    def end_code(self, _):
        self.hyphenateCode = 0

    def start_a(self, _, attrs):
        if attrs.get('class') == "py-listing":
            fileName = os.path.join(self.currDir, attrs['href'])
            self.writer('\\begin{verbatim}')
            self.writer(open(fileName).read())
            self.writer('\\end{verbatim}')
            # Write a caption for this source listing
            self.writer('\\begin{center}\\raisebox{1ex}[1ex]{Source listing for '
                        '\\begin{em}%s\\end{em}}\\end{center}' 
                        % latexEscape(fileName))
            self.ignoring = 1
        elif attrs.has_key('href'):
            if attrs.get('class', '').find('listing') != -1:
                # Source listings aren't cross-references.
                return
            href = attrs['href']
            if href.startswith('#'):
                self.ref = self.filename + 'HASH' + href[1:]
            elif href.find('#') != 1 and not href.startswith('http:'):
                self.ref = href.replace('#', 'HASH')
            elif not href.startswith('http:'):
                self.ref = href
        elif attrs.has_key('name'):
            self.writer('\\label{%sHASH%s}' % (self.filename, attrs['name']))

    def end_a(self, _):
        self.ignoring = 0
        if hasattr(self, 'ref'):
            self.writer(' (page \\pageref{%s})' % self.ref)
            del self.ref

    def start_style(self, _, _1):
        self.ignoring = 1

    def end_style(self, _):
        self.ignoring = 0

    def start_span(self, _, attributes):
        class_ = attributes.get('class')
        self.spans.append(class_)
        if class_:
            self.gotTagStart('span_'+class_, attributes)

    def end_span(self, _):
        class_ = self.spans.pop()
        if class_:
            self.gotTagEnd('span_'+class_)

    def start_div(self, _, attributes):
        class_ = attributes.get('class')
        self.divs.append(class_)
        if class_:
            self.gotTagStart('div_'+class_, attributes)

    def end_div(self, _):
        class_ = self.divs.pop()
        if class_:
            self.gotTagEnd('div_'+class_)

    start_h2 = start_h3 = start_h4 = _headerStart

    mapStart_title = '\\title{'
    mapEnd_title = mapEnd_h2 = mapEnd_h3 = mapEnd_h4 = '}\n'

    mapStart_html = '\\documentclass{article}\n'
    mapStart_body = '\\begin{document}\n\\maketitle\n'
    mapEnd_body = '\\end{document}'

    mapStart_dl = mapStart_ul = '\\begin{itemize}\n'
    mapEnd_dl = mapEnd_ul = '\\end{itemize}\n'

    mapStart_ol = '\\begin{enumerate}\n'
    mapEnd_ol = '\\end{enumerate}\n'

    mapStart_li = '\\item '
    mapEnd_li = '\n'

    mapStart_dt = '\\item{'
    mapEnd_dt = '}'
    mapEnd_dd = '\n'

    mapStart_p = '\n\n'

    mapStart_code = '\\texttt{'
    mapEnd_code = '}'

    mapStart_pre = '\\begin{verbatim}'
    mapEnd_pre = '\\end{verbatim}'

    mapStart_strong = mapStart_em = '\\begin{em}'
    mapEnd_strong = mapEnd_em = '\\end{em}'

    mapStart_q = "``"
    mapEnd_q = "''"

    mapStart_span_footnote = '\\footnote{'
    mapEnd_span_footnote = '}'

    mapStart_div_note = '\\begin{quotation}\\textbf{Note:}'
    mapEnd_div_note = '\\end{quotation}'


class SectionLatexSpitter(LatexSpitter):

    baseLevel = 1
    mapStart_title = '\\section{'
    def end_title(self, _):
        self.writer('\\label{%s}\n' % self.filename)
    mapEnd_body = mapStart_body = mapStart_html = None
