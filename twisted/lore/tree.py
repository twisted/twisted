# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import re, os, cStringIO, time, cgi, string, urlparse
from twisted import copyright
from twisted.python import htmlizer, text
from twisted.web import microdom, domhelpers
import process, latex, indexer, numberer, htmlbook
from twisted.python.util import InsensitiveDict

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
        if node.getAttribute("class", "") == "absolute":
            continue
        if node.getAttribute("class", "").find('listing') != -1:
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
        node.appendChild(microdom.Text(time.ctime(os.path.getmtime(fullpath))))



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
        node2 = microdom.Element('a', {'href': url%fullname, 'title': fullname})
        node2.childNodes = node.childNodes
        node.childNodes = [node2]
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

    @return: C{None}
    """
    oldio = cStringIO.StringIO()
    latex.getLatexText(node, oldio.write,
                       entities={'lt': '<', 'gt': '>', 'amp': '&'})
    oldio = cStringIO.StringIO(oldio.getvalue().strip()+'\n')
    newio = cStringIO.StringIO()
    htmlizer.filter(oldio, newio, writer=htmlizer.SmallerHTMLWriter)
    newio.seek(0)
    newel = microdom.parse(newio).documentElement
    newel.setAttribute("class", "python")
    node.parentNode.replaceChild(newel, node)



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
        lines = map(string.rstrip, open(os.path.join(dir, filename)).readlines())
        data = '\n'.join(lines[int(node.getAttribute('skipLines', 0)):])
        data = cStringIO.StringIO(text.removeLeadingTrailingBlanks(data))
        htmlizer.filter(data, outfile, writer=htmlizer.SmallerHTMLWriter)
        val = outfile.getvalue()
        _replaceWithListing(node, val, filename, "py-listing")



def _replaceWithListing(node, val, filename, class_):
    captionTitle = domhelpers.getNodeText(node)
    if captionTitle == os.path.basename(filename):
        captionTitle = 'Source listing'
    text = ('<div class="%s">%s<div class="caption">%s - '
            '<a href="%s"><span class="filename">%s</span></a></div></div>' %
            (class_, val, captionTitle, filename, filename))
    newnode = microdom.parseString(text).documentElement
    node.parentNode.replaceChild(newnode, node)



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
    toc, level, id = '\n<ol>\n', 0, 0
    for element in getHeaders(document):
        elementLevel = int(element.tagName[1])-2
        toc += (level-elementLevel)*'</ul>\n'
        toc += (elementLevel-level)*'<ul>'
        toc += '<li><a href="#auto%d">' % id
        toc += domhelpers.getNodeText(element)
        toc += '</a></li>\n'
        level = elementLevel
        anchor = microdom.parseString('<a name="auto%d" />' % id).documentElement
        element.childNodes.append(anchor)
        id += 1
    toc += '</ul>\n' * level
    toc += '</ol>\n'
    return microdom.parseString(toc).documentElement



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
    empty = microdom.Element('span')
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
        id += 1
    body = domhelpers.findNodesNamed(document, "body")[0]
    header = microdom.parseString('<h2>Footnotes</h2>').documentElement
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
    notePrefix = microdom.parseString('<strong>Note: </strong>').documentElement
    for note in notes:
        note.childNodes.insert(0, notePrefix)



def compareMarkPos(a, b):
    """
    Perform in every way identically to L{cmp} for valid inputs.

    XXX - replace this with L{cmp}
    """
    linecmp = cmp(a[0], b[0])
    if linecmp:
        return linecmp
    return cmp(a[1], b[1])



def comparePosition(firstElement, secondElement):
    """
    Compare the two elements given by their position in the document or
    documents they were parsed from.

    @type firstElement: C{twisted.web.microdom.Element}
    @type secondElement: C{twisted.web.microdom.Element}

    @return: C{-1}, C{0}, or C{1}, with the same meanings as the return value
    of L{cmp}.
    """
    return compareMarkPos(firstElement._markpos, secondElement._markpos)



def findNodeJustBefore(target, nodes):
    """
    Find the node in C{nodes} which appeared immediately before C{target} in
    the input document.

    @type target: L{twisted.web.microdom.Element}
    @type nodes: C{list} of L{twisted.web.microdom.Element}
    @return: An element from C{nodes}
    """
    result = None
    for node in nodes:
        if comparePosition(target, node) < 0:
            return result
        result = node
    return result



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

    @type header: A DOM Node or L{None}
    @param header: The section from which to extract a number.  The section
    number is the value of this node's first child.

    @return: C{None} or a C{str} giving the section number.
    """
    if not header:
        return None
    return header.childNodes[0].value.strip()



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
        indexer.addEntry(filename, anchor, entry.attributes['value'], ref)
        # does nodeName even affect anything?
        entry.nodeName = entry.tagName = entry.endTagName = 'a'
        entry.attributes = InsensitiveDict({'name': anchor})



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
            link.attributes = InsensitiveDict({'href': indexFilename})



