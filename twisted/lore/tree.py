# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

import re, os, cStringIO, time, cgi, glob
from twisted import copyright
from twisted.python import htmlizer
from twisted.web import microdom, domhelpers


# relative links to html files
def fixLinks(document, ext):
    for node in domhelpers.findElementsWithAttribute(document, 'href'):
        href = node.getAttribute("href")
        if '/' not in href:
            if href.endswith('.html') or href[:href.rfind('#')].endswith('.html'):
                fname, fext = os.path.splitext(href)
                fext = fext.replace('.html', ext) 
                node.setAttribute("href", fname + fext)


def addMtime(document, fullpath):
    for node in domhelpers.findElementsWithAttribute(document, "class","mtime"):
        node.appendChild(microdom.Text(time.ctime(os.path.getmtime(fullpath))))

def _getAPI(node):
    base = ""
    if node.hasAttribute("base"):
        base = node.getAttribute("base") + "."
    return base+node.childNodes[0].nodeValue

def fixAPI(document, url):
    # API references
    for node in domhelpers.findElementsWithAttribute(document, "class", "API"):
        fullname = _getAPI(node)
        node2 = microdom.Element('a', {'href': url%fullname, 'title': fullname})
        node2.childNodes = node.childNodes
        node.childNodes = [node2]

def expandAPI(document):
    seenAPI = {}
    for node in domhelpers.findElementsWithAttribute(document, "class", "API"):
        api = _getAPI(node)
        if seenAPI.get(api) or node.hasAttribute('noexpand'):
            continue
        node.childNodes[0].nodevalue = api
        node.removeAttribute('base')
        seenAPI[api] = 1


def fontifyPython(document):
    def matcher(n):
        return (n.nodeName == 'pre' and n.hasAttribute('class') and
                n.getAttribute('class') == 'python')
    for node in domhelpers.findElements(document, matcher):
        fontifyPythonNode(node)

def fontifyPythonNode(node):
    oldio = cStringIO.StringIO()
    domhelpers.writeNodeData(node, oldio)
    oldio = cStringIO.StringIO(oldio.getvalue().strip()+'\n')
    newio = cStringIO.StringIO()
    htmlizer.filter(oldio, newio)
    newio.seek(0)
    newel = microdom.parse(newio).documentElement
    newel.setAttribute("class", "python")
    node.parentNode.replaceChild(newel, node)


def addPyListings(document, d):
    for node in domhelpers.findElementsWithAttribute(document, "class",
                                                     "py-listing"):
        fn = node.getAttribute("href")
        outfile = cStringIO.StringIO()
        htmlizer.filter(open(os.path.join(d, fn)), outfile)
        val = outfile.getvalue()

        text = ('<div class="py-listing">'
               #'<pre class="python">%s</pre>' #redundant?
                '%s'
                '<div class="py-caption">%s - '
                '<span class="py-filename">%s</span></div></div>' % (
            val, domhelpers.getNodeText(node), fn))
        newnode = microdom.parseString(text).documentElement
        node.parentNode.replaceChild(newnode, node)


def addHTMLListings(document, d):
    for node in domhelpers.findElementsWithAttribute(document, "class",
                                                     "html-listing"):
        fn = node.getAttribute("href")
        val = cgi.escape(open(os.path.join(d, fn)).read())

        text = ('<div class="py-listing">'
                '<pre class="htmlsource">%s</pre>'
                '<div class="py-caption">%s - '
                '<span class="py-filename">%s</span></div></div>' % (
                        val, domhelpers.getNodeText(node), fn))
        newnode = microdom.parseString(text).documentElement
        node.parentNode.replaceChild(newnode, node)


def generateToC(document):
    headers = domhelpers.findElements(document, 
                           lambda n,m=re.compile('h[23]$').match:m(n.nodeName))
    toc, level, id = '\n<ol>\n', 0, 0
    for element in headers:
        elementLevel = int(element.tagName[1])-2
        toc += (level-elementLevel)*'</ul>\n'
        toc += (elementLevel-level)*'<ul>'
        toc += '<li><a href="#auto%d">' % id
        for child in element.childNodes:
            toc += child.toxml()
        toc += '</a></li>\n'
        level = elementLevel
        name = microdom.parseString('<a name="auto%d" />' % id).documentElement
        element.childNodes.append(name)
        id += 1
    toc += '</ul>\n' * level
    toc += '</ol>\n'
    return microdom.parseString(toc).documentElement


