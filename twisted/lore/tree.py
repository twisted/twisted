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

import re, os, cStringIO, stat, time, cgi, glob
from twisted import copyright
from twisted.python import usage, htmlizer
from twisted.web import microdom, domhelpers


def fontifyFiles(infile, outfile):
    htmlizer.filter(infile, outfile)
    
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
    mtime = os.stat(fullpath)[stat.ST_MTIME]
    for node in domhelpers.findElementsWithAttribute(document, "class","mtime"):
        node.appendChild(microdom.Text(time.asctime(time.localtime(mtime))))

def fixAPI(document, url):
    # API references
    for node in domhelpers.findElementsWithAttribute(document, "class", "API"):
        base = ""
        if node.hasAttribute("base"):
            base = node.getAttribute("base") + "."
        newref = url % (base+node.childNodes[0].nodeValue)
        node2 = document.createElement("a")
        node2.setAttribute("href", newref)
        node2.childNodes = node.childNodes
        node.childNodes = [node2]


def fontifyPython(document):
    def matcher(n):
        return (n.nodeName == 'pre' and n.hasAttribute('class') and
                n.getAttribute('class') == 'python')
    for node in domhelpers.findElements(document, matcher):
        newio = cStringIO.StringIO()
        # write the python code to a buffer
        oldio = cStringIO.StringIO()
        domhelpers.writeNodeData(node, oldio)
        oiv = oldio.getvalue()
        oivs = oiv.strip() + '\n'
        oldio = cStringIO.StringIO()
        oldio.write(oivs)
        oldio.seek(0)
        fontifyFiles(oldio, newio)
        newio.seek(0)
        newdom = microdom.parse(newio)
        newel = newdom.documentElement
        newel.setAttribute("class", "python")
        node.parentNode.replaceChild(newel, node)


def addPyListings(document, d):
    for node in domhelpers.findElementsWithAttribute(document, "class",
                                                     "py-listing"):
        fn = node.getAttribute("href")
        outfile = cStringIO.StringIO()
        fontifyFiles(open(os.path.join(d, fn)), outfile)
        val = outfile.getvalue()

        text = ('<div class="py-listing">'
               #'<pre class="python">%s</pre>' #redundant?
                '%s'
                '<div class="py-caption">%s - '
                '<span class="py-filename">%s</span></div></div>' % (
            val, domhelpers.getNodeText(node), node.getAttribute("href")))
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
                        val, domhelpers.getNodeText(node),
                             node.getAttribute('href')))
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
    h1 = domhelpers.findNodesNamed(document, 'h1')
    if h1:
        h1 = h1[0]
        parent = h1.parentNode
        i = parent.childNodes.index(h1)
        parent.childNodes[i+1:i+1] = [toc]

def footnotes(document):
    footnotes = domhelpers.findElementsWithAttribute(document, "class",
                                                     "footnote")
    if not footnotes:
        return
    footnoteElement = microdom.Element('ul')
    id = 0
    for footnote in footnotes:
        href = microdom.parseString('<a href="#footnote-%d">'
                                    '<super>*</super></a>'
                                    % id).documentElement
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


def munge(document, template, linkrel, d, fullpath, ext, url):
    addMtime(template, fullpath)
    fixAPI(document, url)
    fontifyPython(document)
    addPyListings(document, d)
    addHTMLListings(document, d)
    fixLinks(document, ext)
    putInToC(document, generateToC(document))
    footnotes(document)
    notes(document)

    # the title
    domhelpers.findNodesNamed(template, "title")[0].childNodes.extend(
        domhelpers.findNodesNamed(document, 'title')[0].childNodes)
    body = domhelpers.findNodesNamed(document, "body")[0]
    tmplbody = domhelpers.findElementsWithAttribute(template, "class",
                                                              "body")[0]
    tmplbody.childNodes = body.childNodes
    tmplbody.setAttribute("class", "content")


def doFile(fn, docsdir, ext, url, templ):
    try:
        doc = microdom.parse(open(fn))
    except microdom.MismatchedTags, e:
        print ("%s:%s:%s: begin mismatched tags <%s>/</%s>" %
               (e.filename, e.begLine, e.begCol, e.got, e.expect))
        print ("%s:%s:%s: end mismatched tags <%s>/</%s>" %
               (e.filename, e.endLine, e.endCol, e.got, e.expect))
        return
    except microdom.ParseError, e:
        print e
        return
    cn = templ.cloneNode(1)
    munge(doc, cn, '', docsdir, fn, ext, url)
    cn.writexml(open(os.path.splitext(fn)[0]+ext, 'wb'))
