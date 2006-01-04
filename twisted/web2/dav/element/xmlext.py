########################################################################
#
# File Name:            __init__.py
#
#
"""
WWW: http://4suite.com/4DOM         e-mail: support@4suite.com

Copyright (c) 2000 Fourthought Inc, USA.   All Rights Reserved.
See  http://4suite.com/COPYRIGHT  for license and copyright information
"""

"""Some Helper functions: 4DOM/PyXML-specific Extensions to the DOM,
and DOM-related utilities."""

__all__ = [ "Print", "PrettyPrint" ]

import sys,string
import re

from xml.dom import Node
from xml.dom import XML_NAMESPACE, XMLNS_NAMESPACE, DOMException

def Print(root, stream=sys.stdout, encoding='UTF-8'):
    if not hasattr(root, "nodeType"):
        return
    nss = SeekNss(root)
    visitor = PrintVisitor(stream, encoding, nsHints=nss)
    PrintWalker(visitor, root).run()
    return

def PrettyPrint(root, stream=sys.stdout, encoding='UTF-8', indent='  ',
                preserveElements=None):
    if not hasattr(root, "nodeType"):
        return
    nss_hints = SeekNss(root)
    preserveElements = preserveElements or []
    owner_doc = root.ownerDocument or root
    if hasattr(owner_doc, 'getElementsByName'):
        #We don't want to insert any whitespace into HTML inline elements
        preserveElements = preserveElements + HTML_4_TRANSITIONAL_INLINE
    visitor = PrintVisitor(stream, encoding, indent,
                                   preserveElements, nss_hints)
    PrintWalker(visitor, root).run()
    stream.write('\n')
    return

def GetAllNs(node):
    #The xml namespace is implicit
    nss = {'xml': XML_NAMESPACE}
    if node.nodeType == Node.ATTRIBUTE_NODE and node.ownerElement:
        return GetAllNs(node.ownerElement)
    if node.nodeType == Node.ELEMENT_NODE:
        if node.namespaceURI:
            nss[node.prefix] = node.namespaceURI
        for attr in node.attributes.values():
            if attr.namespaceURI == XMLNS_NAMESPACE:
                if attr.localName == 'xmlns':
                    nss[None] = attr.value
                else:
                    nss[attr.localName] = attr.value
            elif attr.namespaceURI:
                nss[attr.prefix] = attr.namespaceURI
    if node.parentNode:
        #Inner NS/Prefix mappings take precedence over outer ones
        parent_nss = GetAllNs(node.parentNode)
        parent_nss.update(nss)
        nss = parent_nss
    return nss

def SeekNss(node, nss=None):
    '''traverses the tree to seek an approximate set of defined namespaces'''
    nss = nss or {}
    for child in node.childNodes:
        if child.nodeType == Node.ELEMENT_NODE:
            if child.namespaceURI:
                nss[child.prefix] = child.namespaceURI
            for attr in child.attributes.values():
                if attr.namespaceURI == XMLNS_NAMESPACE:
                    if attr.localName == 'xmlns':
                        nss[None] = attr.value
                    else:
                        nss[attr.localName] = attr.value
                elif attr.namespaceURI:
                    nss[attr.prefix] = attr.namespaceURI
            SeekNss(child, nss)
    return nss

