# -*- test-case-name: twisted.test.test_xml -*-
#
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

"""Micro Document Object Model: a partial DOM implementation with SUX.

This is an implementation of what we consider to be the useful subset of the
DOM.  The chief advantage of this library is that, not being burdened with
standards compliance, it can remain very stable between versions.  We can also
implement utility 'pythonic' ways to access and mutate the XML tree.

Since this has not subjected to a serious trial by fire, it is not recommended
to use this outside of Twisted applications.  However, it seems to work just
fine for the documentation generator, which parses a fairly representative
sample of XML.

Microdom mainly focuses on working with HTML and XHTML.
"""

from __future__ import nested_scopes

# System Imports
import copy
from cStringIO import StringIO

# Twisted Imports
from twisted.protocols.sux import XMLParser, ParseError
from twisted.python import reflect
from twisted.python.compat import isinstance, StringTypes

# create NodeList class
from types import ListType as NodeList
from types import UnicodeType
import sys
dictsAreNotSequences=0
try:
    'x' in {}
except TypeError:
    dictsAreNotSequences = 1

def getElementsByTagName(iNode, name):
    matches = []
    matches_append = matches.append # faster lookup. don't do this at home
    slice=[iNode]
    while len(slice)>0:
        c = slice.pop(0)
        if c.nodeName == name:
            matches_append(c)
        slice[:0] = c.childNodes
    return matches

def getElementsByTagNameNoCase(iNode, name):
    name = name.lower()
    matches = []
    matches_append = matches.append
    slice=[iNode]
    while len(slice)>0:
        c = slice.pop(0)
        if c.nodeName.lower() == name:
            matches_append(c)
        slice[:0] = c.childNodes
    return matches

# order is important
ESCAPE_CHARS = (('&', '&amp;'),
                 ('<', '&lt;'),
                 ('>', '&gt;'),
                 ('"', '&quot;'))

def unescape(text):
    "Perform the exact opposite of 'escape'."
    for s, h in ESCAPE_CHARS:
        text = text.replace(h, s)
    return text

def escape(text):
    "Escape a few HTML special chars with HTML entities."
    for s, h in ESCAPE_CHARS:
        text = text.replace(s, h)
    return text

class MismatchedTags(Exception):

    def __init__(self, filename, expect, got, endLine, endCol, begLine, begCol):
       (self.filename, self.expect, self.got, self.begLine, self.begCol, self.endLine,
        self.endCol) = filename, expect, got, begLine, begCol, endLine, endCol

    def __str__(self):
        return "expected </%s>, got </%s> line: %s col: %s, began line: %s col: %s" % (self.expect, self.got, self.endLine, self.endCol, self.begLine, self.begCol)


class Node(object):
    nodeName = "Node"

    def __init__(self, parentNode=None):
        self.parentNode = parentNode
        self.childNodes = []

    def __eq__(self, n):
        if not isinstance(n, Node):
            return 0
        return self.isEqualToNode(n)

    def __hash__(self):
        return id(self)
    
    def isEqualToNode(self, n):
        for a, b in zip(self.childNodes, n.childNodes):
            if not a == b:
                return 0
        return 1

    def writexml(self, stream, indent='', addindent='', newl='', strip=0):
        raise NotImplementedError()

    def toxml(self, indent='', addindent='', newl='', strip=0):
        s = StringIO()
        self.writexml(s, indent, addindent, newl, strip)
        rv = s.getvalue()
        return rv

    def toprettyxml(self, indent='', addindent=' ', newl='\n', strip=1):
        return self.toxml(indent, addindent, newl, strip)

    def cloneNode(self, deep=0, parent=None):
        raise NotImplementedError()

    def hasChildNodes(self):
        if self.childNodes:
            return 1
        else:
            return 0
    
    def appendChild(self, child):
        assert isinstance(child, Node)
        self.childNodes.append(child)
        child.parentNode = self

    def insertBefore(self, new, ref):
        i = self.childNodes.index(ref)
        new.parentNode = self
        self.childNodes.insert(i, new)
        return new

    def removeChild(self, child):
        if child in self.childNodes:
            self.childNodes.remove(child)
            child.parentNode = None
        return child

    def replaceChild(self, newChild, oldChild):
        assert isinstance(newChild, Node)
        #if newChild.parentNode:
        #    newChild.parentNode.removeChild(newChild)
        assert oldChild.parentNode is self, 'oldChild (%s): oldChild.parentNode (%s) != self (%s)' % (oldChild, oldChild.parentNode, self)
        self.childNodes[self.childNodes.index(oldChild)] = newChild
        oldChild.parentNode = None
        newChild.parentNode = self

    def lastChild(self):
        return self.childNodes[-1]
    
    def firstChild(self):
        if len(self.childNodes):
            return self.childNodes[0]
        return None

    #def get_ownerDocument(self):
    #   """This doesn't really get the owner document; microdom nodes
    #   don't even have one necessarily.  This gets the root node,
    #   which is usually what you really meant. 
    #   *NOT DOM COMPLIANT.*
    #   """
    #   node=self
    #   while (node.parentNode): node=node.parentNode
    #   return node
    #ownerDocument=node.get_ownerDocument()
    # leaving commented for discussion; see also domhelpers.getParents(node)

