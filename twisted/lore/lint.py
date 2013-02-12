# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Checker for common errors in Lore documents.
"""

from xml.dom import minidom as dom
import parser, urlparse, os.path

from twisted.lore import tree, process
from twisted.web import domhelpers
from twisted.python import reflect


# parser.suite in Python 2.3 raises SyntaxError, <2.3 raises parser.ParserError
parserErrors = (SyntaxError, parser.ParserError)

class TagChecker:

    def check(self, dom, filename):
        self.hadErrors = 0
        for method in reflect.prefixedMethods(self, 'check_'):
            method(dom, filename)
        if self.hadErrors:
            raise process.ProcessingFailure("invalid format")

    def _reportError(self, filename, element, error):
        hlint = element.hasAttribute('hlint') and element.getAttribute('hlint')
        if hlint != 'off':
            self.hadErrors = 1
            pos = getattr(element, '_markpos', None) or (0, 0)
            print "%s:%s:%s: %s" % ((filename,)+pos+(error,))


class DefaultTagChecker(TagChecker):

    def __init__(self, allowedTags, allowedClasses):
        self.allowedTags = allowedTags
        self.allowedClasses = allowedClasses

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

    def check_quote(self, doc, filename):
        def matcher(node):
            return ('"' in getattr(node, 'data', '') and
                    not isinstance(node, dom.Comment) and
                    not  [1 for n in domhelpers.getParents(node)[1:-1]
                           if n.tagName in ('pre', 'code')])
        for node in domhelpers.findNodes(doc, matcher):
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

    def check_80_columns(self, dom, filename):
        for node in domhelpers.findNodesNamed(dom, 'pre'):
            # the ps/pdf output is in a font that cuts off at 80 characters,
            # so this is enforced to make sure the interesting parts (which
            # are likely to be on the right-hand edge) stay on the printed
            # page.
            for line in domhelpers.gatherTextNodes(node, 1).split('\n'):
                if len(line.rstrip()) > 80:
                    self._reportError(filename, node,
                                      'text wider than 80 columns in pre')
        for node in domhelpers.findNodesNamed(dom, 'a'):
            if node.getAttribute('class').endswith('listing'):
                try:
                    fn = os.path.dirname(filename)
                    fn = os.path.join(fn, node.getAttribute('href'))
                    lines = open(fn,'r').readlines()
                except:
                    self._reportError(filename, node,
                                      'bad listing href: %r' %
                                      node.getAttribute('href'))
                    continue

                for line in lines:
                    if len(line.rstrip()) > 80:
                        self._reportError(filename, node,
                                          'listing wider than 80 columns')

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
                    except parserErrors, e:
                        # Pretend the "..." idiom is syntactically valid
                        text = text.replace("...","'...'")
                        parser.suite(text)
                except parserErrors, e:
                    self._reportError(filename, node,
                                      'invalid python code:' + str(e))

    def check_anchor_in_heading(self, dom, filename):
        headingNames = ['h%d' % n for n in range(1,7)]
        for hname in headingNames:
            for node in domhelpers.findNodesNamed(dom, hname):
                if domhelpers.findNodesNamed(node, 'a'):
                    self._reportError(filename, node, 'anchor in heading')

    def check_texturl_matches_href(self, dom, filename):
        for node in domhelpers.findNodesNamed(dom, 'a'):
            if not node.hasAttribute('href'):
                continue
            text = domhelpers.getNodeText(node)
            proto = urlparse.urlparse(text)[0]
            if proto and ' ' not in text:
                if text != node.getAttribute('href'):
                    self._reportError(filename, node,
                                      'link text does not match href')

    def check_lists(self, dom, filename):
        for node in (domhelpers.findNodesNamed(dom, 'ul')+
                     domhelpers.findNodesNamed(dom, 'ol')):
            if not node.childNodes:
                self._reportError(filename, node, 'empty list')
            for child in node.childNodes:
                if child.nodeName != 'li':
                    self._reportError(filename, node,
                                      'only list items allowed in lists')


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
                  "tr", "td", "th", "style", "sub", "sup", "link"])

span = list2dict(['footnote', 'manhole-output', 'index'])

div = list2dict(['note', 'boxed', 'doit'])

a = list2dict(['listing', 'py-listing', 'html-listing', 'absolute'])

pre = list2dict(['python', 'shell', 'python-interpreter', 'elisp'])

allowed = {'code': classes.has_key, 'span': span.has_key, 'div': div.has_key,
           'a': a.has_key, 'pre': pre.has_key, 'ul': lambda x: x=='toc',
           'ol': lambda x: x=='toc', 'li': lambda x: x=='ignoretoc'}

def getDefaultChecker():
    return DefaultTagChecker(tags.__contains__, allowed)

def doFile(file, checker):
    doc = tree.parseFileAndReport(file)
    if doc:
        checker.check(doc, file)
