# -*- test-case-name: twisted.test.test_persisted -*-
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

"""
# System Imports
import copy
from cStringIO import StringIO

# Twisted Imports
from twisted.protocols.sux import XMLParser, ParseError
from twisted.python import reflect
from twisted.python.reflect import Accessor

# Sibling imports
import html

# create NodeList class
from types import ListType as NodeList


class MismatchedTags(Exception):

    def __init__(self, filename, expect, got, endLine, endCol, begLine, begCol):
       (self.filename, self.expect, self.got, self.begLine, self.begCol, self.endLine,
        self.endCol) = filename, expect, got, begLine, begCol, endLine, endCol

    def __str__(self):
        return "expected </%s>, got </%s> line: %s col: %s, began line: %s col: %s" % (self.expect, self.got, self.endLine, self.endCol, self.begLine, self.begCol)


class Node:
    
    def __init__(self, parentNode=None):
        self.parentNode = parentNode
        self.childNodes = []
        self.nodeName = reflect.qual(self.__class__)

    def writexml(self, stream, indent='', addindent='', newl=''):
        raise NotImplementedError()

    def toxml(self, indent='', newl=''):
        s = StringIO()
        self.writexml(s, '', indent, newl)
        rv = s.getvalue()
        return rv

    def toprettyxml(self, indent='\t', newl='\n'):
        return self.toxml(indent, newl)

    def cloneNode(self, deep=0):
        if deep:
            return copy.deepcopy(self)
        else:
            return copy.copy(self)

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
        if newChild.parentNode:
            newChild.parentNode.removeChild(newChild)
        assert oldChild.parentNode is self
        self.childNodes[self.childNodes.index(oldChild)] = newChild
        oldChild.parentNode = None
        newChild.parentNode = self

    def lastChild(self):
        return self.childNodes[-1]
    
    def firstChild(self):
        if len(self.childNodes):
            return self.childNodes[0]
        return None


class Document(Node, Accessor):

    def __init__(self, documentElement=None):
        Node.__init__(self)
        if documentElement:
            self.appendChild(documentElement)

    doctype = None

    def get_documentElement(self):
        return self.childNodes[0]

    def appendChild(self, c):
        assert not self.childNodes, "Only one element per document."
        Node.appendChild(self, c)

    def writexml(self, stream, indent='', addindent='', newl=''):
        stream.write('<?xml version="1.0"?>' + newl)
        if self.doctype:
            stream.write("<!DOCTYPE "+self.doctype+">" + newl)
        self.documentElement.writexml(stream, indent, addindent, newl)

    # of dubious utility (?)
    def createElement(self, name):
        return Element(name)
    
    def createTextNode(self, text):
        return Text(text)

    def getElementsByTagName(self, name):
        childNodes = self.childNodes[:]
        gathered = []
        while childNodes:
            node = childNodes.pop(0)
            if node.childNodes:
                childNodes.extend(node.childNodes)
            if node.nodeName == name:
                gathered.append(node)
        return gathered

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

    def writexml(self, stream, indent='', addindent='', newl=''):
        stream.write(self.nodeValue)


class CharacterData(Node):

    def __init__(self, data, parentNode=None):
        Node.__init__(self, parentNode)
        self.value = self.data = self.nodeValue = data


class Text(CharacterData):

    def __init__(self, data, parentNode=None, raw=0):
        CharacterData.__init__(self, data, parentNode)
        self.raw = raw

    def writexml(self, stream, indent='', addindent='', newl=''):
        if self.raw:
            val = str(self.nodeValue)
        else:
            val = html.escape(str(self.nodeValue))
        stream.write(val)


class CDATASection(CharacterData):
    def writexml(self, stream, indent='', addindent='', newl=''):
        stream.write("<![CDATA[")
        stream.write(self.nodeValue)
        stream.write("]]>")


class _Attr(CharacterData):
    "Support class for getAttributeNode."


class Element(Node):

    def __init__(self, tagName, attributes=None, parentNode=None, filename=None, markpos=None):
        Node.__init__(self, parentNode)
        if attributes is None:
            self.attributes = {}
        else:
            self.attributes = attributes
            for k, v in self.attributes.items():
                self.attributes[k] = v.replace('&quot;', '"')
        self.nodeName = self.tagName = tagName
        self._filename = filename
        self._markpos = markpos

    def getElementsByTagName(self, name):
        return [n for n in self.childNodes if n.nodeName == name]
    
    def hasAttributes(self):
        return 1
    
    def getAttribute(self, name, default=None):
        return self.attributes.get(name, default)

    def getAttributeNode(self, name):
        return _Attr(self.getAttribute(name), self)
        
    def setAttribute(self, name, attr):
        self.attributes[name] = attr

    def removeAttribute(self, name):
        if self.attributes.has_key(name):
            del self.attributes[name]

    def hasAttribute(self, name):
        return self.attributes.has_key(name)

    def writexml(self, stream, indent='', addindent='', newl=''):
        # write beginning
        stream.write("<")
        stream.write(self.tagName)
        for attr, val in self.attributes.items():
            stream.write(" ")
            stream.write(attr)
            stream.write("=")
            stream.write('"')
            stream.write(html.escape(val))
            stream.write('"')
        if self.childNodes or self.tagName.lower() in ('a', 'li', 'div', 'span'):
            stream.write(">"+newl+addindent)
            for child in self.childNodes:
                child.writexml(stream, indent+addindent, addindent, newl)
            stream.write("</")
            stream.write(self.tagName)
            stream.write(">")
        else:
            stream.write(" />")

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
        dd[k] = html.unescape(v)
    return dd

class MicroDOMParser(XMLParser):
    def __init__(self, autoClosedTags=[]):
        # to parse output from e.g. Mozilla Composer, try
        # autoClosedTags=["meta", "br", "hr", "img"]
        self.elementstack = []
        self.documents = []
        self.autoClosedTags = autoClosedTags
        self._shouldAutoClose = ''
        self._mddoctype = None

    # parser options:
    caseInsensitive = 1

    def _getparent(self):
        if self.elementstack:
            parent = self.elementstack[-1]
        else:
            parent = None
        return parent

    def _autoclose(self):
        if self._shouldAutoClose:
            self.gotTagEnd(self._shouldAutoClose)

    def gotDoctype(self, doctype):
        self._mddoctype = doctype

    def gotTagStart(self, name, attributes):
        self._autoclose()
        parent = self._getparent()
        if self.caseInsensitive:
            name = name.lower()
        if name in self.autoClosedTags:
            self._shouldAutoClose = name
        el = Element(name, _unescapeDict(attributes), parent,
                     self.filename, self.saveMark())
        self.elementstack.append(el)
        if parent:
            parent.appendChild(el)

    def gotText(self, data):
        self._autoclose()
        parent = self._getparent()
        te = Text(data, parent)
        if parent:
            parent.appendChild(te)

    def gotEntityReference(self, entityRef):
        self._autoclose()
        parent = self._getparent()
        er = EntityReference(entityRef, parent)
        if parent:
            parent.appendChild(er)

    def gotCData(self, cdata):
        self._autoclose()
        parent = self._getparent()
        cd = CDATASection(cdata, parent)
        if parent:
            parent.appendChild(cd)

    def gotTagEnd(self, name):
        if self.caseInsensitive:
            name = name.lower()
        if self._shouldAutoClose == name:
            self._shouldAutoClose = ''
        else:
            self._autoclose()
        el = self.elementstack.pop()
        if el.tagName != name:
            raise MismatchedTags(*((self.filename, el.tagName, name)+self.saveMark()+el._markpos))
        if not self.elementstack:
            self.documents.append(el)


def parse(readable):
    if not hasattr(readable, "read"):
        readable = open(readable)
    mdp = MicroDOMParser()
    mdp.filename = getattr(readable, "name", "<xmlfile />")
    mdp.makeConnection(None)
    r = readable.read(1024)
    while r:
        mdp.dataReceived(r)
        r = readable.read(1024)
    d = mdp.documents[0]
    doc = Document(d)
    doc.doctype = mdp._mddoctype
    return doc

def parseString(st):
    mdp = MicroDOMParser()
    mdp.makeConnection(None)
    mdp.dataReceived(st)
    d = mdp.documents[0]
    doc = Document(d)
    doc.doctype = mdp._mddoctype
    return doc