class PrintVisitor:
    def __init__(self, stream, encoding, indent='', plainElements=None,
                 nsHints=None, isXhtml=0, force8bit=0):
        self.stream = stream
        self.encoding = encoding
        # Namespaces
        self._namespaces = [{}]
        self._nsHints = nsHints or {}
        # PrettyPrint
        self._indent = indent
        self._depth = 0
        self._inText = 0
        self._plainElements = plainElements or []
        # HTML support
        self._html = None
        self._isXhtml = isXhtml
        self.force8bit = force8bit
        return

    def _write(self, text):
        if self.force8bit:
            obj = strobj_to_utf8str(text, self.encoding)
        else:
            obj = utf8_to_code(text, self.encoding)
        self.stream.write(obj)
        return

    def _tryIndent(self):
        if not self._inText and self._indent:
            self._write('\n' + self._indent*self._depth)
        return

    def visit(self, node):
        if self._html is None:
            # Set HTMLDocument flag here for speed
            self._html = hasattr(node.ownerDocument, 'getElementsByName')

        nodeType = node.nodeType
        if node.nodeType == Node.ELEMENT_NODE:
            return self.visitElement(node)

        elif node.nodeType == Node.ATTRIBUTE_NODE:
            return self.visitAttr(node)

        elif node.nodeType == Node.TEXT_NODE:
            return self.visitText(node)

        elif node.nodeType == Node.CDATA_SECTION_NODE:
            return self.visitCDATASection(node)

        elif node.nodeType == Node.ENTITY_REFERENCE_NODE:
            return self.visitEntityReference(node)

        elif node.nodeType == Node.ENTITY_NODE:
            return self.visitEntity(node)

        elif node.nodeType == Node.PROCESSING_INSTRUCTION_NODE:
            return self.visitProcessingInstruction(node)

        elif node.nodeType == Node.COMMENT_NODE:
            return self.visitComment(node)

        elif node.nodeType == Node.DOCUMENT_NODE:
            return self.visitDocument(node)

        elif node.nodeType == Node.DOCUMENT_TYPE_NODE:
            return self.visitDocumentType(node)

        elif node.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
            return self.visitDocumentFragment(node)

        elif node.nodeType == Node.NOTATION_NODE:
            return self.visitNotation(node)

        # It has a node type, but we don't know how to handle it
        raise Exception("Unknown node type: %s" % repr(node))

    def visitNodeList(self, node, exclude=None):
        for curr in node:
            curr is not exclude and self.visit(curr)
        return

    def visitNamedNodeMap(self, node):
        for item in node.values():
            self.visit(item)
        return

    def visitAttr(self, node):
        if node.namespaceURI == XMLNS_NAMESPACE:
            # Skip namespace declarations
            return
        self._write(' ' + node.name)
        value = node.value
        if value or not self._html:
            text = TranslateCdata(value, self.encoding)
            text, delimiter = TranslateCdataAttr(text)
            self.stream.write("=%s%s%s" % (delimiter, text, delimiter))
        return

    def visitProlog(self):
        self._write("<?xml version='1.0' encoding='%s'?>" % (
            self.encoding or 'utf-8'
            ))
        self._inText = 0
        return

    def visitDocument(self, node):
        not self._html and self.visitProlog()
        node.doctype and self.visitDocumentType(node.doctype)
        self.visitNodeList(node.childNodes, exclude=node.doctype)
        return

    def visitDocumentFragment(self, node):
        self.visitNodeList(node.childNodes)
        return

    def visitElement(self, node):
        self._namespaces.append(self._namespaces[-1].copy())
        inline = node.tagName in self._plainElements
        not inline and self._tryIndent()
        self._write('<%s' % node.tagName)
        if self._isXhtml or not self._html:
            namespaces = ''
            if self._isXhtml:
                nss = {'xml': XML_NAMESPACE, None: XHTML_NAMESPACE}
            else:
                nss = GetAllNs(node)
            if self._nsHints:
                self._nsHints.update(nss)
                nss = self._nsHints
                self._nsHints = {}
            del nss['xml']
            for prefix in nss.keys():
                if not self._namespaces[-1].has_key(prefix) or self._namespaces[-1][prefix] != nss[prefix]:
                    nsuri, delimiter = TranslateCdataAttr(nss[prefix])
                    if prefix:
                        xmlns = " xmlns:%s=%s%s%s" % (prefix, delimiter,nsuri,delimiter)
                    else:
                        xmlns = " xmlns=%s%s%s" % (delimiter,nsuri,delimiter)
                    namespaces = namespaces + xmlns

                self._namespaces[-1][prefix] = nss[prefix]
            self._write(namespaces)
        for attr in node.attributes.values():
            self.visitAttr(attr)
        if len(node.childNodes):
            self._write('>')
            self._depth = self._depth + 1
            self.visitNodeList(node.childNodes)
            self._depth = self._depth - 1
            if not self._html or (node.tagName not in HTML_FORBIDDEN_END):
                not (self._inText and inline) and self._tryIndent()
                self._write('</%s>' % node.tagName)
        elif not self._html:
            self._write('/>')
        elif node.tagName not in HTML_FORBIDDEN_END:
            self._write('></%s>' % node.tagName)
        else:
            self._write('>')
        del self._namespaces[-1]
        self._inText = 0
        return

    def visitText(self, node):
        text = node.data
        if self._indent:
            text = string.strip(text) and text
        if text:
            if self._html:
                text = TranslateHtmlCdata(text, self.encoding)
            else:
                text = TranslateCdata(text, self.encoding)
            self.stream.write(text)
            self._inText = 1
        return

    def visitDocumentType(self, doctype):
        if not doctype.systemId and not doctype.publicId: return
        self._tryIndent()
        self._write('<!DOCTYPE %s' % doctype.name)
        if doctype.systemId and '"' in doctype.systemId:
            system = "'%s'" % doctype.systemId
        else:
            system = '"%s"' % doctype.systemId
        if doctype.publicId and '"' in doctype.publicId:
            # We should probably throw an error
            # Valid characters:  <space> | <newline> | <linefeed> |
            #                    [a-zA-Z0-9] | [-'()+,./:=?;!*#@$_%]
            public = "'%s'" % doctype.publicId
        else:
            public = '"%s"' % doctype.publicId
        if doctype.publicId and doctype.systemId:
            self._write(' PUBLIC %s %s' % (public, system))
        elif doctype.systemId:
            self._write(' SYSTEM %s' % system)
        if doctype.entities or doctype.notations:
            self._write(' [')
            self._depth = self._depth + 1
            self.visitNamedNodeMap(doctype.entities)
            self.visitNamedNodeMap(doctype.notations)
            self._depth = self._depth - 1
            self._tryIndent()
            self._write(']>')
        else:
            self._write('>')
        self._inText = 0
        return

    def visitEntity(self, node):
        """Visited from a NamedNodeMap in DocumentType"""
        self._tryIndent()
        self._write('<!ENTITY %s' % (node.nodeName))
        node.publicId and self._write(' PUBLIC %s' % node.publicId)
        node.systemId and self._write(' SYSTEM %s' % node.systemId)
        node.notationName and self._write(' NDATA %s' % node.notationName)
        self._write('>')
        return

    def visitNotation(self, node):
        """Visited from a NamedNodeMap in DocumentType"""
        self._tryIndent()
        self._write('<!NOTATION %s' % node.nodeName)
        node.publicId and self._write(' PUBLIC %s' % node.publicId)
        node.systemId and self._write(' SYSTEM %s' % node.systemId)
        self._write('>')
        return

    def visitCDATASection(self, node):
        self._tryIndent()
        self._write('<![CDATA[%s]]>' % (node.data))
        self._inText = 0
        return

    def visitComment(self, node):
        self._tryIndent()
        self._write('<!--%s-->' % (node.data))
        self._inText = 0
        return

    def visitEntityReference(self, node):
        self._write('&%s;' % node.nodeName)
        self._inText = 1
        return

    def visitProcessingInstruction(self, node):
        self._tryIndent()
        self._write('<?%s %s?>' % (node.target, node.data))
        self._inText = 0
        return

