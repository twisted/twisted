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

import re, os, cStringIO, stat, time, cgi
from twisted import copyright
from twisted.python import usage, htmlizer
from twisted.web import microdom as dom


def findNodes(parent, matcher, accum=None):
    if accum is None:
        accum = []
    if not hasattr(parent, 'childNodes'):
        print 'no child nodes', parent
    for child in parent.childNodes:
        # print child, child.nodeType, child.nodeName
        findNodes(child, matcher, accum)
        if matcher(child):
            accum.append(child)
    return accum

def findElements(parent, matcher):
    return findNodes(
        parent,
        lambda n, matcher=matcher: isinstance(n, dom.Element) and matcher(n))

def findElementsWithAttribute(parent, attribute, value=None):
    if value:
        return findElements(
            parent,
            lambda n, attribute=attribute, value=value:
              n.hasAttribute(attribute) and n.getAttribute(attribute) == value)
    else:
        return findElements(
            parent,
            lambda n, attribute=attribute: n.hasAttribute(attribute))


def findNodesNamed(parent, name):
    return findNodes(parent, lambda n, name=name: n.nodeName == name)



class Cache:
    def __init__(self, basePath, baseURL):
        self.stuff = {}
        self.basePath = basePath
        self.baseURL = baseURL
        os.path.walk(basePath, self.addFiles, None)

    def addFiles(self, arg, path, files):
        path = path.replace(self.basePath, '')
        for file in files:
            file = os.path.join(path, file)
            module = (file.replace('.py.html', '')
                      .replace('/', '.'))

            self.stuff[module] = self.baseURL + file

    def match(self, name):
        """
        I take a fully-qualified *or* relative module or class-name, and return
        an URL to the Twisted API documentation for that name.
        """
        # Evil is fun.
        if not '.' in name:
            raise ValueError("Gimme more than just *%s* to work with, "
                             "will ya?!?" % name)
        name = '.*' + name.replace('.', '\.') + "\.html$"
        pat = re.compile(name)
        for k,v in self.stuff.items():
            if pat.match(k):
                return v

def fontifyFiles(infile, outfile):
    htmlizer.filter(infile, outfile)
    

def writeNodeData(node, oldio):
    for subnode in node.childNodes:
        if hasattr(subnode, 'data'):
            oldio.write(str(subnode.data))
        else:
            writeNodeData(subnode, oldio)


def getNodeText(node):
    oldio = cStringIO.StringIO()
    writeNodeData(node, oldio)
    return oldio.getvalue()

# relative links to html files
def fixLinks(document, ext):
    for node in findElementsWithAttribute(document, 'href'):
        href = node.getAttribute("href")
        if not (href.startswith("http://") or href.startswith("mailto:")):
            fname = os.path.splitext(href)
            if len(fname) == 2 and fname[1] == '.html':
                node.setAttribute("href", fname[0] + ext)


def addMtime(document, fullpath):
    mtime = os.stat(fullpath)[stat.ST_MTIME]
    for node in findElementsWithAttribute(document, "class", "mtime"):
        node.appendChild(dom.Text(time.asctime(time.localtime(mtime))))

def fixFromTop(nodes, linkrel):
    for node in nodes:
        if node.hasAttribute('src'):
            attr = 'src'
        else:
            attr = 'href'
        node.setAttribute(attr, linkrel+node.getAttribute(attr))


def fixAPI(document, cache):
    # API references
    for node in findElementsWithAttribute(document, "class", "API"):
        if len(node.childNodes) > 1:
            print 'There are too many child nodes of this API link.'
        base = ""
        if node.hasAttribute("base"):
            base = node.getAttribute("base") + "."
        newref = cache.match(base + node.childNodes[0].nodeValue)
        if newref:
            node2 = document.createElement("a")
            node2.setAttribute("href", newref)
            node2.childNodes = node.childNodes
            node.childNodes = [node2]


def fontifyPython(document):
    def matcher(n):
        return (n.nodeName == 'pre' and n.hasAttribute('class') and
                n.getAttribute('class') == 'python')
    for node in findElements(document, matcher):
        newio = cStringIO.StringIO()
        # write the python code to a buffer
        oldio = cStringIO.StringIO()
        writeNodeData(node, oldio)
        oiv = oldio.getvalue()
        oivs = oiv.strip() + '\n'
        oldio = cStringIO.StringIO()
        oldio.write(oivs)
        oldio.seek(0)
        fontifyFiles(oldio, newio)
        newio.seek(0)
        newdom = dom.parse(newio)
        newel = newdom.documentElement
        newel.setAttribute("class", "python")
        node.parentNode.replaceChild(newel, node)


