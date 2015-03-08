# -*- test-case-name: twisted.lore.test.test_slides -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Rudimentary slide support for Lore.

TODO:
    - Complete mgp output target
        - syntax highlighting
        - saner font handling
        - probably lots more
    - Add HTML output targets
        - one slides per page (with navigation links)
        - all in one page

Example input file::
    <html>

    <head><title>Title of talk</title></head>

    <body>
    <h1>Title of talk</h1>

    <h2>First Slide</h2>

    <ul>
      <li>Bullet point</li>
      <li>Look ma, I'm <strong>bold</strong>!</li>
      <li>... etc ...</li>
    </ul>


    <h2>Second Slide</h2>

    <pre class="python">
    # Sample code sample.
    print "Hello, World!"
    </pre>

    </body>

    </html>
"""

from xml.dom import minidom as dom
import os.path, re
from cStringIO import StringIO

from twisted.lore import default
from twisted.web import domhelpers
# These should be factored out
from twisted.lore.latex import BaseLatexSpitter, LatexSpitter, processFile
from twisted.lore.latex import getLatexText, HeadingLatexSpitter
from twisted.lore.tree import getHeaders, _removeLeadingTrailingBlankLines
from twisted.lore.tree import removeH1, fixAPI, fontifyPython
from twisted.lore.tree import addPyListings, addHTMLListings, setTitle


hacked_entities = { 'amp': ' &', 'gt': ' >', 'lt': ' <', 'quot': ' "',
                    'copy': ' (c)'}

entities = { 'amp': '&', 'gt': '>', 'lt': '<', 'quot': '"',
             'copy': '(c)'}



class MagicpointOutput(BaseLatexSpitter):
    bulletDepth = 0

    def writeNodeData(self, node):
        buf = StringIO()
        getLatexText(node, buf.write, entities=hacked_entities)
        data = buf.getvalue().rstrip().replace('\n', ' ')
        self.writer(re.sub(' +', ' ', data))

    def visitNode_title(self, node):
        self.title = domhelpers.getNodeText(node)

    def visitNode_body(self, node):
        # Adapted from tree.generateToC
        self.fontStack = [('standard', None)]

        # Title slide
        self.writer(self.start_h2)
        self.writer(self.title)
        self.writer(self.end_h2)

        self.writer('%center\n\n\n\n\n')
        for authorNode in domhelpers.findElementsWithAttribute(node, 'class', 'author'):
            getLatexText(authorNode, self.writer, entities=entities)
            self.writer('\n')

        # Table of contents
        self.writer(self.start_h2)
        self.writer(self.title)
        self.writer(self.end_h2)

        for element in getHeaders(node):
            level = int(element.tagName[1])-1
            self.writer(level * '\t')
            self.writer(domhelpers.getNodeText(element))
            self.writer('\n')

        self.visitNodeDefault(node)

    def visitNode_div_author(self, node):
        # Skip this node; it's already been used by visitNode_body
        pass

    def visitNode_div_pause(self, node):
        self.writer('%pause\n')


    def visitNode_pre(self, node):
        """
        Writes Latex block using the 'typewriter' font when it encounters a
        I{pre} element.

        @param node: The element to process.
        @type node: L{xml.dom.minidom.Element}
        """
        # TODO: Syntax highlighting
        buf = StringIO()
        getLatexText(node, buf.write, entities=entities)
        data = buf.getvalue()
        data = _removeLeadingTrailingBlankLines(data)
        lines = data.split('\n')
        self.fontStack.append(('typewriter', 4))
        self.writer('%' + self.fontName() + '\n')
        for line in lines:
            self.writer(' ' + line + '\n')
        del self.fontStack[-1]
        self.writer('%' + self.fontName() + '\n')


    def visitNode_ul(self, node):
        if self.bulletDepth > 0:
            self.writer(self._start_ul)
        self.bulletDepth += 1
        self.start_li = self._start_li * self.bulletDepth
        self.visitNodeDefault(node)
        self.bulletDepth -= 1
        self.start_li = self._start_li * self.bulletDepth

    def visitNode_strong(self, node):
        self.doFont(node, 'bold')

    def visitNode_em(self, node):
        self.doFont(node, 'italic')

    def visitNode_code(self, node):
        self.doFont(node, 'typewriter')

    def doFont(self, node, style):
        self.fontStack.append((style, None))
        self.writer(' \n%cont, ' + self.fontName() + '\n')
        self.visitNodeDefault(node)
        del self.fontStack[-1]
        self.writer('\n%cont, ' + self.fontName() + '\n')

    def fontName(self):
        names = [x[0] for x in self.fontStack]
        if 'typewriter' in names:
            name = 'typewriter'
        else:
            name = ''

        if 'bold' in names:
            name += 'bold'
        if 'italic' in names:
            name += 'italic'

        if name == '':
            name = 'standard'

        sizes = [x[1] for x in self.fontStack]
        sizes.reverse()
        for size in sizes:
            if size:
                return 'font "%s", size %d' % (name, size)

        return 'font "%s"' % name

    start_h2 = "%page\n\n"
    end_h2 = '\n\n\n'

    _start_ul = '\n'

    _start_li = "\t"
    end_li = "\n"


def convertFile(filename, outputter, template, ext=".mgp"):
    fout = open(os.path.splitext(filename)[0]+ext, 'w')
    fout.write(open(template).read())
    spitter = outputter(fout.write, os.path.dirname(filename), filename)
    fin = open(filename)
    processFile(spitter, fin)
    fin.close()
    fout.close()


# HTML DOM tree stuff

def splitIntoSlides(document):
    body = domhelpers.findNodesNamed(document, 'body')[0]
    slides = []
    slide = []
    title = '(unset)'
    for child in body.childNodes:
        if isinstance(child, dom.Element) and child.tagName == 'h2':
            if slide:
                slides.append((title, slide))
                slide = []
            title = domhelpers.getNodeText(child)
        else:
            slide.append(child)
    slides.append((title, slide))
    return slides

def insertPrevNextLinks(slides, filename, ext):
    for slide in slides:
        for name, offset in (("previous", -1), ("next", +1)):
            if (slide.pos > 0 and name == "previous") or \
               (slide.pos < len(slides)-1 and name == "next"):
                for node in domhelpers.findElementsWithAttribute(slide.dom, "class", name):
                    if node.tagName == 'a':
                        node.setAttribute('href', '%s-%d%s'
                                          % (filename[0], slide.pos+offset, ext))
                    else:
                        text = dom.Text()
                        text.data = slides[slide.pos+offset].title
                        node.appendChild(text)
            else:
                for node in domhelpers.findElementsWithAttribute(slide.dom, "class", name):
                    pos = 0
                    for child in node.parentNode.childNodes:
                        if child is node:
                            del node.parentNode.childNodes[pos]
                            break
                        pos += 1


class HTMLSlide:
    def __init__(self, dom, title, pos):
        self.dom = dom
        self.title = title
        self.pos = pos


def munge(document, template, linkrel, d, fullpath, ext, url, config):
    # FIXME: This has *way* to much duplicated crap in common with tree.munge
    #fixRelativeLinks(template, linkrel)
    removeH1(document)
    fixAPI(document, url)
    fontifyPython(document)
    addPyListings(document, d)
    addHTMLListings(document, d)
    #fixLinks(document, ext)
    #putInToC(template, generateToC(document))
    template = template.cloneNode(1)

    # Insert the slides into the template
    slides = []
    pos = 0
    for title, slide in splitIntoSlides(document):
        t = template.cloneNode(1)
        text = dom.Text()
        text.data = title
        setTitle(t, [text])
        tmplbody = domhelpers.findElementsWithAttribute(t, "class", "body")[0]
        tmplbody.childNodes = slide
        tmplbody.setAttribute("class", "content")
        # FIXME: Next/Prev links
        # FIXME: Perhaps there should be a "Template" class?  (setTitle/setBody
        #        could be methods...)
        slides.append(HTMLSlide(t, title, pos))
        pos += 1

    insertPrevNextLinks(slides, os.path.splitext(os.path.basename(fullpath)), ext)

    return slides

from tree import makeSureDirectoryExists

def getOutputFileName(originalFileName, outputExtension, index):
    return os.path.splitext(originalFileName)[0]+'-'+str(index) + outputExtension

def doFile(filename, linkrel, ext, url, templ, options={}, outfileGenerator=getOutputFileName):    
    from tree import parseFileAndReport
    doc = parseFileAndReport(filename)
    slides = munge(doc, templ, linkrel, os.path.dirname(filename), filename, ext, url, options)
    for slide, index in zip(slides, range(len(slides))):
        newFilename = outfileGenerator(filename, ext, index)
        makeSureDirectoryExists(newFilename)
        f = open(newFilename, 'wb')
        slide.dom.writexml(f)
        f.close()

# Prosper output

class ProsperSlides(LatexSpitter):
    firstSlide = 1
    start_html = '\\documentclass[ps]{prosper}\n'
    start_body = '\\begin{document}\n'
    start_div_author = '\\author{'
    end_div_author = '}'

    def visitNode_h2(self, node):
        if self.firstSlide:
            self.firstSlide = 0
            self.end_body = '\\end{slide}\n\n' + self.end_body
        else:
            self.writer('\\end{slide}\n\n')
        self.writer('\\begin{slide}{')
        spitter = HeadingLatexSpitter(self.writer, self.currDir, self.filename)
        spitter.visitNodeDefault(node)
        self.writer('}')

    def _write_img(self, target):
        self.writer('\\begin{center}\\includegraphics[%%\nwidth=1.0\n\\textwidth,'
                    'height=1.0\\textheight,\nkeepaspectratio]{%s}\\end{center}\n' % target)


class PagebreakLatex(LatexSpitter):

    everyN = 1
    currentN = 0
    seenH2 = 0

    start_html = LatexSpitter.start_html+"\\date{}\n"
    start_body = '\\begin{document}\n\n'

    def visitNode_h2(self, node):
        if not self.seenH2:
            self.currentN = 0
            self.seenH2 = 1
        else:
            self.currentN += 1
            self.currentN %= self.everyN
            if not self.currentN:
                self.writer('\\clearpage\n')
        level = (int(node.tagName[1])-2)+self.baseLevel
        self.writer('\n\n\\'+level*'sub'+'section*{')
        spitter = HeadingLatexSpitter(self.writer, self.currDir, self.filename)
        spitter.visitNodeDefault(node)
        self.writer('}\n')

class TwoPagebreakLatex(PagebreakLatex):

    everyN = 2


class SlidesProcessingFunctionFactory(default.ProcessingFunctionFactory):

    latexSpitters = default.ProcessingFunctionFactory.latexSpitters.copy()
    latexSpitters['prosper'] = ProsperSlides
    latexSpitters['page'] = PagebreakLatex
    latexSpitters['twopage'] = TwoPagebreakLatex

    def getDoFile(self):
        return doFile

    def generate_mgp(self, d, fileNameGenerator=None):
        template = d.get('template', 'template.mgp')
        df = lambda file, linkrel: convertFile(file, MagicpointOutput, template, ext=".mgp")
        return df

factory=SlidesProcessingFunctionFactory()