def putInToC(document, toc):
    tocOrig = domhelpers.findElementsWithAttribute(document, 'class', 'toc')
    if toc:
        tocOrig= tocOrig[0]
        tocOrig.childNodes = [toc]

def removeH1(document):
    h1 = domhelpers.findNodesNamed(document, 'h1')
    empty = microdom.Element('span')
    for node in h1:
        node.parentNode.replaceChild(empty, node)

def footnotes(document):
    footnotes = domhelpers.findElementsWithAttribute(document, "class",
                                                     "footnote")
    if not footnotes:
        return
    footnoteElement = microdom.Element('ol')
    id = 1
    for footnote in footnotes:
        href = microdom.parseString('<a href="#footnote-%(id)d">'
                                    '<super>%(id)d</super></a>'
                                    % vars()).documentElement
        text = ' '.join(domhelpers.getNodeText(footnote).split())
        href.setAttribute('title', text)
        target = microdom.Element('a', attributes={'name': 'footnote-%d' % id})
        target.childNodes = [footnote]
        footnoteContent = microdom.Element('li')
        footnoteContent.childNodes = [target]
        footnoteElement.childNodes.append(footnoteContent)
        footnote.parentNode.replaceChild(href, footnote)
    body = domhelpers.findNodesNamed(document, "body")[0]
    header = microdom.parseString('<h2>Footnotes</h2>').documentElement
    body.childNodes.append(header)
    body.childNodes.append(footnoteElement)

def notes(document):
    notes = domhelpers.findElementsWithAttribute(document, "class", "note")
    notePrefix = microdom.parseString('<strong>Note: </strong>').documentElement
    for note in notes:
        note.childNodes.insert(0, notePrefix)

def fixRelativeLinks(document, linkrel):
    for node in domhelpers.findElementsWithAttribute(document, "href"):
        node.setAttribute("href", linkrel+node.getAttribute("href"))

def munge(document, template, linkrel, d, fullpath, ext, url):
    fixRelativeLinks(template, linkrel)
    addMtime(template, fullpath)
    removeH1(document)
    expandAPI(document)
    fixAPI(document, url)
    fontifyPython(document)
    addPyListings(document, d)
    addHTMLListings(document, d)
    fixLinks(document, ext)
    putInToC(template, generateToC(document))
    footnotes(document)
    notes(document)

    title = domhelpers.findNodesNamed(document, 'title')[0].childNodes
    for nodeList in (domhelpers.findNodesNamed(template, "title"),
                     domhelpers.findElementsWithAttribute(template, "class",
                                                          'title')):
        nodeList[0].childNodes.extend(title)
    body = domhelpers.findNodesNamed(document, "body")[0]
    tmplbody = domhelpers.findElementsWithAttribute(template, "class",
                                                              "body")[0]
    tmplbody.childNodes = body.childNodes
    tmplbody.setAttribute("class", "content")


def parseFileAndReport(fn):
    try:
        return microdom.parse(open(fn))
    except microdom.MismatchedTags, e:
        print ("%s:%s:%s: begin mismatched tags <%s>/</%s>" %
               (e.filename, e.begLine, e.begCol, e.got, e.expect))
        print ("%s:%s:%s: end mismatched tags <%s>/</%s>" %
               (e.filename, e.endLine, e.endCol, e.got, e.expect))
    except microdom.ParseError, e:
        print e

def doFile(fn, docsdir, ext, url, templ, linkrel=''):
    doc = parseFileAndReport(fn)
    cn = templ.cloneNode(1)
    munge(doc, cn, linkrel, docsdir, fn, ext, url)
    cn.writexml(open(os.path.splitext(fn)[0]+ext, 'wb'))
