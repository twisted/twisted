# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from itertools import count
import re, os, cStringIO, time, cgi, urlparse
from xml.dom import minidom as dom
from xml.sax.handler import ErrorHandler, feature_validation
from xml.dom.pulldom import SAX2DOM
from xml.sax import make_parser
from xml.sax.xmlreader import InputSource

from twisted.python import htmlizer
from twisted.python.filepath import FilePath
from twisted.web import domhelpers
import process, latex, indexer, numberer, htmlbook



# relative links to html files
def fixLinks(document, ext):
    """
    Rewrite links to XHTML lore input documents so they point to lore XHTML
    output documents.

    Any node with an C{href} attribute which does not contain a value starting
    with C{http}, C{https}, C{ftp}, or C{mailto} and which does not have a
    C{class} attribute of C{absolute} or which contains C{listing} and which
    does point to an URL ending with C{html} will have that attribute value
    rewritten so that the filename extension is C{ext} instead of C{html}.

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @type ext: C{str}
    @param ext: The extension to use when selecting an output file name.  This
    replaces the extension of the input file name.

    @return: C{None}
    """
    supported_schemes=['http', 'https', 'ftp', 'mailto']
    for node in domhelpers.findElementsWithAttribute(document, 'href'):
        href = node.getAttribute("href")
        if urlparse.urlparse(href)[0] in supported_schemes:
            continue
        if node.getAttribute("class") == "absolute":
            continue
        if node.getAttribute("class").find('listing') != -1:
            continue

        # This is a relative link, so it should be munged.
        if href.endswith('html') or href[:href.rfind('#')].endswith('html'):
            fname, fext = os.path.splitext(href)
            if '#' in fext:
                fext = ext+'#'+fext.split('#', 1)[1]
            else:
                fext = ext
            node.setAttribute("href", fname + fext)



def addMtime(document, fullpath):
    """
    Set the last modified time of the given document.

    @type document: A DOM Node or Document
    @param document: The output template which defines the presentation of the
    last modified time.

    @type fullpath: C{str}
    @param fullpath: The file name from which to take the last modified time.

    @return: C{None}
    """
    for node in domhelpers.findElementsWithAttribute(document, "class","mtime"):
        txt = dom.Text()
        txt.data = time.ctime(os.path.getmtime(fullpath))
        node.appendChild(txt)



def _getAPI(node):
    """
    Retrieve the fully qualified Python name represented by the given node.

    The name is represented by one or two aspects of the node: the value of the
    node's first child forms the end of the name.  If the node has a C{base}
    attribute, that attribute's value is prepended to the node's value, with
    C{.} separating the two parts.

    @rtype: C{str}
    @return: The fully qualified Python name.
    """
    base = ""
    if node.hasAttribute("base"):
        base = node.getAttribute("base") + "."
    return base+node.childNodes[0].nodeValue



def fixAPI(document, url):
    """
    Replace API references with links to API documentation.

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @type url: C{str}
    @param url: A string which will be interpolated with the fully qualified
    Python name of any API reference encountered in the input document, the
    result of which will be used as a link to API documentation for that name
    in the output document.

    @return: C{None}
    """
    # API references
    for node in domhelpers.findElementsWithAttribute(document, "class", "API"):
        fullname = _getAPI(node)
        anchor = dom.Element('a')
        anchor.setAttribute('href', url % (fullname,))
        anchor.setAttribute('title', fullname)
        while node.childNodes:
            child = node.childNodes[0]
            node.removeChild(child)
            anchor.appendChild(child)
        node.appendChild(anchor)
        if node.hasAttribute('base'):
            node.removeAttribute('base')



def fontifyPython(document):
    """
    Syntax color any node in the given document which contains a Python source
    listing.

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @return: C{None}
    """
    def matcher(node):
        return (node.nodeName == 'pre' and node.hasAttribute('class') and
                node.getAttribute('class') == 'python')
    for node in domhelpers.findElements(document, matcher):
        fontifyPythonNode(node)