class Document(Node):

    def __init__(self, documentElement=None):
        Node.__init__(self)
        if documentElement:
            self.appendChild(documentElement)

    def cloneNode(self, deep=0, parent=None):
        d = Document()
        if deep:
            newEl = self.documentElement.cloneNode(1, self)
        else:
            newEl = self.documentElement
        d.appendChild(newEl)
        return d

    doctype = None

    def __eq__(self, n):
        if not isinstance(n, Document):
            return 0
        return self.isEqualToDocument(n) and self.isEqualToNode(n)

    def isEqualToDocument(self, n):
        return (self.doctype == n.doctype)

    def get_documentElement(self):
        return self.childNodes[0]
    documentElement=property(get_documentElement)

    def appendChild(self, c):
        assert not self.childNodes, "Only one element per document."
        Node.appendChild(self, c)

    def writexml(self, stream, indent='', addindent='', newl='', strip=0):
        stream.write('<?xml version="1.0"?>' + newl)
        if self.doctype:
            stream.write("<!DOCTYPE "+self.doctype+">" + newl)
        self.documentElement.writexml(stream, indent, addindent, newl, strip)

    # of dubious utility (?)
    def createElement(self, name):
        return Element(name)
    
    def createTextNode(self, text):
        return Text(text)

    def getElementsByTagName(self, name):
        if self.documentElement.caseInsensitive:
            return getElementsByTagNameNoCase(self, name)
        return getElementsByTagName(self, name)

    def getElementById(self, id):
        childNodes = self.childNodes[:]
        while childNodes:
            node = childNodes.pop(0)
            if node.childNodes:
                childNodes.extend(node.childNodes)
            if hasattr(node, 'getAttribute') and node.getAttribute("id") == id:
                return node


class EntityReference(Node):

    def __init__(self, eref, parentNode=None):
        Node.__init__(self, parentNode)
        self.eref = eref
        self.nodeValue = self.data = "&" + eref + ";"

    def __eq__(self, n):
        return self.isEqualToEntityReference(n) and self.isEqualToNode(n)
    
    def isEqualToEntityReference(self, n):
        if not isinstance(n, EntityReference):
            return 0
        return (self.eref == n.eref) and (self.nodeValue == n.nodeValue)
        
    def writexml(self, stream, indent='', addindent='', newl='', strip=0):
        stream.write(self.nodeValue)

    def cloneNode(self, deep=0, parent=None):
        return EntityReference(self.eref, parent)


class CharacterData(Node):

    def __init__(self, data, parentNode=None):
        Node.__init__(self, parentNode)
        self.value = self.data = self.nodeValue = data

    def __eq__(self, n):
        if not isinstance(n, CharacterData):
            return 0
        return self.isEqualToCharacterData(n) and self.isEqualToNode(n)

    def isEqualToCharacterData(self, n):
        return self.value == n.value


class Comment(CharacterData):
    """A comment node."""

    def writexml(self, stream, indent='', addindent='', newl='', strip=0):
        stream.write("<!--%s-->" % self.data)

    def cloneNode(self, deep=0, parent=None):
        return Comment(self.nodeValue, parent)