class PrintWalker:
    def __init__(self, visitor, startNode):
        self.visitor = visitor
        self.start_node = startNode
        return

    def step(self):
        """There is really no step to printing.  It prints the whole thing"""
        self.visitor.visit(self.start_node)
        return

    def run(self):
        return self.step()

ILLEGAL_LOW_CHARS = '[\x01-\x08\x0B-\x0C\x0E-\x1F]'
SURROGATE_BLOCK = '[\xF0-\xF7][\x80-\xBF][\x80-\xBF][\x80-\xBF]'
ILLEGAL_HIGH_CHARS = '\xEF\xBF[\xBE\xBF]'
#Note: Prolly fuzzy on this, but it looks as if characters from the surrogate block are allowed if in scalar form, which is encoded in UTF8 the same was as in surrogate block form
XML_ILLEGAL_CHAR_PATTERN = re.compile('%s|%s'%(ILLEGAL_LOW_CHARS, ILLEGAL_HIGH_CHARS))

g_utf8TwoBytePattern = re.compile('([\xC0-\xC3])([\x80-\xBF])')
g_cdataCharPattern = re.compile('[&<]|]]>')
g_charToEntity = {
        '&': '&amp;',
        '<': '&lt;',
        ']]>': ']]&gt;',
        }

# Slightly modified to not use types.Unicode
import codecs
def utf8_to_code(text, encoding):
    encoder = codecs.lookup(encoding)[0] # encode,decode,reader,writer
    if type(text) is not unicode:
        text = unicode(text, "utf-8")
    return encoder(text)[0] # result,size
def strobj_to_utf8str(text, encoding):
    if string.upper(encoding) not in ["UTF-8", "ISO-8859-1", "LATIN-1"]:
        raise ValueError("Invalid encoding: %s"%encoding)
    encoder = codecs.lookup(encoding)[0] # encode,decode,reader,writer
    if type(text) is not unicode:
        text = unicode(text, "utf-8")
    #FIXME
    return str(encoder(text)[0])

def TranslateCdataAttr(characters):
    '''Handles normalization and some intelligence about quoting'''
    if not characters:
        return '', "'"
    if "'" in characters:
        delimiter = '"'
        new_chars = re.sub('"', '&quot;', characters)
    else:
        delimiter = "'"
        new_chars = re.sub("'", '&apos;', characters)
    #FIXME: There's more to normalization
    #Convert attribute new-lines to character entity
    # characters is possibly shorter than new_chars (no entities)
    if "\n" in characters:
        new_chars = re.sub('\n', '&#10;', new_chars)
    return new_chars, delimiter

#Note: Unicode object only for now
def TranslateCdata(characters, encoding='UTF-8', prev_chars='', markupSafe=0,
                   charsetHandler=utf8_to_code):
    """
    charsetHandler is a function that takes a string or unicode object as the
    first argument, representing the string to be procesed, and an encoding
    specifier as the second argument.  It must return a string or unicode
    object
    """
    if not characters:
        return ''
    if not markupSafe:
        if g_cdataCharPattern.search(characters):
            new_string = g_cdataCharPattern.subn(
                lambda m, d=g_charToEntity: d[m.group()],
                characters)[0]
        else:
            new_string = characters
        if prev_chars[-2:] == ']]' and characters[0] == '>':
            new_string = '&gt;' + new_string[1:]
    else:
        new_string = characters
    #Note: use decimal char entity rep because some browsers are broken
    #FIXME: This will bomb for high characters.  Should, for instance, detect
    #The UTF-8 for 0xFFFE and put out &#xFFFE;
    if XML_ILLEGAL_CHAR_PATTERN.search(new_string):
        new_string = XML_ILLEGAL_CHAR_PATTERN.subn(
            lambda m: '&#%i;' % ord(m.group()),
            new_string)[0]
    new_string = charsetHandler(new_string, encoding)
    return new_string