def fontifyPythonNode(node):
    """
    Syntax color the given node containing Python source code.

    The node must have a parent.

    @return: C{None}
    """
    oldio = cStringIO.StringIO()
    latex.getLatexText(node, oldio.write,
                       entities={'lt': '<', 'gt': '>', 'amp': '&'})
    oldio = cStringIO.StringIO(oldio.getvalue().strip()+'\n')
    howManyLines = len(oldio.getvalue().splitlines())
    newio = cStringIO.StringIO()
    htmlizer.filter(oldio, newio, writer=htmlizer.SmallerHTMLWriter)
    lineLabels = _makeLineNumbers(howManyLines)
    newel = dom.parseString(newio.getvalue()).documentElement
    newel.setAttribute("class", "python")
    node.parentNode.replaceChild(newel, node)
    newel.insertBefore(lineLabels, newel.firstChild)



def addPyListings(document, dir):
    """
    Insert Python source listings into the given document from files in the
    given directory based on C{py-listing} nodes.

    Any node in C{document} with a C{class} attribute set to C{py-listing} will
    have source lines taken from the file named in that node's C{href}
    attribute (searched for in C{dir}) inserted in place of that node.

    If a node has a C{skipLines} attribute, its value will be parsed as an
    integer and that many lines will be skipped at the beginning of the source
    file.

    @type document: A DOM Node or Document
    @param document: The document within which to make listing replacements.

    @type dir: C{str}
    @param dir: The directory in which to find source files containing the
    referenced Python listings.

    @return: C{None}
    """
    for node in domhelpers.findElementsWithAttribute(document, "class",
                                                     "py-listing"):
        filename = node.getAttribute("href")
        outfile = cStringIO.StringIO()
        lines = map(str.rstrip, open(os.path.join(dir, filename)).readlines())

        skip = node.getAttribute('skipLines') or 0
        lines = lines[int(skip):]
        howManyLines = len(lines)
        data = '\n'.join(lines)

        data = cStringIO.StringIO(_removeLeadingTrailingBlankLines(data))
        htmlizer.filter(data, outfile, writer=htmlizer.SmallerHTMLWriter)
        sourceNode = dom.parseString(outfile.getvalue()).documentElement
        sourceNode.insertBefore(_makeLineNumbers(howManyLines), sourceNode.firstChild)
        _replaceWithListing(node, sourceNode.toxml(), filename, "py-listing")



def _makeLineNumbers(howMany):
    """
    Return an element which will render line numbers for a source listing.

    @param howMany: The number of lines in the source listing.
    @type howMany: C{int}

    @return: An L{dom.Element} which can be added to the document before
        the source listing to add line numbers to it.
    """
    # Figure out how many digits wide the widest line number label will be.
    width = len(str(howMany))

    # Render all the line labels with appropriate padding
    labels = ['%*d' % (width, i) for i in range(1, howMany + 1)]

    # Create a p element with the right style containing the labels
    p = dom.Element('p')
    p.setAttribute('class', 'py-linenumber')
    t = dom.Text()
    t.data = '\n'.join(labels) + '\n'
    p.appendChild(t)
    return p


def _replaceWithListing(node, val, filename, class_):
    captionTitle = domhelpers.getNodeText(node)
    if captionTitle == os.path.basename(filename):
        captionTitle = 'Source listing'
    text = ('<div class="%s">%s<div class="caption">%s - '
            '<a href="%s"><span class="filename">%s</span></a></div></div>' %
            (class_, val, captionTitle, filename, filename))
    newnode = dom.parseString(text).documentElement
    node.parentNode.replaceChild(newnode, node)



def _removeLeadingBlankLines(lines):
    """
    Removes leading blank lines from C{lines} and returns a list containing the
    remaining characters.

    @param lines: Input string.
    @type lines: L{str}
    @rtype: C{list}
    @return: List of characters.
    """
    ret = []
    for line in lines:
        if ret or line.strip():
            ret.append(line)
    return ret



def _removeLeadingTrailingBlankLines(inputString):
    """
    Splits input string C{inputString} into lines, strips leading and trailing
    blank lines, and returns a string with all lines joined, each line
    separated by a newline character.

    @param inputString: The input string.
    @type inputString: L{str}
    @rtype: L{str}
    @return: String containing normalized lines.
    """
    lines = _removeLeadingBlankLines(inputString.split('\n'))
    lines.reverse()
    lines = _removeLeadingBlankLines(lines)
    lines.reverse()
    return '\n'.join(lines) + '\n'



