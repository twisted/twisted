# -*- test-case-name: twisted.test.test_domish -*-
#
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

from __future__ import generators

import types

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

def _splitPrefix(name):
    """Internal method for splitting a prefixed Element name into its respective parts """
    ntok = name.split(":", 1)
    if len(ntok) == 2:
        return ntok
    else:
        return (None, ntok[0])

class _Serializer:
    """ Internal class which serializes an Element tree into a buffer """
    def __init__(self, prefixes = None):
        self.cio = StringIO.StringIO()
        self.prefixes = prefixes or {}
        self.prefixCounter = 0

    def getValue(self):
        return self.cio.getvalue()

    def getPrefix(self, uri):
        if not self.prefixes.has_key(uri):
            self.prefixes[uri] = "xn%d" % (self.prefixCounter)
            self.prefixCounter = self.prefixCounter + 1
        return self.prefixes[uri]

    def serialize(self, elem, closeElement = 1):
        # Optimization shortcuts
        write = self.cio.write

        # Shortcut, check to see if elem is actually a chunk o' serialized XML
        if isinstance(elem, SerializedXML):
            write(elem.encode("utf-8"))
            return

        # Shortcut, check to see if elem is actually a string (aka Cdata)
        if isinstance(elem, types.StringTypes):
            write(escapeToXml(elem).encode("utf-8")) 
            return

        # Further optimizations
        parent = elem.parent
        name = elem.name
        uri = elem.uri
        defaultUri = elem.defaultUri

        
        # Seralize element name
        if defaultUri == uri:
            if parent == None or defaultUri == parent.defaultUri:
                write("<%s" % (name))
            else:
                write("<%s xmlns='%s' " % (name, defaultUri))
        else:
            prefix = self.getPrefix(uri)
            if parent == None or elem.defaultUri == parent.defaultUri:
                write("<%s:%s xmlns:%s='%s'" % (prefix, name, prefix, uri))
            else:
               write("<%s:%s xmlns:%s='%s' xmlns='%s'" % (prefix, name, prefix, uri, defaultUri))

        # Serialize attributes
        for k,v in elem.attributes.items():
            # If the attribute name is a list, it's a qualified attribute
            if isinstance(k, types.TupleType):
                write(" %s:%s='%s'" % (self.getPrefix[k[0]], k[1], escapeToXml(v, 1)).encode("utf-8"))
            else:
                write((" %s='%s'" % ( k, escapeToXml(v, 1))).encode("utf-8"))

        # Shortcut out if this is only going to return
        # the element (i.e. no children)
        if closeElement == 0:
            write(">")
            return

        # Serialize children
        if len(elem.children) > 0:
            write(">")
            for c in elem.children:
                self.serialize(c)
            # Add closing tag
            if defaultUri == uri:
                write("</%s>" % (name))
            else:
                write("</%s:%s>" % (self.getPrefix(uri), name))
        else:
            write("/>")

class _ListSerializer:
    """ Internal class which serializes an Element tree into a buffer """
    def __init__(self, prefixes = None):
        self.writelist = []
        self.prefixes = prefixes or {}
        self.prefixCounter = 0

    def getValue(self):
        d = "".join(self.writelist)
        return d.encode("utf-8")

    def getPrefix(self, uri):
        if not self.prefixes.has_key(uri):
            self.prefixes[uri] = "xn%d" % (self.prefixCounter)
            self.prefixCounter = self.prefixCounter + 1
        return self.prefixes[uri]

    def serialize(self, elem, closeElement = 1):
        # Optimization shortcuts
        write = self.writelist.append

        # Shortcut, check to see if elem is actually a chunk o' serialized XML
        if isinstance(elem, SerializedXML):
            write(elem)
            return

        # Shortcut, check to see if elem is actually a string (aka Cdata)
        if isinstance(elem, types.StringTypes):
            write(escapeToXml(elem))
            return

        # Further optimizations
        parent = elem.parent
        name = elem.name
        uri = elem.uri
        defaultUri = elem.defaultUri
        
        # Seralize element name
        if defaultUri == uri:
            if parent == None or defaultUri == parent.defaultUri:
                write("<%s" % (name))
            else:
                write("<%s xmlns='%s' " % (name, defaultUri))
        else:
            prefix = self.getPrefix(uri)
            if parent == None or elem.defaultUri == parent.defaultUri:
                write("<%s:%s xmlns:%s='%s'" % (prefix, name, prefix, uri))
            else:
               write("<%s:%s xmlns:%s='%s' xmlns='%s'" % (prefix, name, prefix, uri, defaultUri))

        # Serialize attributes
        for k,v in elem.attributes.items():
            # If the attribute name is a list, it's a qualified attribute
            if isinstance(k, types.TupleType):
                write(" %s:%s='%s'" % (self.getPrefix[k[0]], k[1], escapeToXml(v, 1)))
            else:
                write((" %s='%s'" % ( k, escapeToXml(v, 1))))

        # Shortcut out if this is only going to return
        # the element (i.e. no children)
        if closeElement == 0:
            write(">")
            return

        # Serialize children
        if len(elem.children) > 0:
            write(">")
            for c in elem.children:
                self.serialize(c)
            # Add closing tag
            if defaultUri == uri:
                write("</%s>" % (name))
            else:
                write("</%s:%s>" % (self.getPrefix(uri), name))
        else:
            write("/>")