class Text(CharacterData):

    def __init__(self, data, parentNode=None, raw=0):
        CharacterData.__init__(self, data, parentNode)
        self.raw = raw

    def cloneNode(self, deep=0, parent=None):
        return Text(self.nodeValue, parent, self.raw)

    def writexml(self, stream, indent='', addindent='', newl='', strip=0):
        if self.raw:
            val = self.nodeValue
            if not isinstance(val, StringTypes):
                val = str(self.nodeValue)
        else:
            v = self.nodeValue
            if not isinstance(v, StringTypes):
                v = str(v)
            if strip:
                v = ' '.join(v.split())
            val = escape(v)
            if isinstance(val, UnicodeType):
                val = val.encode('utf8')
        stream.write(val)

    def __repr__(self):
        return "Text(%s" % repr(self.nodeValue) + ')'


class CDATASection(CharacterData):
    def cloneNode(self, deep=0, parent=None):
        return CDATASection(self.nodeValue, parent)

    def writexml(self, stream, indent='', addindent='', newl='', strip=0):
        stream.write("<![CDATA[")
        stream.write(self.nodeValue)
        stream.write("]]>")


class _Attr(CharacterData):
    "Support class for getAttributeNode."

import new

class Element(Node):

    preserveCase = 0
    caseInsensitive = 1
    
    def __init__(self, tagName, attributes=None, parentNode=None, 
                        filename=None, markpos=None, 
                        caseInsensitive=1, preserveCase=0):
        Node.__init__(self, parentNode)
        self.preserveCase = preserveCase or not caseInsensitive
        self.caseInsensitive = caseInsensitive
        if not preserveCase:
            tagName = tagName.lower()
        if attributes is None:
            self.attributes = {}
        else:
            self.attributes = attributes
            for k, v in self.attributes.items():
                self.attributes[k] = v.replace('&quot;', '"')
        self.endTagName = self.nodeName = self.tagName = tagName
        self._filename = filename
        self._markpos = markpos

    def __eq__(self, n):
        if not isinstance(n, Element):
            return 0
        return self.isEqualToElement(n) and self.isEqualToNode(n)

    def endTag(self, endTagName):
        if not self.preserveCase:
            endTagName = endTagName.lower()
        self.endTagName = endTagName

    def isEqualToElement(self, n):
        if self.caseInsensitive:
            return (self.attributes == n.attributes) and (self.nodeName.lower() == n.nodeName.lower())
        return (self.attributes == n.attributes) and (self.nodeName == n.nodeName)

    def cloneNode(self, deep=0, parent=None):
        clone = Element(self.tagName, parentNode=parent)
        clone.attributes.update(self.attributes)
        if deep:
            clone.childNodes = [child.cloneNode(1, clone) for child in self.childNodes]
        else:
            clone.childNodes = []
        return clone

    def getElementsByTagName(self, name):
        if self.caseInsensitive:
            return getElementsByTagNameNoCase(self, name)
        return getElementsByTagName(self, name)
    
    def hasAttributes(self):
        return 1
    
    def getAttribute(self, name, default=None):
        return self.attributes.get(name, default)

    def getAttributeNode(self, name):
        return _Attr(self.getAttribute(name), self)
        
    def setAttribute(self, name, attr):
        self.attributes[name] = attr

    def removeAttribute(self, name):
        if name in self.attributes:
            del self.attributes[name]

    def removeAttribute_has_key(self, name):
        if self.attributes.has_key(name):
            del self.attributes[name]
            
    def hasAttribute(self, name):
        return name in self.attributes

    def hasAttribute_has_key(self, name):
        return self.attributes.has_key(name)

    if dictsAreNotSequences:
        hasAttribute = hasAttribute_has_key
        removeAttribute = removeAttribute_has_key

    def writexml(self, stream, indent='', addindent='', newl='', strip=0):
        # write beginning
        NEVERSINGLETON = ('a', 'li', 'div', 'span', 'title', 'script',
                          'textarea')
        # this should never be necessary unless people start 
        # changing .tagName on the fly(?)
        if not self.preserveCase:
            self.endTagName = self.tagName
        w = stream.write
        begin = [newl, indent, '<', self.tagName]
        bext = begin.extend
        j = ''.join
        for attr, val in self.attributes.items():
            bext((' ', attr, '="', escape(val), '"'))
        w(j(begin))
        if self.childNodes:
            w(">")
            newindent = indent + addindent
            for child in self.childNodes:
                child.writexml(stream, newindent, addindent, newl, strip)
            w(j((newl, indent, "</", self.endTagName, '>')))
        elif self.tagName.lower() in NEVERSINGLETON:
            w(j(('></', self.endTagName, '>')))
        else:
            w(" />")

    def __repr__(self):
        rep = "Element(%s" % repr(self.nodeName)
        if self.attributes:
            rep += ", attributes=%r" % (self.attributes,)
        if self._filename:
            rep += ", filename=%r" % (self._filename,)
        if self._markpos:
            rep += ", markpos=%r" % (self._markpos,)
        return rep + ')'

    def __str__(self):
        rep = "<" + self.nodeName
        if self._filename or self._markpos:
            rep += " ("
        if self._filename:
            rep += repr(self._filename)
        if self._markpos:
            rep += " line %s column %s" % self._markpos
        if self._filename or self._markpos:
            rep += ")"
        for item in self.attributes.items():
            rep += " %s=%r" % item
        if self.hasChildNodes():
            rep += " >...</%s>" % self.nodeName
        else:
            rep += " />"
        return rep