def addHTMLListings(document, dir):
    """
    Insert HTML source listings into the given document from files in the given
    directory based on C{html-listing} nodes.

    Any node in C{document} with a C{class} attribute set to C{html-listing}
    will have source lines taken from the file named in that node's C{href}
    attribute (searched for in C{dir}) inserted in place of that node.

    @type document: A DOM Node or Document
    @param document: The document within which to make listing replacements.

    @type dir: C{str}
    @param dir: The directory in which to find source files containing the
    referenced HTML listings.

    @return: C{None}
    """
    for node in domhelpers.findElementsWithAttribute(document, "class",
                                                     "html-listing"):
        filename = node.getAttribute("href")
        val = ('<pre class="htmlsource">\n%s</pre>' %
               cgi.escape(open(os.path.join(dir, filename)).read()))
        _replaceWithListing(node, val, filename, "html-listing")



def addPlainListings(document, dir):
    """
    Insert text listings into the given document from files in the given
    directory based on C{listing} nodes.

    Any node in C{document} with a C{class} attribute set to C{listing} will
    have source lines taken from the file named in that node's C{href}
    attribute (searched for in C{dir}) inserted in place of that node.

    @type document: A DOM Node or Document
    @param document: The document within which to make listing replacements.

    @type dir: C{str}
    @param dir: The directory in which to find source files containing the
    referenced text listings.

    @return: C{None}
    """
    for node in domhelpers.findElementsWithAttribute(document, "class",
                                                     "listing"):
        filename = node.getAttribute("href")
        val = ('<pre>\n%s</pre>' %
               cgi.escape(open(os.path.join(dir, filename)).read()))
        _replaceWithListing(node, val, filename, "listing")



def getHeaders(document):
    """
    Return all H2 and H3 nodes in the given document.

    @type document: A DOM Node or Document

    @rtype: C{list}
    """
    return domhelpers.findElements(
        document,
        lambda n, m=re.compile('h[23]$').match: m(n.nodeName))



def generateToC(document):
    """
    Create a table of contents for the given document.

    @type document: A DOM Node or Document

    @rtype: A DOM Node
    @return: a Node containing a table of contents based on the headers of the
    given document.
    """
    subHeaders = None
    headers = []
    for element in getHeaders(document):
        if element.tagName == 'h2':
            subHeaders = []
            headers.append((element, subHeaders))
        elif subHeaders is None:
            raise ValueError(
                "No H3 element is allowed until after an H2 element")
        else:
            subHeaders.append(element)

    auto = count().next

    def addItem(headerElement, parent):
        anchor = dom.Element('a')
        name = 'auto%d' % (auto(),)
        anchor.setAttribute('href', '#' + name)
        text = dom.Text()
        text.data = domhelpers.getNodeText(headerElement)
        anchor.appendChild(text)
        headerNameItem = dom.Element('li')
        headerNameItem.appendChild(anchor)
        parent.appendChild(headerNameItem)
        anchor = dom.Element('a')
        anchor.setAttribute('name', name)
        headerElement.appendChild(anchor)

    toc = dom.Element('ol')
    for headerElement, subHeaders in headers:
        addItem(headerElement, toc)
        if subHeaders:
            subtoc = dom.Element('ul')
            toc.appendChild(subtoc)
            for subHeaderElement in subHeaders:
                addItem(subHeaderElement, subtoc)

    return toc



def putInToC(document, toc):
    """
    Insert the given table of contents into the given document.

    The node with C{class} attribute set to C{toc} has its children replaced
    with C{toc}.

    @type document: A DOM Node or Document
    @type toc: A DOM Node
    """
    tocOrig = domhelpers.findElementsWithAttribute(document, 'class', 'toc')
    if tocOrig:
        tocOrig= tocOrig[0]
        tocOrig.childNodes = [toc]



def removeH1(document):
    """
    Replace all C{h1} nodes in the given document with empty C{span} nodes.

    C{h1} nodes mark up document sections and the output template is given an
    opportunity to present this information in a different way.

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @return: C{None}
    """
    h1 = domhelpers.findNodesNamed(document, 'h1')
    empty = dom.Element('span')
    for node in h1:
        node.parentNode.replaceChild(empty, node)



