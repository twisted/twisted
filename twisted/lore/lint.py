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

from twisted.lore import tree
from twisted.web import domhelpers
from twisted.python import reflect

import parser

class TagChecker:

    def __init__(self, allowedTags, allowedClasses):
        self.allowedTags = allowedTags
        self.allowedClasses = allowedClasses

    def check(self, dom, filename):
        for method in reflect.prefixedMethods(self, 'check_'):
            method(dom, filename)

    def _reportError(self, filename, element, error):
        hlint = element.hasAttribute('hlint') and element.getAttribute('hlint')
        if hlint != 'off':
            pos = getattr(element, '_markpos', None) or (0, 0)
            print "%s:%s:%s: %s" % ((filename,)+pos+(error,))

    def check_disallowedElements(self, dom, filename):
        def m(node, self=self):
            return not self.allowedTags(node.tagName)
        for element in domhelpers.findElements(dom, m):
            self._reportError(filename, element,
                               'unrecommended tag %s' % element.tagName)

    def check_disallowedClasses(self, dom, filename):
        def matcher(element, self=self):
            if not element.hasAttribute('class'):
                return 0
            checker = self.allowedClasses.get(element.tagName, lambda x:0)
            return not checker(element.getAttribute('class'))
        for element in domhelpers.findElements(dom, matcher):
            self._reportError(filename, element,
                              'unknown class %s' %element.getAttribute('class'))

    def check_quote(self, dom, filename):
        def matcher(node):
            return ('"' in getattr(node, 'data', '') and
                    [1 for n in domhelpers.getParents(node)[1:-1]
                           if n.tagName in ('pre', 'code')] == [])
        for node in domhelpers.findNodes(dom, matcher):
            self._reportError(filename, node.parentNode, 'contains quote')

    def check_styleattr(self, dom, filename):
        for node in domhelpers.findElementsWithAttribute(dom, 'style'):
            self._reportError(filename, node, 'explicit style')

    def check_align(self, dom, filename):
        for node in domhelpers.findElementsWithAttribute(dom, 'align'):
            self._reportError(filename, node, 'explicit alignment')

    def check_style(self, dom, filename):
        for node in domhelpers.findNodesNamed(dom, 'style'):
            if domhelpers.getNodeText(node) != '':
                self._reportError(filename, node, 'hand hacked style')

    def check_title(self, dom, filename):
        doc = dom.documentElement
        title = domhelpers.findNodesNamed(dom, 'title')
        if len(title)!=1:
            return self._reportError(filename, doc, 'not exactly one title')
        h1 = domhelpers.findNodesNamed(dom, 'h1')
        if len(h1)!=1:
            return self._reportError(filename, doc, 'not exactly one h1')
        if domhelpers.getNodeText(h1[0]) != domhelpers.getNodeText(title[0]):
            self._reportError(filename, h1[0], 'title and h1 text differ')

    def check_pre(self, dom, filename):
        for node in domhelpers.findNodesNamed(dom, 'pre'):
            for line in domhelpers.getNodeText(node).split('\n'):
                if len(line) > 80:
                    self._reportError(filename, node, 
                                      'text wider than 80 columns in pre')

    def check_pre_py_listing(self, dom, filename):
        for node in domhelpers.findNodesNamed(dom, 'pre'):
            if node.getAttribute('class') == 'python':
                try:
                    text = domhelpers.getNodeText(node)
                    # Fix < and >
                    text = text.replace('&gt;', '>').replace('&lt;', '<')
                    # Strip blank lines
                    lines = filter(None,[l.rstrip() for l in text.split('\n')])
                    # Strip leading space
                    while not [1 for line in lines if line[:1] not in ('',' ')]:
                        lines = [line[1:] for line in lines]
                    text = '\n'.join(lines) + '\n'
                    try:
                        parser.suite(text)
                    except parser.ParserError, e:
                        # Pretend the "..." idiom is syntactically valid
                        text = text.replace("...","'...'")
                        parser.suite(text)
                except parser.ParserError, e:
                    self._reportError(filename, node, 
                                      'invalid python code:' + str(e))

    def check_anchor_in_heading(self, dom, filename):
        headingNames = ['h%d' % n for n in range(1,7)]
        for hname in headingNames:
            for node in domhelpers.findNodesNamed(dom, hname):
                if domhelpers.findNodesNamed(node, 'a'):
                    self._reportError(filename, node, 'anchor in heading')


def list2dict(l):
    d = {}
    for el in l:
        d[el] = None
    return d

classes = list2dict(['shell', 'API', 'python', 'py-prototype', 'py-filename',
                     'py-src-string', 'py-signature', 'py-src-parameter',
                     'py-src-identifier', 'py-src-keyword'])

tags = list2dict(["html", "title", "head", "body", "h1", "h2", "h3", "ol", "ul",
                  "dl", "li", "dt", "dd", "p", "code", "img", "blockquote", "a",
                  "cite", "div", "span", "strong", "em", "pre", "q", "table",
                  "tr", "td", "th", "style"])

span = list2dict(['footnote', 'manhole-output'])

div = list2dict(['note', 'boxed', 'doit'])

a = list2dict(['py-listing', 'html-listing'])

pre = list2dict(['python', 'shell', 'python-interpreter', 'elisp'])

allowed = {'code': classes.has_key, 'span': span.has_key, 'div': div.has_key,
           'a': a.has_key, 'pre': pre.has_key}

def getDefaultChecker():
    return TagChecker(tags.has_key, allowed)

def doFile(file, checker):
    dom = tree.parseFileAndReport(file)
    if dom:
        checker.check(dom, file)
