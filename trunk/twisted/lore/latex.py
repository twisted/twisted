# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
LaTeX output support for Lore.
"""

from xml.dom import minidom as dom
import os.path, re
from cStringIO import StringIO
import urlparse

from twisted.web import domhelpers
from twisted.python import text, procutils

import tree

escapingRE = re.compile(r'([\[\]#$%&_{}^~\\])')
lowerUpperRE = re.compile(r'([a-z])([A-Z])')

def _escapeMatch(match):
    c = match.group()
    if c == '\\':
        return '$\\backslash$'
    elif c == '~':
        return '\\~{}'
    elif c == '^':
        return '\\^{}'
    elif c in '[]':
        return '{'+c+'}'
    else:
        return '\\' + c

def latexEscape(txt):
    txt = escapingRE.sub(_escapeMatch, txt)
    return txt.replace('\n', ' ')

entities = {'amp': '\&', 'gt': '>', 'lt': '<', 'quot': '"',
            'copy': '\\copyright', 'mdash': '---', 'rdquo': '``', 
            'ldquo': "''"}


def realpath(path):
    # Normalise path
    cwd = os.getcwd()
    path = os.path.normpath(os.path.join(cwd, path))
    return path.replace('\\', '/') # windows slashes make LaTeX blow up


def getLatexText(node, writer, filter=lambda x:x, entities=entities):
    if hasattr(node, 'eref'):
        return writer(entities.get(node.eref, ''))
    if hasattr(node, 'data'):
        if isinstance(node.data, unicode):
            data = node.data.encode('utf-8')
        else:
            data = node.data
        return writer(filter(data))
    for child in node.childNodes:
        getLatexText(child, writer, filter, entities)

class BaseLatexSpitter:

    def __init__(self, writer, currDir='.', filename=''):
        self.writer = writer
        self.currDir = currDir
        self.filename = filename

    def visitNode(self, node):
        if isinstance(node, dom.Comment):
            return
        if not hasattr(node, 'tagName'):
            self.writeNodeData(node)
            return
        getattr(self, 'visitNode_'+node.tagName, self.visitNodeDefault)(node)

    def visitNodeDefault(self, node):
        self.writer(getattr(self, 'start_'+node.tagName, ''))
        for child in node.childNodes:
            self.visitNode(child)
        self.writer(getattr(self, 'end_'+node.tagName, ''))

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
    diaHack = bool(procutils.which("dia"))

    def writeNodeData(self, node):
        buf = StringIO()
        getLatexText(node, buf.write, latexEscape)
        self.writer(buf.getvalue().replace('<', '$<$').replace('>', '$>$'))

    def visitNode_head(self, node):
        authorNodes = domhelpers.findElementsWithAttribute(node, 'rel', 'author')
        authorNodes = [n for n in authorNodes if n.tagName == 'link']

        if authorNodes:
            self.writer('\\author{')
            authors = []
            for aNode in authorNodes:
                name = aNode.getAttribute('title')
                href = aNode.getAttribute('href')
                if href.startswith('mailto:'):
                    href = href[7:]
                if href:
                    if name:
                        name += ' '
                    name += '$<$' + href + '$>$'
                if name:
                    authors.append(name)
            
            self.writer(' \\and '.join(authors))
            self.writer('}')

        self.visitNodeDefault(node)

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
        if self.diaHack and os.access(target + '.dia', os.R_OK):
            ext = '.dia'
            fileName = target + ext
        f = getattr(self, 'convert_'+ext[1:], None)
        if not f:
            return
        target = os.path.join(self.currDir, os.path.basename(target)+'.eps')
        f(fileName, target)
        target = os.path.basename(target)
        self._write_img(target)

    def _write_img(self, target):
        """Write LaTeX for image."""
        self.writer('\\begin{center}\\includegraphics[%%\n'
                    'width=1.0\n'
                    '\\textwidth,height=1.0\\textheight,\nkeepaspectratio]'
                    '{%s}\\end{center}\n' % target)
    
    def convert_png(self, src, target):
        # XXX there's a *reason* Python comes with the pipes module -
        # someone fix this to use it.
        r = os.system('pngtopnm "%s" | pnmtops -noturn > "%s"' % (src, target))
        if r != 0:
            raise OSError(r)

    def convert_dia(self, src, target):
        # EVIL DISGUSTING HACK
        data = os.popen("gunzip -dc %s" % (src)).read()
        pre = '<dia:attribute name="scaling">\n          <dia:real val="1"/>'
        post = '<dia:attribute name="scaling">\n          <dia:real val="0.5"/>'
        f = open('%s_hacked.dia' % (src), 'wb')
        f.write(data.replace(pre, post))
        f.close()
        os.system('gzip %s_hacked.dia' % (src,))
        os.system('mv %s_hacked.dia.gz %s_hacked.dia' % (src,src))
        # Let's pretend we never saw that.

        # Silly dia needs an X server, even though it doesn't display anything.
        # If this is a problem for you, try using Xvfb.
        os.system("dia %s_hacked.dia -n -e %s" % (src, target))

    def visitNodeHeader(self, node):
        level = (int(node.tagName[1])-2)+self.baseLevel
        self.writer('\n\n\\'+level*'sub'+'section{')
        spitter = HeadingLatexSpitter(self.writer, self.currDir, self.filename)
        spitter.visitNodeDefault(node)
        self.writer('}\n')

    def visitNode_a_listing(self, node):
        fileName = os.path.join(self.currDir, node.getAttribute('href'))
        self.writer('\\begin{verbatim}\n')
        lines = map(str.rstrip, open(fileName).readlines())
        skipLines = int(node.getAttribute('skipLines') or 0)
        lines = lines[skipLines:]
        self.writer(text.removeLeadingTrailingBlanks('\n'.join(lines)))
        self.writer('\\end{verbatim}')

        # Write a caption for this source listing
        fileName = os.path.basename(fileName)
        caption = domhelpers.getNodeText(node)
        if caption == fileName:
            caption = 'Source listing'
        self.writer('\parbox[b]{\linewidth}{\\begin{center}%s --- '
                    '\\begin{em}%s\\end{em}\\end{center}}'
                    % (latexEscape(caption), latexEscape(fileName)))

    def visitNode_a_href(self, node):
        supported_schemes=['http', 'https', 'ftp', 'mailto']
        href = node.getAttribute('href')
        if urlparse.urlparse(href)[0] in supported_schemes:
            text = domhelpers.getNodeText(node)
            self.visitNodeDefault(node)
            if text != href:
                self.writer('\\footnote{%s}' % latexEscape(href))
        else:
            path, fragid = (href.split('#', 1) + [None])[:2]
            if path == '':
                path = self.filename
            else:
                path = os.path.join(os.path.dirname(self.filename), path)
            #if path == '':
                #path = os.path.basename(self.filename)
            #else:
            #    # Hack for linking to man pages from howtos, i.e.
            #    # ../doc/foo-man.html -> foo-man.html
            #    path = os.path.basename(path)

            path = realpath(path)

            if fragid:
                ref = path + 'HASH' + fragid
            else:
                ref = path
            self.writer('\\textit{')
            self.visitNodeDefault(node)
            self.writer('}')
            self.writer('\\loreref{%s}' % ref)

    def visitNode_a_name(self, node):
        self.writer('\\label{%sHASH%s}' % (
                realpath(self.filename), node.getAttribute('name')))
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

    def visitNode_span_footnote(self, node):
        self.writer('\\footnote{')
        spitter = FootnoteLatexSpitter(self.writer, self.currDir, self.filename)
        spitter.visitNodeDefault(node)
        self.writer('}')

    def visitNode_span_index(self, node):
        self.writer('\\index{%s}\n' % node.getAttribute('value'))
        self.visitNodeDefault(node)

    visitNode_h2 = visitNode_h3 = visitNode_h4 = visitNodeHeader

    start_title = '\\title{'
    end_title = '}\n'

    start_sub = '$_{'
    end_sub = '}$'

    start_sup = '$^{'
    end_sup = '}$'

    start_html = '''\\documentclass{article}
    \\newcommand{\\loreref}[1]{%
    \\ifthenelse{\\value{page}=\\pageref{#1}}%
               { (this page)}%
               { (page \\pageref{#1})}%
    }'''

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

    start_div_note = '\\begin{quotation}\\textbf{Note:}'
    end_div_note = '\\end{quotation}'

    start_th = '\\textbf{'
    end_th = '}'


class SectionLatexSpitter(LatexSpitter):

    baseLevel = 1

    start_title = '\\section{'

    def visitNode_title(self, node):
        self.visitNodeDefault(node)
        #self.writer('\\label{%s}}\n' % os.path.basename(self.filename))
        self.writer('\\label{%s}}\n' % realpath(self.filename))

    end_title = end_body = start_body = start_html = ''


class ChapterLatexSpitter(SectionLatexSpitter):
    baseLevel = 0
    start_title = '\\chapter{'


class HeadingLatexSpitter(BaseLatexSpitter):
    start_q = "``"
    end_q = "''"

    writeNodeData = LatexSpitter.writeNodeData.im_func


class FootnoteLatexSpitter(LatexSpitter):
    """For multi-paragraph footnotes, this avoids having an empty leading
    paragraph."""

    start_p = ''

    def visitNode_span_footnote(self, node):
        self.visitNodeDefault(node)

    def visitNode_p(self, node):
        self.visitNodeDefault(node)
        self.start_p = LatexSpitter.start_p

class BookLatexSpitter(LatexSpitter):
    def visitNode_body(self, node):
        tocs=domhelpers.locateNodes([node], 'class', 'toc')
        domhelpers.clearNode(node)
        if len(tocs):
            toc=tocs[0]
            node.appendChild(toc)
        self.visitNodeDefault(node)

    def visitNode_link(self, node):
        if not node.hasAttribute('rel'):
            return self.visitNodeDefault(node)
        node.tagName += '_'+node.getAttribute('rel')
        self.visitNode(node)

    def visitNode_link_author(self, node):
        self.writer('\\author{%s}\n' % node.getAttribute('text'))

    def visitNode_link_stylesheet(self, node):
        if node.hasAttribute('type') and node.hasAttribute('href'):
            if node.getAttribute('type')=='application/x-latex':
                packagename=node.getAttribute('href')
                packagebase,ext=os.path.splitext(packagename)
                self.writer('\\usepackage{%s}\n' % packagebase)

    start_html = r'''\documentclass[oneside]{book}
\usepackage{graphicx}
\usepackage{times,mathptmx}
'''

    start_body = r'''\begin{document}
\maketitle
\tableofcontents
'''

    start_li=''
    end_li=''
    start_ul=''
    end_ul=''


    def visitNode_a(self, node):
        if node.hasAttribute('class'):
            a_class=node.getAttribute('class')
            if a_class.endswith('listing'):
                return self.visitNode_a_listing(node)
            else:
                return getattr(self, 'visitNode_a_%s' % a_class)(node)
        if node.hasAttribute('href'):
            return self.visitNode_a_href(node)
        if node.hasAttribute('name'):
            return self.visitNode_a_name(node)
        self.visitNodeDefault(node)

    def visitNode_a_chapter(self, node):
        self.writer('\\chapter{')
        self.visitNodeDefault(node)
        self.writer('}\n')

    def visitNode_a_sect(self, node):
        base,ext=os.path.splitext(node.getAttribute('href'))
        self.writer('\\input{%s}\n' % base)



def processFile(spitter, fin):
    # XXX Use Inversion Of Control Pattern to orthogonalize the parsing API
    # from the Visitor Pattern application. (EnterPrise)
    dom = tree.parseFileAndReport(fin.name, lambda x: fin).documentElement
    spitter.visitNode(dom)


def convertFile(filename, spitterClass):
    fout = open(os.path.splitext(filename)[0]+".tex", 'w')
    spitter = spitterClass(fout.write, os.path.dirname(filename), filename)
    fin = open(filename)
    processFile(spitter, fin)
    fin.close()
    fout.close()