def footnotes(document):
    """
    Find footnotes in the given document, move them to the end of the body, and
    generate links to them.

    A footnote is any node with a C{class} attribute set to C{footnote}.
    Footnote links are generated as superscript.  Footnotes are collected in a
    C{ol} node at the end of the document.

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @return: C{None}
    """
    footnotes = domhelpers.findElementsWithAttribute(document, "class",
                                                     "footnote")
    if not footnotes:
        return
    footnoteElement = dom.Element('ol')
    id = 1
    for footnote in footnotes:
        href = dom.parseString('<a href="#footnote-%(id)d">'
                               '<super>%(id)d</super></a>'
                               % vars()).documentElement
        text = ' '.join(domhelpers.getNodeText(footnote).split())
        href.setAttribute('title', text)
        target = dom.Element('a')
        target.setAttribute('name', 'footnote-%d' % (id,))
        target.childNodes = [footnote]
        footnoteContent = dom.Element('li')
        footnoteContent.childNodes = [target]
        footnoteElement.childNodes.append(footnoteContent)
        footnote.parentNode.replaceChild(href, footnote)
        id += 1
    body = domhelpers.findNodesNamed(document, "body")[0]
    header = dom.parseString('<h2>Footnotes</h2>').documentElement
    body.childNodes.append(header)
    body.childNodes.append(footnoteElement)



def notes(document):
    """
    Find notes in the given document and mark them up as such.

    A note is any node with a C{class} attribute set to C{note}.

    (I think this is a very stupid feature.  When I found it I actually
    exclaimed out loud. -exarkun)

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @return: C{None}
    """
    notes = domhelpers.findElementsWithAttribute(document, "class", "note")
    notePrefix = dom.parseString('<strong>Note: </strong>').documentElement
    for note in notes:
        note.childNodes.insert(0, notePrefix)



def findNodeJustBefore(target, nodes):
    """
    Find the last Element which is a sibling of C{target} and is in C{nodes}.

    @param target: A node the previous sibling of which to return.
    @param nodes: A list of nodes which might be the right node.

    @return: The previous sibling of C{target}.
    """
    while target is not None:
        node = target.previousSibling
        while node is not None:
            if node in nodes:
                return node
            node = node.previousSibling
        target = target.parentNode
    raise RuntimeError("Oops")



def getFirstAncestorWithSectionHeader(entry):
    """
    Visit the ancestors of C{entry} until one with at least one C{h2} child
    node is found, then return all of that node's C{h2} child nodes.

    @type entry: A DOM Node
    @param entry: The node from which to begin traversal.  This node itself is
    excluded from consideration.

    @rtype: C{list} of DOM Nodes
    @return: All C{h2} nodes of the ultimately selected parent node.
    """
    for a in domhelpers.getParents(entry)[1:]:
        headers = domhelpers.findNodesNamed(a, "h2")
        if len(headers) > 0:
            return headers
    return []



def getSectionNumber(header):
    """
    Retrieve the section number of the given node.

    This is probably intended to interact in a rather specific way with
    L{numberDocument}.

    @type header: A DOM Node or L{None}
    @param header: The section from which to extract a number.  The section
        number is the value of this node's first child.

    @return: C{None} or a C{str} giving the section number.
    """
    if not header:
        return None
    return domhelpers.gatherTextNodes(header.childNodes[0])



def getSectionReference(entry):
    """
    Find the section number which contains the given node.

    This function looks at the given node's ancestry until it finds a node
    which defines a section, then returns that section's number.

    @type entry: A DOM Node
    @param entry: The node for which to determine the section.

    @rtype: C{str}
    @return: The section number, as returned by C{getSectionNumber} of the
    first ancestor of C{entry} which defines a section, as determined by
    L{getFirstAncestorWithSectionHeader}.
    """
    headers = getFirstAncestorWithSectionHeader(entry)
    myHeader = findNodeJustBefore(entry, headers)
    return getSectionNumber(myHeader)



