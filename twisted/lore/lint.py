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

class TagChecker:

    def __init__(self, allowedTags, allowedCodeClasses):
        self.allowedTags = allowedTags
        self.allowedCodeClasses = allowedCodeClasses

    def check(self, dom, filename):
        for method in reflect.prefixedMethods(self, 'check_'):
            method(dom, filename)

    def _reportError(self, filename, element, error):
        t = (filename,)+element._markpos+(error,)
        print ("%s:%s:%s: %s" % t)

    def check_disallowedElements(self, dom, filename):
        def m(node, self=self):
            return not self.allowedTags(node.tagName)
        for element in domhelpers.findElements(dom, m):
            self._reportError(filename, element,
                               'unrecommended tag %s' % element.tagName)

    def check_codeClass(self, dom, filename):
        def matcher(element, self=self):
            if element.tagName != 'code':
                return 0
            if not element.hasAttribute('class'):
                return 0
            if self.allowedCodeClasses(element.getAttribute('class')):
                return 0
            return 1
        for element in domhelpers.findElements(dom, matcher):
            self._reportError(filename, element,
                              'unkown class %s' %element.getAttribute('class'))

    def check_quote(self, dom, filename):
        def matcher(node):
            return ('"' in getattr(node, 'data', '') and
                    node.parentNode.tagName not in ('code', 'pre'))
        for node in domhelpers.findNodes(dom, matcher):
            if node.parentNode.parentNode.tagName in ('code', 'pre'):
                continue 
            self._reportError(filename, node.parentNode, 'contains quote')

def list2dict(l):
    d = {}
    for el in l:
        d[el] = None
    return d

classes = list2dict(['shell', 'API', 'python', 'py-prototype', 'py-filename',
                     'py-src-string', 'py-signature', 'py-src-parameter'])

tags = list2dict(["html", "title", "head", "body", "h1", "h2", "h3", "ol", "ul",
                  "dl", "li", "dt", "dd", "p", "code", "img", "blockquote", "a",
                  "cite", "div", "span", "strong", "em", "pre", "q", "table",
                  "tr", "td", "th", "style"])

def getDefaultChecker():
    return TagChecker(tags.has_key, classes.has_key)

def doFile(file, checker):
    dom = tree.parseFileAndReport(file)
    if not dom:
        return
    checker.check(dom, file)