def addPyListings(document, d):
    for node in findElementsWithAttribute(document, "class", "py-listing"):
        fn = node.getAttribute("href")
        outfile = cStringIO.StringIO()
        fontifyFiles(open(os.path.join(d, fn)), outfile)
        val = outfile.getvalue()

        text = ('<div class="py-listing">'
               #'<pre class="python">%s</pre>' #redundant?
                '%s'
                '<div class="py-caption">%s - '
                '<span class="py-filename">%s</span></div></div>' % (
            val, getNodeText(node), node.getAttribute("href")))
        newnode = dom.parseString(text).documentElement
        node.parentNode.replaceChild(newnode, node)


def addHTMLListings(document, d):
    for node in findElementsWithAttribute(document, "class", "html-listing"):
        fn = node.getAttribute("href")
        val = cgi.escape(open(os.path.join(d, fn)).read())

        text = ('<div class="py-listing">'
                '<pre class="htmlsource">%s</pre>'
                '<div class="py-caption">%s - '
                '<span class="py-filename">%s</span></div></div>' % (
                        val, getNodeText(node), node.getAttribute('href')))
        newnode = dom.parseString(text).documentElement
        node.parentNode.replaceChild(newnode, node)


def generateToC(document):
    headers = findElements(document, 
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
        name = dom.parseString('<a name="auto%d" />' % id).documentElement
        element.childNodes.append(name)
        id += 1
    toc += '</ul>\n' * level
    toc += '</ol>\n'
    return dom.parseString(toc).documentElement


def putInToC(document, toc):
    h1 = findNodesNamed(document, 'h1')
    if h1:
        h1 = h1[0]
        parent = h1.parentNode
        i = parent.childNodes.index(h1)
        parent.childNodes[i+1:i+1] = [toc]

def footnotes(document):
    footnotes = findElementsWithAttribute(document, "class", "footnote")
    if not footnotes:
        return
    footnoteElement = dom.Element('ul')
    id = 0
    for footnote in footnotes:
        href = dom.parseString('<a href="#footnote-%d"><super>*</super></a>'
                               % id).documentElement
        target = dom.Element('a', attributes={'name': 'footnote-%d' % id})
        target.childNodes = [footnote]
        footnoteContent = dom.Element('li')
        footnoteContent.childNodes = [target]
        footnoteElement.childNodes.append(footnoteContent)
        footnote.parentNode.replaceChild(href, footnote)
    body = findNodesNamed(document, "body")[0]
    header = dom.parseString('<h2>Footnotes</h2>').documentElement
    body.childNodes.append(header)
    body.childNodes.append(footnoteElement)

def munge(document, template, linkrel, d, fullpath, ext, cache):
    addMtime(template, fullpath)
    # things linked from the top
    for list in (findElementsWithAttribute(template,"src"),
                 findElementsWithAttribute(template,"href"),
                 findElementsWithAttribute(document, "fromtop")):
        fixFromTop(list, linkrel)
    fixAPI(document, cache)
    fontifyPython(document)
    addPyListings(document, d)
    addHTMLListings(document, d)
    for doc in (template, document):
        fixLinks(doc, ext)
    putInToC(document, generateToC(document))
    footnotes(document)

    # the title
    findNodesNamed(template, "title")[0].childNodes.extend(
        findNodesNamed(document, 'title')[0].childNodes)
    body = findNodesNamed(document, "body")[0]
    tmplbody = findElementsWithAttribute(template, "class", "body")[0]
    tmplbody.childNodes = body.childNodes
    tmplbody.setAttribute("class", "content")


def doFile(fn, docsdir, ext, c, templ):
    try:
        doc = dom.parse(open(fn))
    except dom.MismatchedTags, e:
        print ("%s:%s:%s: begin mismatched tags <%s>/</%s>" %
               (e.filename, e.begLine, e.begCol, e.got, e.expect))
        print ("%s:%s:%s: end mismatched tags <%s>/</%s>" %
               (e.filename, e.endLine, e.endCol, e.got, e.expect))
        return
    except dom.ParseError, e:
        print e
        return
    cn = templ.cloneNode(1)
    munge(doc, cn, '', docsdir, fn, ext, c)
    cn.writexml(open(os.path.splitext(fn)[0]+ext, 'wb'))