def index(document, filename, chapterReference):
    """
    Extract index entries from the given document and store them for later use
    and insert named anchors so that the index can link back to those entries.

    Any node with a C{class} attribute set to C{index} is considered an index
    entry.

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @type filename: C{str}
    @param filename: A link to the output for the given document which will be
    included in the index to link to any index entry found here.

    @type chapterReference: ???
    @param chapterReference: ???

    @return: C{None}
    """
    entries = domhelpers.findElementsWithAttribute(document, "class", "index")
    if not entries:
        return
    i = 0;
    for entry in entries:
        i += 1
        anchor = 'index%02d' % i
        if chapterReference:
            ref = getSectionReference(entry) or chapterReference
        else:
            ref = 'link'
        indexer.addEntry(filename, anchor, entry.getAttribute('value'), ref)
        # does nodeName even affect anything?
        entry.nodeName = entry.tagName = entry.endTagName = 'a'
        for attrName in entry.attributes.keys():
            entry.removeAttribute(attrName)
        entry.setAttribute('name', anchor)



def setIndexLink(template, indexFilename):
    """
    Insert a link to an index document.

    Any node with a C{class} attribute set to C{index-link} will have its tag
    name changed to C{a} and its C{href} attribute set to C{indexFilename}.

    @type template: A DOM Node or Document
    @param template: The output template which defines the presentation of the
    version information.

    @type indexFilename: C{str}
    @param indexFilename: The address of the index document to which to link.
    If any C{False} value, this function will remove all index-link nodes.

    @return: C{None}
    """
    indexLinks = domhelpers.findElementsWithAttribute(template,
                                                      "class",
                                                      "index-link")
    for link in indexLinks:
        if indexFilename is None:
            link.parentNode.removeChild(link)
        else:
            link.nodeName = link.tagName = link.endTagName = 'a'
            for attrName in link.attributes.keys():
                link.removeAttribute(attrName)
            link.setAttribute('href', indexFilename)



def numberDocument(document, chapterNumber):
    """
    Number the sections of the given document.

    A dot-separated chapter, section number is added to the beginning of each
    section, as defined by C{h2} nodes.

    This is probably intended to interact in a rather specific way with
    L{getSectionNumber}.

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @type chapterNumber: C{int}
    @param chapterNumber: The chapter number of this content in an overall
    document.

    @return: C{None}
    """
    i = 1
    for node in domhelpers.findNodesNamed(document, "h2"):
        label = dom.Text()
        label.data = "%s.%d " % (chapterNumber, i)
        node.insertBefore(label, node.firstChild)
        i += 1



def fixRelativeLinks(document, linkrel):
    """
    Replace relative links in C{str} and C{href} attributes with links relative
    to C{linkrel}.

    @type document: A DOM Node or Document
    @param document: The output template.

    @type linkrel: C{str}
    @param linkrel: An prefix to apply to all relative links in C{src} or
    C{href} attributes in the input document when generating the output
    document.
    """
    for attr in 'src', 'href':
        for node in domhelpers.findElementsWithAttribute(document, attr):
            href = node.getAttribute(attr)
            if not href.startswith('http') and not href.startswith('/'):
                node.setAttribute(attr, linkrel+node.getAttribute(attr))



def setTitle(template, title, chapterNumber):
    """
    Add title and chapter number information to the template document.

    The title is added to the end of the first C{title} tag and the end of the
    first tag with a C{class} attribute set to C{title}.  If specified, the
    chapter is inserted before the title.

    @type template: A DOM Node or Document
    @param template: The output template which defines the presentation of the
    version information.

    @type title: C{list} of DOM Nodes
    @param title: Nodes from the input document defining its title.

    @type chapterNumber: C{int}
    @param chapterNumber: The chapter number of this content in an overall
    document.  If not applicable, any C{False} value will result in this
    information being omitted.

    @return: C{None}
    """
    if numberer.getNumberSections() and chapterNumber:
        titleNode = dom.Text()
        # This is necessary in order for cloning below to work.  See Python
        # isuse 4851.
        titleNode.ownerDocument = template.ownerDocument
        titleNode.data = '%s. ' % (chapterNumber,)
        title.insert(0, titleNode)

    for nodeList in (domhelpers.findNodesNamed(template, "title"),
                     domhelpers.findElementsWithAttribute(template, "class",
                                                          'title')):
        if nodeList:
            for titleNode in title:
                nodeList[0].appendChild(titleNode.cloneNode(True))



