# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
from twisted.web import microdom, domhelpers
import os

def makeBook(dom, d):
    body = microdom.Element('body')
    body.appendChild(domhelpers.findNodesNamed(dom, 'h1')[0])
    toc = domhelpers.findElementsWithAttribute(dom, 'class', 'toc')[0]
    toc = domhelpers.findNodesNamed(toc, 'li')
    for node in toc:
        if (node.hasAttribute('class') and
            node.getAttribute('class')=='tocignore'):
             continue
        parents = domhelpers.getParents(node)
        nodeLevel = len([1 for parent in parents if hasattr(parent, 'tagName')
                                           and parent.tagName in ('ol', 'ul')])
        data = node.childNodes[0].data != ''
        if not data:
            node = node.childNodes[1]
            newNode = lowerDocument(node.getAttribute('href'), d, nodeLevel)
            for child in newNode.childNodes:
                body.appendChild(child)
        else:
            text = microdom.Text(node.childNodes[0].data)
            newNode = microdom.Element('h'+str(nodeLevel))
            newNode.appendChild(text)
            body.appendChild(newNode)
    origBody = domhelpers.findNodesNamed(dom, 'body')[0]
    origBody.parentNode.replaceChild(body, origBody)

def lowerDocument(href, d, nodeLevel):
    newNode = microdom.parse(open(os.path.join(d, href)))
    newNode = domhelpers.findNodesNamed(newNode, 'body')[0]
    headers = domhelpers.findElements(newNode,
              lambda x: len(x.tagName)==2 and x.tagName[0]=='h' and
                        x.tagName[1] in '123456')
    for header in headers:
        header.tagName = 'h'+str(int(header.tagName[1])+nodeLevel)
    return newNode

def doFile(infile, outfile):
    dom = microdom.parse(open(infile))
    dir = os.path.dirname(infile)
    makeBook(dom, dir)
    outfile = open(outfile, 'w')
    dom.writexml(outfile)
    outfile.close()

if __name__ == '__main__':
   import sys
   doFile(sys.argv[1], sys.argv[2])
