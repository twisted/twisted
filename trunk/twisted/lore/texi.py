# -*- test-case-name: twisted.lore.test.test_texi -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from cStringIO import StringIO
import os, re

from twisted.web import domhelpers
import latex, tree

spaceRe = re.compile('\s+')

def texiEscape(text):
    return spaceRe.sub(text, ' ')

entities = latex.entities.copy()
entities['copy'] = '@copyright{}'

class TexiSpitter(latex.BaseLatexSpitter):

    baseLevel = 1

    def writeNodeData(self, node):
        latex.getLatexText(node, self.writer, texiEscape, entities)

    def visitNode_title(self, node):
        self.writer('@node ')
        self.visitNodeDefault(node)
        self.writer('\n')
        self.writer('@section ')
        self.visitNodeDefault(node)
        self.writer('\n')
        headers = tree.getHeaders(domhelpers.getParents(node)[-1])
        if not headers:
            return
        self.writer('@menu\n')
        for header in headers:
            self.writer('* %s::\n' % domhelpers.getNodeText(header))
        self.writer('@end menu\n')


    def visitNode_pre(self, node):
        """
        Writes a I{verbatim} block when it encounters a I{pre} element.

        @param node: The element to process.
        @type node: L{xml.dom.minidom.Element}
        """
        self.writer('@verbatim\n')
        buf = StringIO()
        latex.getLatexText(node, buf.write, entities=entities)
        self.writer(tree._removeLeadingTrailingBlankLines(buf.getvalue()))
        self.writer('@end verbatim\n')


    def visitNode_code(self, node):
        fout = StringIO()
        latex.getLatexText(node, fout.write, texiEscape, entities)
        self.writer('@code{'+fout.getvalue()+'}')

    def visitNodeHeader(self, node):
        self.writer('\n\n@node ')
        self.visitNodeDefault(node)
        self.writer('\n')
        level = (int(node.tagName[1])-2)+self.baseLevel
        self.writer('\n\n@'+level*'sub'+'section ')
        self.visitNodeDefault(node)
        self.writer('\n')

    def visitNode_a_listing(self, node):
        fileName = os.path.join(self.currDir, node.getAttribute('href'))
        self.writer('@verbatim\n')
        self.writer(open(fileName).read())
        self.writer('@end verbatim')
        # Write a caption for this source listing

    def visitNode_a_href(self, node):
        self.visitNodeDefault(node)

    def visitNode_a_name(self, node):
        self.visitNodeDefault(node)

    visitNode_h2 = visitNode_h3 = visitNode_h4 = visitNodeHeader

    start_dl = '@itemize\n'
    end_dl = '@end itemize\n'
    start_ul = '@itemize\n'
    end_ul = '@end itemize\n'

    start_ol = '@enumerate\n'
    end_ol = '@end enumerate\n'

    start_li = '@item\n'
    end_li = '\n'

    start_dt = '@item\n'
    end_dt = ': '
    end_dd = '\n'

    start_p = '\n\n'

    start_strong = start_em = '@emph{'
    end_strong = end_em = '}'

    start_q = "``"
    end_q = "''"

    start_span_footnote = '@footnote{'
    end_span_footnote = '}'

    start_div_note = '@quotation\n@strong{Note:}'
    end_div_note = '@end quotation\n'

    start_th = '@strong{'
    end_th = '}'