def setAuthors(template, authors):
    """
    Add author information to the template document.

    Names and contact information for authors are added to each node with a
    C{class} attribute set to C{authors} and to the template head as C{link}
    nodes.

    @type template: A DOM Node or Document
    @param template: The output template which defines the presentation of the
    version information.

    @type authors: C{list} of two-tuples of C{str}
    @param authors: List of names and contact information for the authors of
    the input document.

    @return: C{None}
    """

    for node in domhelpers.findElementsWithAttribute(template,
                                                     "class", 'authors'):

        # First, similarly to setTitle, insert text into an <div
        # class="authors">
        container = dom.Element('span')
        for name, href in authors:
            anchor = dom.Element('a')
            anchor.setAttribute('href', href)
            anchorText = dom.Text()
            anchorText.data = name
            anchor.appendChild(anchorText)
            if (name, href) == authors[-1]:
                if len(authors) == 1:
                    container.appendChild(anchor)
                else:
                    andText = dom.Text()
                    andText.data = 'and '
                    container.appendChild(andText)
                    container.appendChild(anchor)
            else:
                container.appendChild(anchor)
                commaText = dom.Text()
                commaText.data = ', '
                container.appendChild(commaText)

        node.appendChild(container)

    # Second, add appropriate <link rel="author" ...> tags to the <head>.
    head = domhelpers.findNodesNamed(template, 'head')[0]
    authors = [dom.parseString('<link rel="author" href="%s" title="%s"/>'
                               % (href, name)).childNodes[0]
               for name, href in authors]
    head.childNodes.extend(authors)



def setVersion(template, version):
    """
    Add a version indicator to the given template.

    @type template: A DOM Node or Document
    @param template: The output template which defines the presentation of the
    version information.

    @type version: C{str}
    @param version: The version string to add to the template.

    @return: C{None}
    """
    for node in domhelpers.findElementsWithAttribute(template, "class",
                                                               "version"):
        text = dom.Text()
        text.data = version
        node.appendChild(text)



def getOutputFileName(originalFileName, outputExtension, index=None):
    """
    Return a filename which is the same as C{originalFileName} except for the
    extension, which is replaced with C{outputExtension}.

    For example, if C{originalFileName} is C{'/foo/bar.baz'} and
    C{outputExtension} is C{'quux'}, the return value will be
    C{'/foo/bar.quux'}.

    @type originalFileName: C{str}
    @type outputExtension: C{stR}
    @param index: ignored, never passed.
    @rtype: C{str}
    """
    return os.path.splitext(originalFileName)[0]+outputExtension



def munge(document, template, linkrel, dir, fullpath, ext, url, config, outfileGenerator=getOutputFileName):
    """
    Mutate C{template} until it resembles C{document}.

    @type document: A DOM Node or Document
    @param document: The input document which contains all of the content to be
    presented.

    @type template: A DOM Node or Document
    @param template: The template document which defines the desired
    presentation format of the content.

    @type linkrel: C{str}
    @param linkrel: An prefix to apply to all relative links in C{src} or
    C{href} attributes in the input document when generating the output
    document.

    @type dir: C{str}
    @param dir: The directory in which to search for source listing files.

    @type fullpath: C{str}
    @param fullpath: The file name which contained the input document.

    @type ext: C{str}
    @param ext: The extension to use when selecting an output file name.  This
    replaces the extension of the input file name.

    @type url: C{str}
    @param url: A string which will be interpolated with the fully qualified
    Python name of any API reference encountered in the input document, the
    result of which will be used as a link to API documentation for that name
    in the output document.

    @type config: C{dict}
    @param config: Further specification of the desired form of the output.
    Valid keys in this dictionary::

        noapi: If present and set to a True value, links to API documentation
               will not be generated.

        version: A string which will be included in the output to indicate the
                 version of this documentation.

    @type outfileGenerator: Callable of C{str}, C{str} returning C{str}
    @param outfileGenerator: Output filename factory.  This is invoked with the
    intput filename and C{ext} and the output document is serialized to the
    file with the name returned.

    @return: C{None}
    """
    fixRelativeLinks(template, linkrel)
    addMtime(template, fullpath)
    removeH1(document)
    if not config.get('noapi', False):
        fixAPI(document, url)
    fontifyPython(document)
    fixLinks(document, ext)
    addPyListings(document, dir)
    addHTMLListings(document, dir)
    addPlainListings(document, dir)
    putInToC(template, generateToC(document))
    footnotes(document)
    notes(document)

    setIndexLink(template, indexer.getIndexFilename())
    setVersion(template, config.get('version', ''))

    # Insert the document into the template
    chapterNumber = htmlbook.getNumber(fullpath)
    title = domhelpers.findNodesNamed(document, 'title')[0].childNodes
    setTitle(template, title, chapterNumber)
    if numberer.getNumberSections() and chapterNumber:
        numberDocument(document, chapterNumber)
    index(document, outfileGenerator(os.path.split(fullpath)[1], ext),
          htmlbook.getReference(fullpath))

    authors = domhelpers.findNodesNamed(document, 'link')
    authors = [(node.getAttribute('title') or '',
                node.getAttribute('href') or '')
               for node in authors
               if node.getAttribute('rel') == 'author']
    setAuthors(template, authors)

    body = domhelpers.findNodesNamed(document, "body")[0]
    tmplbody = domhelpers.findElementsWithAttribute(template, "class",
                                                              "body")[0]
    tmplbody.childNodes = body.childNodes
    tmplbody.setAttribute("class", "content")