SerializerClass = _Serializer

def escapeToXml(text, isattrib = 0):
    """Escape text to proper XML form, per section 2.3 in the XML specification.

     @type text: L{str}
     @param text: Text to escape

     @type isattrib: L{Boolean}
     @param isattrib: Triggers escaping of characters necessary for use as attribute values
    """
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    if isattrib == 1:
        text = text.replace("'", "&apos;")
        text = text.replace("\"", "&quot;")
    return text

def unescapeFromXml(text):
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&apos;", "'")
    text = text.replace("&quot;", "\"")
    text = text.replace("&amp;", "&")
    return text

def generateOnlyKlass(list, klass):
    """ Filters items in a list by class
    """
    for n in list:
        if n.__class__ == klass:
            yield n

def generateElementsQNamed(list, name, uri):
    """ Filters Element items in a list with matching name and URI
    """
    for n in list:
        if n.__class__ == Element and n.name == name and n.uri == uri:
            yield n

def generateElementsNamed(list, name):
    """ Filters Element items in a list with matching name, regardless of URI
    """
    for n in list:
        if n.__class__ == Element and n.name == name:
            yield n


class SerializedXML(str):
    """ Marker class for pre-serialized XML in the DOM """
    pass

        
class Namespace:
    """ Convenience object for tracking namespace declarations
    """
    def __init__(self, uri):
        self._uri = uri
    def __getattr__(self, n):
        return (self._uri, n)
    def __getitem__(self, n):
        return (self._uri, n)


class Element(object):
    """Object representing a container (a.k.a. tag or element) in an HTML or XML document.

    An Element contains a series of attributes (name/value pairs),
    content (character data), and other child Element objects. When building a document
    with markup (such as HTML or XML), use this object as the starting point.

    @type uri: C{str}
    @ivar uri: URI of this Element's name

    @type defaultUri: C{str}
    @ivar defaultUri: URI this Element exists within

    @type name: C{str}
    @ivar name: Name of this Element

    @type children: C{list}
    @ivar children: List of child Elements and content

    @type parent: C{Element}
    @ivar parent: Reference to the parent Element, if any.

    @type attributes: C{dict}
    @ivar attributes: Dictionary of attributes associated with this Element.

    """
    _idCounter = 0
    def __init__(self, qname, defaultUri = None, attribs = None):
        """
        @param qname: Tuple of (uri, name)
        @param defaultUri: The default URI of the element; defaults to the URI specified in L{qname}
        @param attribs: Dictionary of attributes
        """
        self.uri, self.name = qname
        self.defaultUri = defaultUri or self.uri
        self.attributes = attribs or {}
        self.children = []
        self.parent = None

    def __getattr__(self, key):
        # Check child list for first Element with a name matching the key
        for n in self.children:
            if n.__class__ == Element and n.name == key:
                return n
            
        # Tweak the behaviour so that it's more friendly about not
        # finding elements -- we need to document this somewhere :)
        return None
            
    def __getitem__(self, key):
        return self.attributes[self._dqa(key)]

    def __delitem__(self, key):
        del self.attributes[self._dqa(key)];

    def __setitem__(self, key, value):
        self.attributes[self._dqa(key)] = value

    def __str__(self):
        """ Retrieve the first CData (content) node 
        """
        for n in self.children:
            if isinstance(n, types.StringTypes): return n
        return ""

    def _dqa(self, attr):
        """Dequalify an attribute key as needed"""
        if isinstance(attr, types.TupleType) and attr[0] == self.uri:
            return attr[1]
        else:
            return attr

    def getAttribute(self, attribname, default = None):
        """Retrieve the value of attribname, if it exists """
        return self.attributes.get(attribname, default)

    def hasAttribute(self, attrib):
        """Determine if the specified attribute exists """
        return self.attributes.has_key(self._dqa(attrib))
    
    def compareAttribute(self, attrib, value):
        """Safely compare the value of an attribute against a provided value; None-safe. """
        return self.attributes.get(self._dqa(attrib), None) == value

    def swapAttributeValues(self, left, right):
        """Swap the values of two attribute"""
        d = self.attributes
        l = d[left]
        d[left] = d[right]
        d[right] = l

    def addChild(self, node):
        """Add a child to this Element"""
        if node.__class__ == Element:
            node.parent = self
        self.children.append(node)
        return self.children[-1]

    def addContent(self, text):
        """Add some text data to this element"""
        c = self.children
        if len(c) > 0 and isinstance(c[-1], types.StringTypes):
            c[-1] = c[-1] + text
        else:
            c.append(text)
        return c[-1]

    def addElement(self, name, defaultUri = None, content = None):
        """Add a new child Element to this Element; preferred method
        """
        result = None
        if isinstance(name, type(())):
            defaultUri = defaultUri or name[0]
            self.children.append(Element(name, defaultUri))
        else:
            defaultUri = defaultUri or self.defaultUri
            self.children.append(Element((self.uri, name), defaultUri))

        result = self.children[-1]
        result.parent = self

        if content:
            result.children.append(content)

        return result

    def addRawXml(self, rawxmlstring):
        """Add a pre-serialized chunk o' XML as a child of this Element.
        """
        self.children.append(SerializedXML(rawxmlstring))

    def addUniqueId(self):
        """Add a unique (across a given Python session) id attribute to this Element"""
        self.attributes["id"] = "H_%d" % Element._idCounter
        Element._idCounter = Element._idCounter + 1

    def elements(self):
        """Iterate across all children of this Element that are Elements"""
        return generateOnlyKlass(self.children, Element)

    def toXml(self, prefixes = None, closeElement = 1):
        """Serialize this Element and all children to a string """
        s = SerializerClass(prefixes)
        s.serialize(self, closeElement)
        return s.getValue()

    def firstChildElement(self):
        for c in self.children:
            if c.__class__ == Element:
                return c
        return None


