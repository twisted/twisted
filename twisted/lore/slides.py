"""Rudimentary slide support for Lore.

TODO:
    - Complete mgp output target 
        - syntax highlighting
        - saner font handling
        - probably lots more
    - Add HTML output targets
        - one slides per page (with navigation links)
        - all in one page
"""
from __future__ import nested_scopes

from twisted.lore import default
from twisted.web import domhelpers
# These should be factored out
from twisted.lore.latex import BaseLatexSpitter, processFile, getLatexText
from twisted.lore.tree import getHeaders

import os
from cStringIO import StringIO

entities = { 'amp': '&', 'gt': '>', 'lt': '<', 'quot': '"',
             'copy': '(c)'}

class MagicpointOutput(BaseLatexSpitter):
    def writeNodeData(self, node):
        buf = StringIO()
        getLatexText(node, buf.write, entities=entities)
        self.writer(buf.getvalue())

    def visitNode_title(self, node):
        self.title = domhelpers.getNodeText(node)

    def visitNode_body(self, node):
        self.fontStack = [('standard', None)]

        self.writer(self.start_h2)
        self.writer(self.title)
        self.writer(self.end_h2)
        # Adapted from tree.generateToC
        for element in getHeaders(node):
            level = int(element.tagName[1])-1
            self.writer(level * '\t')
            self.writer(domhelpers.getNodeText(element))
            self.writer('\n')
        self.visitNodeDefault(node)

    def visitNode_pre(self, node):
        # TODO: Syntax highlighting
        text = domhelpers.getNodeText(node)
        lines = text.split('\n')
        self.writer('%font "typewriter", size 4\n')
        self.fontStack.append(('typewriter', 4))
        for line in lines:
            self.writer(' ' + line + '\n')
        del self.fontStack[-1]
        self.writer('%' + self.fontName() + '\n')

    def visitNode_strong(self, node):
        self.doFont(node, 'bold')

    def visitNode_em(self, node):
        self.doFont(node, 'italic')

    def doFont(self, node, style):
        self.fontStack.append((style, None))
        self.writer('\n%cont, ' + self.fontName() + '\n')
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
                return 'font "%s" size %d' % (name, size)

        return 'font "%s"' % name

    start_h2 = "%page\n\n"
    end_h2 = '\n\n%font "typewriter", size 2\n\n%font "standard"\n'

    start_li = "\t"
    end_li = "\n"
    

def convertFile(filename, outputter, template, ext=".mgp"):
    fout = open(os.path.splitext(filename)[0]+ext, 'w')
    fout.write(open(template).read())
    spitter = outputter(fout.write, os.path.dirname(filename), filename)
    fin = open(filename)
    processFile(spitter, fin)
    fin.close()
    fout.close()


class SlidesProcessingFunctionFactory(default.ProcessingFunctionFactory):
    def generate_mgp(self, d):
        template = d.get('template', 'template.mgp')
        df = lambda file, linkrel: convertFile(file, MagicpointOutput, template, ext=".mgp")
        return df

factory=SlidesProcessingFunctionFactory()