class _LocationReportingErrorHandler(ErrorHandler):
    """
    Define a SAX error handler which can report the location of fatal
    errors.

    Unlike the errors reported during parsing by other APIs in the xml
    package, this one tries to mismatched tag errors by including the
    location of both the relevant opening and closing tags.
    """
    def __init__(self, contentHandler):
        self.contentHandler = contentHandler

    def fatalError(self, err):
        # Unfortunately, the underlying expat error code is only exposed as
        # a string.  I surely do hope no one ever goes and localizes expat.
        if err.getMessage() == 'mismatched tag':
            expect, begLine, begCol = self.contentHandler._locationStack[-1]
            endLine, endCol = err.getLineNumber(), err.getColumnNumber()
            raise process.ProcessingFailure(
                "mismatched close tag at line %d, column %d; expected </%s> "
                "(from line %d, column %d)" % (
                    endLine, endCol, expect, begLine, begCol))
        raise process.ProcessingFailure(
            '%s at line %d, column %d' % (err.getMessage(),
                                          err.getLineNumber(),
                                          err.getColumnNumber()))


class _TagTrackingContentHandler(SAX2DOM):
    """
    Define a SAX content handler which keeps track of the start location of
    all open tags.  This information is used by the above defined error
    handler to report useful locations when a fatal error is encountered.
    """
    def __init__(self):
        SAX2DOM.__init__(self)
        self._locationStack = []

    def setDocumentLocator(self, locator):
        self._docLocator = locator
        SAX2DOM.setDocumentLocator(self, locator)

    def startElement(self, name, attrs):
        self._locationStack.append((name, self._docLocator.getLineNumber(), self._docLocator.getColumnNumber()))
        SAX2DOM.startElement(self, name, attrs)

    def endElement(self, name):
        self._locationStack.pop()
        SAX2DOM.endElement(self, name)


class _LocalEntityResolver(object):
    """
    Implement DTD loading (from a local source) for the limited number of
    DTDs which are allowed for Lore input documents.

    @ivar filename: The name of the file containing the lore input
        document.

    @ivar knownDTDs: A mapping from DTD system identifiers to L{FilePath}
        instances pointing to the corresponding DTD.
    """
    s = FilePath(__file__).sibling

    knownDTDs = {
        None: s("xhtml1-strict.dtd"),
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd": s("xhtml1-strict.dtd"),
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd": s("xhtml1-transitional.dtd"),
        "xhtml-lat1.ent": s("xhtml-lat1.ent"),
        "xhtml-symbol.ent": s("xhtml-symbol.ent"),
        "xhtml-special.ent": s("xhtml-special.ent"),
        }
    del s

    def __init__(self, filename):
        self.filename = filename


    def resolveEntity(self, publicId, systemId):
        source = InputSource()
        source.setSystemId(systemId)
        try:
            dtdPath = self.knownDTDs[systemId]
        except KeyError:
            raise process.ProcessingFailure(
                "Invalid DTD system identifier (%r) in %s.  Only "
                "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd "
                "is allowed." % (systemId, self.filename))
        source.setByteStream(dtdPath.open())
        return source