class ParserError(Exception):
    """ Exception thrown when a parsing error occurs """
    pass

def elementStream():
    """ Preferred method to construct an ElementStream

    Uses Expat-based stream if available, and falls back to Sux if necessary.
    """
    try:
        es = ExpatElementStream()
        return es
    except ImportError:
        es = SuxElementStream()
        return es

from twisted.protocols import sux
class SuxElementStream(sux.XMLParser):
    def __init__(self):
        self.connectionMade()
        self.DocumentStartEvent = None
        self.ElementEvent = None
        self.DocumentEndEvent = None
        self.currElem = None
        self.rootElem = None
        self.documentStarted = False
        self.defaultNsStack = []
        self.prefixStack = []
        self.parse = self.dataReceived

    def findUri(self, prefix):
        # Walk prefix stack backwards, looking for the uri
        # matching the specified prefix
        stack = self.prefixStack
        for i in range(-1, (len(self.prefixStack)+1) * -1, -1):
            if prefix in stack[i]:
                return stack[i][prefix]
        return None

    def gotTagStart(self, name, attributes):
        defaultUri = None
        localPrefixes = {}
        attribs = {}
        uri = None
                    
        # Pass 1 - Identify namespace decls
        for k, v in attributes.items():
            if k.startswith("xmlns"):
                x, p = _splitPrefix(k)
                if (x == None): # I.e.  default declaration
                    defaultUri = v
                else:
                    localPrefixes[p] = v
                del attributes[k]

        # Push namespace decls onto prefix stack
        self.prefixStack.append(localPrefixes)

        # Determine default namespace for this element; if there
        # is one
        if defaultUri == None and len(self.defaultNsStack) > 0:
            defaultUri = self.defaultNsStack[-1]
                
        # Fix up name
        prefix, name = _splitPrefix(name)
        if prefix == None: # This element is in the default namespace
            uri = defaultUri
        else:
            # Find the URI for the prefix
            uri = self.findUri(prefix)
        
        # Pass 2 - Fix up and escape attributes
        for k, v in attributes.items():
            p, n = _splitPrefix(k)
            if p == None:
                attribs[n] = v
            else:
                attribs[(self.findUri(p)), n] = unescapeFromXml(v)

        # Construct the actual Element object
        e = Element((uri, name), defaultUri, attribs)

        # Save current default namespace
        self.defaultNsStack.append(defaultUri)

        # Document already started
        if self.documentStarted:
            # Starting a new packet
            if self.currElem == None:
                self.currElem = e
            # Adding to existing element
            else:
                self.currElem = self.currElem.addChild(e)
        # New document
        else:
            self.rootElem = e
            self.documentStarted = True
            self.DocumentStartEvent(e)

    def gotText(self, data):
        if self.currElem != None:
            self.currElem.addContent(data)

    def gotCData(self, data):
        if self.currElem != None:
            self.currElem.addContent(data)

    def gotComment(self, data):
        # Ignore comments for the moment
        pass

    entities = { "amp" : "&",
                 "lt"  : "<",
                 "gt"  : ">",
                 "apos": "'",
                 "quot": "\"" }

    def gotEntityReference(self, entityRef):
        # If this is an entity we know about, add it as content
        # to the current element
        if entityRef in SuxElementStream.entities:
            self.currElem.addContent(SuxElementStream.entities[entityRef])

    def gotTagEnd(self, name):
        # Ensure the document hasn't already ended
        if self.rootElem == None:
            # XXX: Write more legible explanation
            raise ParserError, "Element closed after end of document."
        
        # Fix up name
        prefix, name = _splitPrefix(name)
        if prefix == None:
            uri = self.defaultNsStack[-1]
        else:
            uri = self.findUri(prefix)

        # End of document
        if self.currElem == None:
            # Ensure element name and uri matches
            if self.rootElem.name != name or self.rootElem.uri != uri:
                raise ParserError, "Mismatched root elements"
            self.DocumentEndEvent()
            self.rootElem = None

        # Other elements
        else:
            # Ensure the tag being closed matches the name of the current
            # element
            if self.currElem.name != name or self.currElem.uri != uri:
                # XXX: Write more legible explanation
                raise ParserError, "Malformed element close"

            # Pop prefix and default NS stack
            self.prefixStack.pop()
            self.defaultNsStack.pop()

            # Check for parent null parent of current elem;
            # that's the top of the stack
            if self.currElem.parent == None:
                self.ElementEvent(self.currElem)
                self.currElem = None

            # Anything else is just some element wrapping up
            else:
                self.currElem = self.currElem.parent


