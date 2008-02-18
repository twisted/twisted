# -*- test-case-name: twisted.lore.test.test_lore -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for multi-document indexes and tables of content.
"""

import re

from twisted.web import microdom, domhelpers

wxopts = {'newl':'\n', 'addindent':'  '}

def _stripTag(tag, text):
    """
    Strip all opening and closing instances of a tag from a string.

    @type tag: C{str}; an HTML tag name e.g. C{em}
    @param tag: The name of the tag to remove

    @type text: C{str}
    @param text: The original text; not modified

    @rtype: C{str}
    @return: a copy of C{text} with all instances of the tag C{tag}
        removed
    """
    return text.replace('<'+tag+'>', '').replace('</'+tag+'>', '')


def sortingKeyed(original):
    """
    Return a pair consisting of the C{original} text, preceded
    by the text as transformed into a sorting key: lowercased,
    with any initial <em> tag stripped (along with its close).

    @type original: C{str}
    @param original: the original text

    @rtype: C{tuple}: (C{str}, C{str})
    @return: a tuple containing the key to use when sorting the
      original text, followed by the original text itself
    """
    key = original.lower()
    if key.startswith('<em>'):
        key = _stripTag('em', key)
    return (key, original)


def _fixEm(text): # could use a direct test
    """
    Take flat text string, possibly with C{<em>} open and close tags,
    and turn it into a C{span} with C{em Element}s and C{Text} nodes

    @type text: C{str}
    @param text: a text string, possibly containing C{<em>} open and close tags

    @rtype: L{Element<twisted.microdom.Element>}
    @return: a C{span} C{Element} with the appropriate C{Text} and
        C{Element} C{<em>} child nodes, plus a trailing C{Text} node
        containing ': '
    """
    node = microdom.Element('span')

    inEm = 0
    for chunk in re.split('</?em>', text):
        if inEm:
            emNode = microdom.Element('em')
            emNode.appendChild(microdom.Text(chunk))
            node.appendChild(emNode)
        else:
            if len(chunk) > 0:
                node.appendChild(microdom.Text(chunk))
        inEm = not inEm

    node.appendChild(microdom.Text(': '))
    return node


def _toTree(html):
    """
    return microdom.parseString(html).documentElement
    """
    return microdom.parseString(html).documentElement


def getTemplateFilenameOrDefault(templateFile):
    """
    Return the given C{templateFile} or, if it is None,
    the default value from C{htmlDefault}.

    @type templateFile: C{str}
    @param templateFile: filename of the template file

    @rtype: C{str}
    @return: filename to use for the template file
    """
    if templateFile == None:
        from default import htmlDefault
        templateFile = htmlDefault['template']
    return templateFile


def getTemplate(templateFile=None):
    """
    Return the document and body-div of the given templateFile
    This function may raise any exception which L{microdom.parseString} might
    raise.

    @type templateFile: C{str}; a filename or None
    @param templateFile: the name of the template file, or None to use the
        default

    @rtype: C{tuple} of L{Document<twisted.web.microdom.Document>}
        and C{Element<twisted.web.microdom.Element>}
    @return: the tuple (document, body), where:
        C{document} is the template file as parsed by L{microdom<twisted.web.microdom>}
        C{body} is the first div with C{class=body} in C{document}'s C{body} element
        (I{not} the entire body element!)
    """
    templateFile = getTemplateFilenameOrDefault(templateFile)

    fp = open(templateFile)
    document = microdom.parse(fp)

    body = domhelpers.findNodesNamed(document, "body")[0]
    body = domhelpers.findElementsWithAttribute(body, "class", "body")[0] # div "body" inside usual body

    return document, body


def _dumpNode(node):
    """
    Internal function to help with debugging.
    """
    atts = [a for a in dir(node) if not a.startswith('__')]
    #['nodeName', '_filename', '_markpos', 'tagName', 'endTagName',
    # 'parentNode', 'attributes', 'caseInsensitive', 'preserveCase',
    # 'namespace', 'nsprefixes', 'childNodes']
    for a in atts:
        print a, ':', node.__getattribute__(a)


class Indexer(object):
    """
    Represents a book-style index across multiple files (chapters).
    """

    def __init__(self): # untested
        """
        Create an instance of C{Indexer} with no entries and a default filename
        """
        self.indexFilename = 'index.xhtml' # wtf? why xhtml?
        self.clearEntries()


    def setIndexFilename(self, filename='index.xhtml'):
        """
        Set the index filename to C{filename}

        @type filename: C{str}
        @param filename: the new index filename
        """
        self.indexFilename = filename


    def getIndexFilename(self):
        """
        Return the index filename

        @rtype: C{str}
        @return: the index filename
        """
        return self.indexFilename


    def addEntry(self, filename, anchor, text, reference):
        """
        Add an entry to the index.
        Adding an entry with the same C{text} as an existing entry
        adds the given information to the existing entry, rather than
        replacing the existing entry.

        @type filename: C{str}; a filename
        @param filename: the filename where C{text} occurred

        @type anchor: C{str}; an HTML anchor name
        @param anchor: the anchor in C{filename} where C{text} occurred

        @type text: C{str}
        @param text: the text that the entry refers to

        @type reference: C{str}; a dotted chapter and section
        @param reference: the short chapter/section reference text to be
          displayed in the index
        """
        if not self.entries.has_key(text):
            self.entries[text] = []
        self.entries[text].append((filename, anchor, reference))


    def clearEntries(self):
        """
        Delete all entries from the index.
        """
        self.entries = {}


    def toDocument(self):
        """
        Return a Lore input document representing the contents of this index.
        """
        document = microdom.Document()
        document.appendChild(document.createElement('html'))

        head = document.createElement('head')
        title = document.createElement('title')
        text = document.createTextNode('Index')
        title.appendChild(text)
        head.appendChild(title)
        document.documentElement.appendChild(head)

        body = document.createElement('body')

        heading = document.createElement('h1')
        text = document.createTextNode('Index')
        heading.appendChild(text)
        body.appendChild(heading)

        body.appendChild(self.generateIndexBody())
        document.documentElement.appendChild(body)
        return document


    def generateIndex(self, setTitle, templateFile=None):
        """
        Generate a book-style index and write it to the file
        C{self.indexFilename}.  The index will be in a new DIV with class=body
        inside a new document based on C{templateFile}.
        If C{self.indexFilename} is any C{False} value, skip generating
        the index and return "SKIPPED".

        @type templateFile: C{str}; a filename
        @param templateFile: the file containing the template for the index
        """
        if not self.indexFilename:
            return 'SKIPPED'
        document, bodydiv = getTemplate(templateFile)
        setTitle(document, [microdom.Text('Index')], None)
        newbodydiv = self.generateIndexBody()
        bodydiv.parentNode.replaceChild(newbodydiv, bodydiv)
        #TODO newFilename = outfileGenerator(filename, ext)
        #makeSureDirectoryExists(self.indexFilename)
        document.writexml(open(self.indexFilename, 'wb'), **wxopts)


    def generateIndexBody(self):
        """
        Generate a book-style index and return it in a new DIV Element
        with class=body.  Index entries will be grouped by the first
        letter of their text, unless it is non-alphanumeric, in which
        case the entry is grouped under "Symbol".  Entries are followed
        by links to their occurrences; the text of the links is the
        short reference string provided to addEntry().

        @rtype: C{microdom.Element}
        @return: the index, as a new DIV C{Element} with class=body

        """
        body = microdom.Element('div', {'class': 'body'})
        sortedEntryKeys = [sortingKeyed(e) for e in self.entries]
        sortedEntryKeys.sort()

        prevInitial = None
        for key, text in sortedEntryKeys:
            initial = key[0].upper()
            if not initial.isalnum():
                initial = 'Symbols'
            if initial != prevInitial:
                #body.appendChild(microdom.Text('\n\n'))
                header = _toTree('<h2>%s</h2>' % initial)
                body.appendChild(header)
                prevInitial = initial
            children = self.generateIndexEntry(text)
            for c in children:
                body.appendChild(c) # tests don't distinguish this from body.childNodes.append(c)

        return body


    def generateIndexEntry(self, text):
        """
        Generate the index entry for the given C{text}, which is a list of
        C{microdom.Node} objects that constitute what will be displayed
        in the index.

        @type text: C{str}
        @param text: the text to generate an index entry for;
          The character "!" in C{text} is converted to ", ".

        @rtype: C{list} of C{microdom.Node}
        @return: a list of Nodes; the first is the text indexed, followed
          by links for each of its occurrences, pointing to anchors in files,
          with the link text chapter and section numbers.
        """
        nodes = []
        refs = []
        if '<em>' in text:
            keyText = _fixEm(text.replace('!', ', '))
        else:
            keyText = microdom.Text('\n' + text.replace('!', ', ') + ': ')
        nodes.append(keyText)
        for (file, anchor, reference) in self.entries[text]:
            link = microdom.Element('a', {'href': file + '#' + anchor})
            link.appendChild(microdom.Text(reference))
            refs.append(link)
        if text == 'infinite recursion':
            refs.append(_toTree('<span><em>See Also:</em> recursion, infinite\n</span>'))
        if text == 'recursion!infinite':
            refs.append(_toTree('<span><em>See Also:</em> infinite recursion\n</span>'))
        for r in refs[:-1]:
            nodes.append(r)
            nodes.append(microdom.Text(', '))
        nodes.append(refs[-1])
        nodes.append(microdom.Element('br'))
        return nodes



class TocEntry(object):
    """
    Represents a single chapter\'s ToC in the whole-book ToC.
    """
    def __init__(self, tree, title, outfile, reference):
        """
        Construct a TocEntry instance.

        @type tree: A DOM Node
        @param tree: a Node containing a table of contents based on the
          headers of the chapter.

        @type title: C{str}
        @param title: the title of the chapter

        @type outfile: C{str}
        @param outfile: the output filename of the chapter

        @type reference: C{str}
        @param reference: the short reference for the chapter, e.g. "3"
        """
        self.tree = tree
        self.title = title
        self.outfile = outfile
        self.reference = reference


class TableOfContents(object):
    """
    Represents a book-style table of contents across multiple files
    (chapters).
    """

    def __init__(self):
        """
        Initialize a new, empty TableOfContents
        """
        self.clearTableOfContents()

    def clearTableOfContents(self):
        """
        Delete all entries from the table of contents.
        """
        self.toc = []

    def addChapterTableOfContents(self, tree, title, outfile, reference):
        """
        Add a chapter\'s ToC to the whole-book ToC.

        @type tree: A DOM Node
        @param tree: a Node containing a table of contents based on the
          headers of the given chapter.

        @type title: C{str}
        @param title: the title of the chapter

        @type outfile: C{str}
        @param outfile: the output filename of the chapter

        @type reference: C{str}
        @param reference: the short reference for the chapter, e.g. "6"
        """
        self.toc.append(TocEntry(tree, title, outfile, reference))


    _baseDocument = microdom.Document()
    _baseDocument.appendChild(_baseDocument.createElement('html'))

    head = _baseDocument.createElement('head')
    title = _baseDocument.createElement('title')
    text = _baseDocument.createTextNode('Table of Contents')
    title.appendChild(text)
    head.appendChild(title)
    _baseDocument.documentElement.appendChild(head)

    body = _baseDocument.createElement('body')

    heading = _baseDocument.createElement('h1')
    text = _baseDocument.createTextNode('Table of Contents')
    heading.appendChild(text)
    body.appendChild(heading)
    _baseDocument.documentElement.appendChild(body)

    del head, title, text, body, heading

    def toDocument(self):
        """
        Return a Lore input document which represents the contents of this
        table.
        """
        document = self._baseDocument.cloneNode(True)
        [body] = domhelpers.findElements(
            document, lambda node: node.tagName == 'body')
        body.appendChild(self.generateTableOfContentsBody())
        return document


    def generateTableOfContents(self, setTitle, setIndexLink, indexFilename, templateFile=None):
        """
        Generate a book-style table of contents.

        @type templateFile: C{str}; a filename
        @param templateFile: the file containing the template to base
          the table of contents on
        """
        document, body = getTemplate(templateFile)
        setTitle(document, [microdom.Text('Table of Contents')], None)
        for t in self.toc:
            chapterNode = _toTree('<span>%s. </span>' % t.reference)
            linkNode = _toTree('<a href="%s"></a>' % t.outfile)
            for titlePart in t.title:
                linkNode.appendChild(titlePart)
            chapterNode.appendChild(linkNode)
            body.appendChild(chapterNode)
            # Replace bare anchors with filename + anchor
            for anc in domhelpers.findNodesNamed(t.tree, 'a'):
                anc.attributes['href'] = t.outfile + anc.attributes['href']
            body.appendChild(t.tree)
            setIndexLink(document, indexFilename)
        document.writexml(open('toc.html', 'wb'), **wxopts) # Fix filename


    def generateTableOfContentsBody(self):
        """
        Return the body node for a table of contents document.
        """
        body = microdom.Element('div', {'class': 'body'})
        for t in self.toc:
            chapterNode = microdom.Element('span')
            chapterNode.appendChild(microdom.Text(t.reference))
            linkNode = microdom.Element('a', {'href': t.outfile})
            for titlePart in t.title:
                linkNode.appendChild(microdom.Text(titlePart))
            chapterNode.appendChild(linkNode)
            body.appendChild(chapterNode)
            # Replace bare anchors with filename + anchor
            for anc in domhelpers.findNodesNamed(t.tree, 'a'):
                anc.attributes['href'] = t.outfile + anc.attributes['href']
            body.appendChild(t.tree)
        return body