def parseFileAndReport(filename, _open=file):
    """
    Parse and return the contents of the given lore XHTML document.

    @type filename: C{str}
    @param filename: The name of a file containing a lore XHTML document to
    load.

    @raise process.ProcessingFailure: When the contents of the specified file
    cannot be parsed.

    @rtype: A DOM Document
    @return: The document contained in C{filename}.
    """
    content = _TagTrackingContentHandler()
    error = _LocationReportingErrorHandler(content)
    parser = make_parser()
    parser.setContentHandler(content)
    parser.setErrorHandler(error)

    # In order to call a method on the expat parser which will be used by this
    # parser, we need the expat parser to be created.  This doesn't happen
    # until reset is called, normally by the parser's parse method.  That's too
    # late for us, since it will then go on to parse the document without
    # letting us do any extra set up.  So, force the expat parser to be created
    # here, and then disable reset so that the parser created is the one
    # actually used to parse our document.  Resetting is only needed if more
    # than one document is going to be parsed, and that isn't the case here.
    parser.reset()
    parser.reset = lambda: None

    # This is necessary to make the xhtml1 transitional declaration optional.
    # It causes LocalEntityResolver.resolveEntity(None, None) to be called.
    # LocalEntityResolver handles that case by giving out the xhtml1
    # transitional dtd.  Unfortunately, there is no public API for manipulating
    # the expat parser when using xml.sax.  Using the private _parser attribute
    # may break.  It's also possible that make_parser will return a parser
    # which doesn't use expat, but uses some other parser.  Oh well. :(
    # -exarkun
    parser._parser.UseForeignDTD(True)
    parser.setEntityResolver(_LocalEntityResolver(filename))

    # This is probably no-op because expat is not a validating parser.  Who
    # knows though, maybe you figured out a way to not use expat.
    parser.setFeature(feature_validation, False)

    fObj = _open(filename)
    try:
        try:
            parser.parse(fObj)
        except IOError, e:
            raise process.ProcessingFailure(
                e.strerror + ", filename was '" + filename + "'")
    finally:
        fObj.close()
    return content.document


def makeSureDirectoryExists(filename):
    filename = os.path.abspath(filename)
    dirname = os.path.dirname(filename)
    if (not os.path.exists(dirname)):
        os.makedirs(dirname)

def doFile(filename, linkrel, ext, url, templ, options={}, outfileGenerator=getOutputFileName):
    """
    Process the input document at C{filename} and write an output document.

    @type filename: C{str}
    @param filename: The path to the input file which will be processed.

    @type linkrel: C{str}
    @param linkrel: An prefix to apply to all relative links in C{src} or
    C{href} attributes in the input document when generating the output
    document.

    @type ext: C{str}
    @param ext: The extension to use when selecting an output file name.  This
    replaces the extension of the input file name.

    @type url: C{str}
    @param url: A string which will be interpolated with the fully qualified
    Python name of any API reference encountered in the input document, the
    result of which will be used as a link to API documentation for that name
    in the output document.

    @type templ: A DOM Node or Document
    @param templ: The template on which the output document will be based.
    This is mutated and then serialized to the output file.

    @type options: C{dict}
    @param options: Further specification of the desired form of the output.
    Valid keys in this dictionary::

        noapi: If present and set to a True value, links to API documentation
               will not be generated.

        version: A string which will be included in the output to indicate the
                 version of this documentation.

    @type outfileGenerator: Callable of C{str}, C{str} returning C{str}
    @param outfileGenerator: Output filename factory.  This is invoked with the
    intput filename and C{ext} and the output document is serialized to the
    file with the name returned.

    @return: C{None}
    """
    doc = parseFileAndReport(filename)
    clonedNode = templ.cloneNode(1)
    munge(doc, clonedNode, linkrel, os.path.dirname(filename), filename, ext,
          url, options, outfileGenerator)
    newFilename = outfileGenerator(filename, ext)
    _writeDocument(newFilename, clonedNode)



def _writeDocument(newFilename, clonedNode):
    """
    Serialize the given node to XML into the named file.

    @param newFilename: The name of the file to which the XML will be
        written.  If this is in a directory which does not exist, the
        directory will be created.

    @param clonedNode: The root DOM node which will be serialized.

    @return: C{None}
    """
    makeSureDirectoryExists(newFilename)
    f = open(newFilename, 'w')
    f.write(clonedNode.toxml('utf-8'))
    f.close()