class ExpatElementStream:
    def __init__(self):
        import pyexpat
        self.DocumentStartEvent = None
        self.ElementEvent = None
        self.DocumentEndEvent = None
        self.parser = pyexpat.ParserCreate("UTF-8", " ")
        self.parser.StartElementHandler = self._onStartElement
        self.parser.EndElementHandler = self._onEndElement
        self.parser.CharacterDataHandler = self._onCdata
        self.parser.StartNamespaceDeclHandler = self._onStartNamespace
        self.parser.EndNamespaceDeclHandler = self._onEndNamespace
        self.currElem = None
        self.defaultNsStack = []
        self.documentStarted = 0        

    def parse(self, buffer):
        self.parser.Parse(buffer)

    def _onStartElement(self, name, attrs):
        # Generate a qname tuple from the provided name
        qname = name.split(" ")

        # Process attributes
        for k, v in attrs.items():
            if k.find(" ") != -1:
                attrs[k.split(" ")] = v
                del attrs[k]

        # Construct the new element
        e = Element(qname, self.defaultNsStack[-1], attrs)

        # Document already started
        if self.documentStarted == 1:
            if self.currElem != None:
                self.currElem.children.append(e)
                e.parent = self.currElem
            self.currElem = e

        # New document
        else:
            self.documentStarted = 1
            self.DocumentStartEvent(e)

    def _onEndElement(self, _):
        # Check for null current elem; end of doc
        if self.currElem == None:
            self.DocumentEndEvent()
            
        # Check for parent that is None; that's
        # the top of the stack
        elif self.currElem.parent == None:
            self.ElementEvent(self.currElem)
            self.currElem = None

        # Anything else is just some element in the current
        # packet wrapping up
        else:
            self.currElem = self.currElem.parent

    def _onCdata(self, data):
        if self.currElem != None:
            self.currElem.addContent(data)

    def _onStartNamespace(self, prefix, uri):
        # If this is the default namespace, put
        # it on the stack
        if prefix == None:
            self.defaultNsStack.append(uri)

    def _onEndNamespace(self, prefix):
        # Remove last element on the stack
        if prefix == None:
            self.defaultNsStack.pop()

## class FileParser(ElementStream):
##     def __init__(self):
##         ElementStream.__init__(self)
##         self.DocumentStartEvent = self.docStart
##         self.ElementEvent = self.elem
##         self.DocumentEndEvent = self.docEnd
##         self.done = 0

##     def docStart(self, elem):
##         self.document = elem

##     def elem(self, elem):
##         self.document.addChild(elem)

##     def docEnd(self):
##         self.done = 1

##     def parse(self, filename):
##         for l in open(filename).readlines():
##             self.parser.Parse(l)
##         assert self.done == 1
##         return self.document

## def parseFile(filename):
##     return FileParser().parse(filename)


