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

from twisted.protocols.sux import XMLParser
from twisted.python import reflect

import copy

class Node:
    def __init__(self, parentNode=None):
        self.parentNode = parentNode
        self.childNodes = []
        self.nodeName = reflect.qual(self.__class__)

    def writexml(self, stream, indent='', addindent='', newl=''):
        raise NotImplementedError()
    def toxml(self, indent='', newl=''):
        from cStringIO import StringIO
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
        self.childNodes.append(child)
        child.parentNode = self
    def removeChild(self, child):
        if child in self.childNodes:
            self.childNodes.remove(child)
            child.parentNode = None
        return child
    def replaceChild(self, newChild, oldChild):
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

class _tee:
    def __init__(self, f):
        self.f = f

    def write(self, data):
        import sys
        self.f.write(data)
        sys.stdout.write(data)
        sys.stdout.flush()

from twisted.python.reflect import Accessor
class Document(Node, Accessor):
    def __init__(self, documentElement=None):
        Node.__init__(self)
        if documentElement:
            self.appendChild(documentElement)

    def get_documentElement(self):
        return self.childNodes[0]

    def appendChild(self, c):
        assert not self.childNodes, "Only one element per document."
        Node.appendChild(self, c)
    def writexml(self, stream, indent='', addindent='', newl=''):
        stream.write('<?xml version="1.0"?>' + newl)
        self.documentElement.writexml(stream, indent, addindent, newl)

    # of dubious utility (?)
    def createElement(self, name):
        return Element(name)
    
    def createTextNode(self, text):
        return Text(text)

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
        self.data = self.nodeValue = data

##     def cloneNode(self, deep):
##         return self.__class__(self.data)

class Text(CharacterData):
    def writexml(self, stream, indent='', addindent='', newl=''):
        stream.write(str(self.nodeValue))

class CDATASection(CharacterData):
    def writexml(self, stream, indent='', addindent='', newl=''):
        stream.write("<![CDATA[")
        stream.write(self.nodeValue)
        stream.write("]]>")

class Element(Node):
    def __init__(self, tagName, attributes=None, parentNode=None):
        Node.__init__(self, parentNode)
        if attributes is None:
            self.attributes = {}
        else:
            self.attributes = attributes
            for k, v in self.attributes.items():
                self.attributes[k] = v.replace('&quot;', '"')
        self.nodeName = self.tagName = tagName

    def hasAttributes(self):
        return 1
    
    def getAttribute(self, name):
        return self.attributes.get(name, None)
        
    def setAttribute(self, name, attr):
        self.attributes[name] = attr

    def removeAttribute(self, name):
        if self.attributes.has_key(name):
            del self.attributes[name]

    def hasAttribute(self, name):
        return self.attributes.has_key(name)

    def appendChild(self, child):
        # should we be checking the type of the child?
        self.childNodes.append(child)

    def writexml(self, stream, indent='', addindent='', newl=''):
        # write beginning
        stream.write("<")
        stream.write(self.tagName)
        for attr, val in self.attributes.items():
            stream.write(" ")
            stream.write(attr)
            stream.write("=")
            stream.write('"')
            stream.write(val.replace('"', '&quot;'))
            stream.write('"')
        if self.childNodes:
            stream.write(">"+newl+addindent)
            for child in self.childNodes:
                child.writexml(stream, indent+addindent, addindent, newl)
            stream.write("</")
            stream.write(self.tagName)
            stream.write(">")
        else:
            stream.write("/>")
        

class MicroDOMParser(XMLParser):
    def __init__(self, autoClosedTags=[]):
        # to parse output from e.g. Mozilla Composer, try
        # autoClosedTags=["meta", "br", "hr", "img"]
        self.elementstack = []
        self.documents = []
        self.autoClosedTags = autoClosedTags
        self._shouldAutoClose = ''

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

    def gotTagStart(self, name, attributes):
        self._autoclose()
        parent = self._getparent()
        if self.caseInsensitive:
            name = name.lower()
        if name in self.autoClosedTags:
            self._shouldAutoClose = name
        el = Element(name, attributes, parent)
        el._filename = self.filename
        el._markpos = self.saveMark()
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
            raise Exception("expected </%s>, got </%s> line: %s col: %s, began line: %s col: %s" %
                            ((el.tagName, name)+self.saveMark()+el._markpos) )
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
    return Document(d)

def parseString(st):
    mdp = MicroDOMParser()
    mdp.makeConnection(None)
    mdp.dataReceived(st)
    d = mdp.documents[0]
    return Document(d)

# parseString("<!DOCTYPE suck it> <foo> testing testing, one two <bar/> </foo>").toxml()

from types import ListType as NodeList