def _unescapeDict(d):
    dd = {}
    for k, v in d.items():
        dd[k] = unescape(v)
    return dd

class MicroDOMParser(XMLParser):

    # <dash> glyph: a quick scan thru the DTD says BODY, AREA, LINK, IMG, HR,
    # P, DT, DD, LI, INPUT, OPTION, THEAD, TFOOT, TBODY, COLGROUP, COL, TR, TH,
    # TD, HEAD, BASE, META, HTML all have optional closing tags
    
    soonClosers = 'area link br img hr input base meta'.split()
    laterClosers = {'p': ['p'],
                    'dt': ['dt','dd'],
                    'dd': ['dt', 'dd'],
                    'li': ['li'],
                    'tbody': ['thead', 'tfoot', 'tbody'],
                    'thead': ['thead', 'tfoot', 'tbody'],
                    'tfoot': ['thead', 'tfoot', 'tbody'],
                    'colgroup': ['colgroup'],
                    'col': ['col'],
                    'tr': ['tr'],
                    'td': ['td'],
                    'th': ['th'],
                    'head': ['body'],
                    'title': ['head', 'body'], # this looks wrong...
                    'option': ['option'],
                    }


    def __init__(self, beExtremelyLenient=0, caseInsensitive=1, preserveCase=0):
        self.elementstack = []
        self.documents = []
        self._mddoctype = None
        self.beExtremelyLenient = beExtremelyLenient
        self.caseInsensitive = caseInsensitive
        self.preserveCase = preserveCase or not caseInsensitive
        # self.indentlevel = 0

    def shouldPreserveSpace(self):
        for edx in xrange(len(self.elementstack)):
            el = self.elementstack[-edx]
            if el.tagName == 'pre' or el.getAttribute("xml:space", '') == 'preserve':
                return 1
        return 0

    def _getparent(self):
        if self.elementstack:
            return self.elementstack[-1]
        else:
            return None

    def gotDoctype(self, doctype):
        self._mddoctype = doctype

    def gotTagStart(self, name, attributes):
        # print ' '*self.indentlevel, 'start tag',name
        # self.indentlevel += 1
        parent = self._getparent()
        if (self.beExtremelyLenient and isinstance(parent, Element) and
            self.laterClosers.has_key(parent.tagName) and
            name in self.laterClosers[parent.tagName]):
            self.gotTagEnd(parent.tagName)
            parent = self._getparent()
        el = Element(name, _unescapeDict(attributes), parent,
                     self.filename, self.saveMark(), 
                     caseInsensitive=self.caseInsensitive,
                     preserveCase=self.preserveCase)
        self.elementstack.append(el)
        if parent:
            parent.appendChild(el)
        if (self.beExtremelyLenient and name in self.soonClosers):
            self.gotTagEnd(name)

    def _gotStandalone(self, factory, data):
        parent = self._getparent()
        te = factory(data, parent)
        if parent:
            parent.appendChild(te)
        elif self.beExtremelyLenient:
            self.documents.append(te)

    def gotText(self, data):
        if data.strip() or self.shouldPreserveSpace():
            self._gotStandalone(Text, data)

    def gotComment(self, data):
        self._gotStandalone(Comment, data)

    def gotEntityReference(self, entityRef):
        self._gotStandalone(EntityReference, entityRef)

    def gotCData(self, cdata):
        self._gotStandalone(CDATASection, cdata)

    def gotTagEnd(self, name):
        # print ' '*self.indentlevel, 'end tag',name
        # self.indentlevel -= 1
        if not self.elementstack:
            if self.beExtremelyLenient:
                return
            raise MismatchedTags(*((self.filename, "NOTHING", name)
                                   +self.saveMark()+(0,0)))
        el = self.elementstack.pop()
        if not (el.tagName == name or (self.caseInsensitive and el.tagName.lower() == name.lower())):
            if self.beExtremelyLenient:
                if self.elementstack:
                    lastEl = self.elementstack[0]
                    for idx in xrange(len(self.elementstack)):
                        if self.elementstack[-(idx+1)].tagName == name:
                            self.elementstack[-(idx+1)].endTag(name)
                            break
                    else:
                        # this was a garbage close tag; wait for a real one
                        self.elementstack.append(el)
                        return
                    del self.elementstack[-(idx+1):]
                    if not self.elementstack:
                        self.documents.append(lastEl)
                        return
            else:
                raise MismatchedTags(*((self.filename, el.tagName, name)
                                       +self.saveMark()+el._markpos))
        el.endTag(name)
        if not self.elementstack:
            self.documents.append(el)

    def connectionLost(self, reason):
        if self.elementstack:
            if self.beExtremelyLenient:
                self.documents.append(self.elementstack[0])
            else:
                raise MismatchedTags(*((self.filename, self.elementstack[-1],
                                        "END_OF_FILE")
                                       +self.saveMark()
                                       +self.elementstack[-1]._markpos))