def numberDocument(document, chapterNumber):
    """
    Number the sections of the given document.

    A dot-separated chapter, section number is added to the beginning of each
    section, as defined by C{h2} nodes.

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
        node.childNodes = [microdom.Text("%s.%d " % (chapterNumber, i))] + node.childNodes
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
    for nodeList in (domhelpers.findNodesNamed(template, "title"),
                     domhelpers.findElementsWithAttribute(template, "class",
                                                          'title')):
        if nodeList:
            if numberer.getNumberSections() and chapterNumber:
                nodeList[0].childNodes.append(microdom.Text('%s. ' % chapterNumber))
            nodeList[0].childNodes.extend(title)



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
    # First, similarly to setTitle, insert text into an <div class="authors">
    text = ''
    for name, href in authors:
        # FIXME: Do proper quoting/escaping (is it ok to use
        # xml.sax.saxutils.{escape,quoteattr}?)
        anchor = '<a href="%s">%s</a>' % (href, name)
        if (name, href) == authors[-1]:
            if len(authors) == 1:
                text = anchor
            else:
                text += 'and ' + anchor
        else:
            text += anchor + ','

    childNodes = microdom.parseString('<span>' + text +'</span>').childNodes

    for node in domhelpers.findElementsWithAttribute(template,
                                                     "class", 'authors'):
        node.childNodes.extend(childNodes)

    # Second, add appropriate <link rel="author" ...> tags to the <head>.
    head = domhelpers.findNodesNamed(template, 'head')[0]
    authors = [microdom.parseString('<link rel="author" href="%s" title="%s"/>'
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
        node.appendChild(microdom.Text(version))



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
    authors = [(node.getAttribute('title',''), node.getAttribute('href', ''))
               for node in authors if node.getAttribute('rel', '') == 'author']
    setAuthors(template, authors)

    body = domhelpers.findNodesNamed(document, "body")[0]
    tmplbody = domhelpers.findElementsWithAttribute(template, "class",
                                                              "body")[0]
    tmplbody.childNodes = body.childNodes
    tmplbody.setAttribute("class", "content")


def parseFileAndReport(filename):
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
    try:
        return microdom.parse(open(filename))
    except microdom.MismatchedTags, e:
        raise process.ProcessingFailure(
              "%s:%s: begin mismatched tags <%s>/</%s>" %
               (e.begLine, e.begCol, e.got, e.expect),
              "%s:%s: end mismatched tags <%s>/</%s>" %
               (e.endLine, e.endCol, e.got, e.expect))
    except microdom.ParseError, e:
        raise process.ProcessingFailure("%s:%s:%s" % (e.line, e.col, e.message))
    except IOError, e:
        raise process.ProcessingFailure(e.strerror + ", filename was '" + filename + "'")

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
    makeSureDirectoryExists(newFilename)
    f = open(newFilename, 'wb')
    clonedNode.writexml(f)
    f.close()
