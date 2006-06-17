##
# Copyright (c) 2005 Apple Computer, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# DRI: Wilfredo Sanchez, wsanchez@apple.com
##

"""
WebDAV XML parsing.

This module provides XML utilities for use with WebDAV.

See RFC 2518: http://www.ietf.org/rfc/rfc2518.txt (WebDAV)
"""

__all__ = [
    "registerElements",
    "WebDAVContentHandler",
    "WebDAVDocument",
]

import StringIO
import xml.dom.minidom
import xml.sax

from twisted.web2.dav.element.base import *
from twisted.web2.dav.element.util import PrintXML, encodeXMLName

##
# Parsing
##

def registerElements(module):
    """
    Register XML elements defined in the given module with the parser.
    """
    element_names = []

    for element_class_name in dir(module):
        element_class = getattr(module, element_class_name)

        if type(element_class) is type and issubclass(element_class, WebDAVElement):
            if element_class.namespace is None: continue
            if element_class.name is None: continue
            if element_class.unregistered: continue

            qname = element_class.namespace, element_class.name

            if qname in elements_by_tag_name:
                raise AssertionError(
                    "Attempting to register qname %s multiple times: (%r, %r)"
                    % (qname, elements_by_tag_name[qname], element_class)
                )

            if not (qname in elements_by_tag_name and issubclass(element_class, elements_by_tag_name[qname])):
                elements_by_tag_name[qname] = element_class
                element_names.append(element_class.__name__)

    return element_names

def lookupElement(qname):
    """
    Return the element class for the element with the given qname.
    """
    return elements_by_tag_name[qname]

elements_by_tag_name = {}

class WebDAVContentHandler (xml.sax.handler.ContentHandler):
    def setDocumentLocator(self, locator): self.locator = locator
    locator = None

    def location(self):
        return "line %d, column %d" % (self.locator.getLineNumber(), self.locator.getColumnNumber())

    def startDocument(self):
        self.stack = [{
            "name"       : None,
            "class"      : None,
            "attributes" : None,
            "children"   : [],
        }]

    def endDocument(self):
        top = self.stack[-1]

        assert top["name"] is None
        assert top["class"] is None
        assert top["attributes"] is None
        assert len(top["children"]) is 1, "Must have exactly one root element, got %d" % len(top["children"])

        self.dom = WebDAVDocument(top["children"][0])

    def startElementNS(self, name, qname, attributes):
        attributes_dict = {}

        if attributes.getLength() is not 0:
            for attr_name in attributes.getNames():
                attributes_dict[encodeXMLName(attr_name)] = attributes.getValue(attr_name)

        tag_namespace, tag_name = name

        if (name not in elements_by_tag_name):
            class UnknownElement (WebDAVUnknownElement):
                namespace = tag_namespace
                name      = tag_name
            element_class = UnknownElement
        else:
            element_class = elements_by_tag_name[name]

        self.stack.append({
            "name"       : name,
            "class"      : element_class,
            "attributes" : attributes_dict,
            "children"   : [],
        })

    def endElementNS(self, name, qname):
        # Pop the current element from the stack...
        top = self.stack[-1]
        del(self.stack[-1])

        assert top["name"] == name, "Last item on stack is %s while closing %s" % (top["name"], name)

        # ...then instantiate the element and add it to the parent's list of
        # children.
        try:
            element = top["class"](*top["children"], **top["attributes"])
        except ValueError, e:
            e.args = ("%s at %s" % (e.args[0], self.location()),) + e.args[1:]
            raise # Re-raises modified e, but preserves traceback

        self.stack[-1]["children"].append(element)

    def characters(self, content):
        self.stack[-1]["children"].append(PCDATAElement(content))

    def ignorableWhitespace(self, whitespace):
        self.characters(self, whitespace)

    def startElement(self, name, attributes):
        raise AssertionError("startElement() should not be called by namespace-aware parser")

    def endElement(self, name):
        raise AssertionError("endElement() should not be called by namespace-aware parser")

    def processingInstruction(self, target, data):
        raise AssertionError("processing instructions are not allowed")

    def skippedEntity(self, name):
        raise AssertionError("skipped entities are not allowed")

class WebDAVDocument (object):
    """
    WebDAV XML document.
    """
    def _parse(source_is_string):
        def parse(source):
            handler = WebDAVContentHandler()
            parser  = xml.sax.make_parser()

            parser.setContentHandler(handler)
            parser.setFeature(xml.sax.handler.feature_namespaces, True)

            if source_is_string: source = StringIO.StringIO(source)

            try:
                parser.parse(source)
            except xml.sax.SAXParseException, e:
                raise ValueError(e)

            return handler.dom

        return parse
        
    fromStream = staticmethod(_parse(False))
    fromString = staticmethod(_parse(True ))

    def __init__(self, root_element):
        """
        root_element must be a WebDAVElement instance.
        """
        super(WebDAVDocument, self).__init__()

        if not isinstance(root_element, WebDAVElement):
            raise ValueError("Not a WebDAVElement: %r" % (obj,))

        self.root_element = root_element

    def __str__(self):
        output = StringIO.StringIO()
        self.writeXML(output)
        return output.getvalue()

    def __eq__(self, other):
        if isinstance(other, WebDAVDocument):
            return self.root_element == other.root_element
        else:
            return NotImplemented

    def writeXML(self, output):
        document = xml.dom.minidom.Document()
        self.root_element.addToDOM(document, None)
        PrintXML(document, stream=output)

    def toxml(self):
        output = StringIO.StringIO()
        self.writeXML(output)
        return output.getvalue()