def parse(readable, *args, **kwargs):
    """Parse HTML or XML readable."""
    if not hasattr(readable, "read"):
        readable = open(readable, "rb")
    mdp = MicroDOMParser(*args, **kwargs)
    mdp.filename = getattr(readable, "name", "<xmlfile />")
    mdp.makeConnection(None)
    if hasattr(readable,"getvalue"):
        mdp.dataReceived(readable.getvalue())
    else:
        r = readable.read(1024)
        while r:
            mdp.dataReceived(r)
            r = readable.read(1024)
    mdp.connectionLost(None)

    if not mdp.documents:
        raise ParseError(mdp.filename, 0, 0, "No top-level Nodes in document")
    
    if mdp.beExtremelyLenient:
        if len(mdp.documents) == 1:
            d = mdp.documents[0]
        else:
            d = None
            for el in mdp.documents:
                if isinstance(el, Element):
                    if d is not None:
                        d = None
                        break
                    d = el
            if d is None:
                d = Element("html")
                d.childNodes[:] = mdp.documents
    else:
        d = mdp.documents[0]
    doc = Document(d)
    doc.doctype = mdp._mddoctype
    return doc

def parseString(st, *args, **kw):
    if isinstance(st, UnicodeType):
        # this isn't particularly ideal, but it does work.
        return parse(StringIO(st.encode('UTF-16')), *args, **kw)
    return parse(StringIO(st), *args, **kw)


def parseXML(readable):
    """Parse an XML readable object."""
    return parse(readable, caseInsensitive=0, preserveCase=1)


def parseXMLString(st):
    """Parse an XML readable object."""
    return parseString(st, caseInsensitive=0, preserveCase=1)


# Utility

class lmx:
    """Easy creation of XML."""
    
    def __init__(self, node='div'):
        if isinstance(node, StringTypes):
            node = Element(node)
        self.node = node

    def __getattr__(self, name):
        if name[0] == '_':
            raise AttributeError("no private attrs")
        return lambda **kw: self.add(name,**kw)

    def __setitem__(self, key, val):
        self.node.setAttribute(key, val)

    def __getitem__(self, key):
        return self.node.getAttribute(key)

    def text(self, txt, raw=0):
        nn = Text(txt, raw=raw)
        self.node.appendChild(nn)
        return self

    def add(self, tagName, **kw):
        newNode = Element(tagName)
        self.node.appendChild(newNode)
        xf = lmx(newNode)
        for k, v in kw.items():
            if k[0] == '_':
                k = k[1:]
            xf[k]=v
        return xf
