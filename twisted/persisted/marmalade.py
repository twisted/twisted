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

"""Marmalade: jelly, with just a hint of bitterness.

I can serialize a Python object to an XML DOM tree (xml.dom.minidom), and
therefore to XML data, similarly to twisted.spread.jelly.  Because both Python
lists and DOM trees are tree data-structures, many of the idioms used here are
identical.

"""

from twisted.python.reflect import namedModule, namedClass, namedObject

from xml.dom.minidom import Text, Element, Node, Document, parse, parseString, CDATASection

try:
    from new import instance
    from new import instancemethod
except:
    from org.python.core import PyMethod
    instancemethod = PyMethod

import types
import pickle

##### ganked straight from jelly.py

class NotKnown:
    def __init__(self):
        self.dependants = []

    def addDependant(self, mutableObject, key):
        self.dependants.append( (mutableObject, key) )

    def resolveDependants(self, newObject):
        for mut, key in self.dependants:
            mut[key] = newObject
            if isinstance(newObject, NotKnown):
                newObject.addDependant(mut, key)

    def __hash__(self):
        assert 0, "I am not to be used as a dictionary key."


class _Tuple(NotKnown):
    def __init__(self, l):
        NotKnown.__init__(self)
        self.l = l
        self.locs = []
        for idx in xrange(len(l)):
            if isinstance(l[idx], NotKnown):
                self.locs.append(idx)
                l[idx].addDependant(self, idx)

    def __setitem__(self, n, obj):
        self.l[n] = obj
        if not isinstance(obj, NotKnown):
            self.locs.remove(n)
            if not self.locs:
                self.resolveDependants(tuple(self.l))

class _DictKeyAndValue:
    def __init__(self, dict):
        self.dict = dict
    def __setitem__(self, n, obj):
        if n not in (1, 0):
            raise AssertionError("DictKeyAndValue should only ever be called with 0 or 1")
        if n: # value
            self.value = obj
        else:
            self.key = obj
        if hasattr(self, "key") and hasattr(self, "value"):
            self.dict[self.key] = self.value


class _Dereference(NotKnown):
    def __init__(self, id):
        NotKnown.__init__(self)
        self.id = id


##### end gankage


def getValueElement(node):
    valueNode = None
    for subnode in node.childNodes:
        if isinstance(subnode, Element):
            if valueNode is None:
                valueNode = subnode
            else:
                raise "Only one value node allowed per instance!"
    return valueNode


class DOMUnjellier:
    def __init__(self):
        self.references = {}

    def unjellyInto(self, obj, loc, node):
        o = self.unjellyNode(node)
        if isinstance(o, NotKnown):
            o.addDependant(obj, loc)
        obj[loc] = o
        return o
        
    def unjellyNode(self, node):
        if node.tagName == "None":
            retval = None
        elif node.tagName == "string":
            retval = str(node.getAttribute("value").replace("\\n", "\n").replace("\\t", "\t"))
        elif node.tagName == "int":
            retval = int(node.getAttribute("value"))
        elif node.tagName == "float":
            retval = float(node.getAttribute("value"))
        elif node.tagName == "longint":
            retval = long(node.getAttribute("value"))
        elif node.tagName == "module":
            retval = namedModule(str(node.getAttribute("name")))
        elif node.tagName == "class":
            retval = namedClass(str(node.getAttribute("name")))
        elif node.tagName == "unicode":
            retval = unicode(str(node.getAttribute("value")).replace("\\n", "\n").replace("\\t", "\t"), "raw_unicode_escape")
        elif node.tagName == "function":
            retval = namedObject(str(node.getAttribute("name")))
        elif node.tagName == "method":
            im_name = node.getAttribute("name")
            im_class = namedClass(node.getAttribute("class"))
            im_self = self.unjellyNode(getValueElement(node))
            if im_class.__dict__.has_key(im_name):
                if im_self is None:
                    retval = getattr(im_class, im_name)
                else:
                    retval = instancemethod(im_class.__dict__[im_name],
                                            im_self,
                                            im_class)
            else:
                raise "instance method changed"
        elif node.tagName == "tuple":
            l = []
            tupFunc = tuple
            for subnode in node.childNodes:
                if isinstance(subnode, Element):
                    l.append(None)
                    if isinstance(self.unjellyInto(l, len(l)-1, subnode), NotKnown):
                        tupFunc = _Tuple
            retval = tupFunc(l)
        elif node.tagName == "list":
            l = []
            finished = 1
            for subnode in node.childNodes:
                if isinstance(subnode, Element):
                    l.append(None)
                    self.unjellyInto(l, len(l)-1, subnode)
            retval = l
        elif node.tagName == "dictionary":
            d = {}
            keyMode = 1
            for subnode in node.childNodes:
                if isinstance(subnode, Element):
                    if keyMode:
                        kvd = _DictKeyAndValue(d)
                        if not subnode.getAttribute("role") == "key":
                            raise "Unjellying Error: key role not set" 
                        self.unjellyInto(kvd, 0, subnode)
                    else:
                        self.unjellyInto(kvd, 1, subnode)
                    keyMode = not keyMode
            retval = d
        elif node.tagName == "instance":
            # XXX TODO: fromNode or similar
            className = node.getAttribute("class")
            clasz = namedClass(className)
            state = self.unjellyNode(getValueElement(node))
            if hasattr(clasz, "__setstate__"):
                inst = instance(clasz, {})
                inst.__setstate__(state)
            else:
                inst = instance(clasz, state)
            retval = inst
        elif node.tagName == "reference":
            refkey = node.getAttribute("key")
            retval = self.references.get(refkey)
            if retval is None:
                der = _Dereference(refkey)
                self.references[refkey] = der
                retval = der
        else:
            raise "Unsupported Node Type: %s" % str(node.tagName)
        if node.hasAttribute("reference"):
            refkey = node.getAttribute("reference")
            ref = self.references.get(refkey)
            if ref is None:
                self.references[refkey] = retval
            elif isinstance(ref, NotKnown):
                ref.resolveDependants(retval)
                self.references[refkey] = retval
            else:
                assert 0, "Multiple references with the same ID!"
        return retval

    def unjelly(self, doc):
        return self.unjellyNode(doc.childNodes[0])


class DOMJellier:
    def __init__(self):
        # dict of {id(obj): (obj, node)}
        self.prepared = {}
        self.document = Document()
        self._ref_id = 0

    def prepareElement(self, element, object):
        self.prepared[id(object)] = (object, element)

    def jellyToNode(self, obj):
        """Create a node representing the given object and return it.
        """
        objType = type(obj)
        if objType is types.NoneType:
            node = Element("None")
        elif objType is types.StringType:
            node = Element("string")
            node.setAttribute("value", obj.replace("\n", "\\n").replace("\t", "\\t"))
            # node.appendChild(CDATASection(obj))
        elif objType is types.IntType:
            node = Element("int")
            node.setAttribute("value", str(obj))
        elif objType is types.LongType:
            node = Element("longint")
            s = str(obj)
            if s[-1] == 'L':
                s = s[:-1]
            node.setAttribute("value", s)
        elif objType is types.FloatType:
            node = Element("float")
            node.setAttribute("value", repr(obj))
        elif objType is types.MethodType:
            node = Element("method")
            node.setAttribute("name", obj.im_func.__name__)
            node.setAttribute("class", str(obj.im_class))
            # TODO: make methods 'prefer' not to jelly the object internally,
            # so that the object will show up where it's referenced first NOT
            # by a method.
            node.appendChild(self.jellyToNode(obj.im_self))
        elif objType is types.ModuleType:
            node = Element("module")
            node.setAttribute("name", obj.__name__)
        elif objType is types.ClassType:
            node = Element("class")
            node.setAttribute("name", str(obj))
        elif objType is types.UnicodeType:
            node = Element("unicode")
            obj = obj.encode('raw_unicode_escape')
            s = obj.replace("\n", "\\n").replace("\t", "\\t")
            node.setAttribute("value", s)
        elif objType is types.FunctionType:
            node = Element("function")
            node.setAttribute("name", str(pickle.whichmodule(obj, obj.__name__)) + '.' + obj.__name__)
        else:
            if self.prepared.has_key(id(obj)):
                oldNode = self.prepared[id(obj)][1]
                if oldNode.hasAttribute("reference"):
                    # it's been referenced already
                    key = oldNode.getAttribute("reference")
                else:
                    # it hasn't been referenced yet
                    self._ref_id = self._ref_id + 1
                    key = str(self._ref_id)
                    oldNode.setAttribute("reference", key)
                node = Element("reference")
                node.setAttribute("key", key)
                return node
            node = Element("UNNAMED")
            self.prepareElement(node, obj)
            if objType is types.ListType:
                node.tagName = "list"
                for subobj in obj:
                    node.appendChild(self.jellyToNode(subobj))
            elif objType is types.TupleType:
                node.tagName = "tuple"
                for subobj in obj:
                    node.appendChild(self.jellyToNode(subobj))
            elif objType is types.DictionaryType:
                node.tagName = "dictionary"
                for k, v in obj.items():
                    n = self.jellyToNode(k)
                    n.setAttribute("role", "key")
                    n2 = self.jellyToNode(v)
                    node.appendChild(n)
                    node.appendChild(n2)
            elif objType is types.InstanceType:
                className = str(obj.__class__)
                node.tagName = "instance"
                node.setAttribute("class", className)
                # XXX TODO: obj.mutateNode or similar
                if hasattr(obj, "__getstate__"):
                    state = obj.__getstate__()
                else:
                    state = obj.__dict__
                n = self.jellyToNode(state)
                node.appendChild(n)
            else:
                raise "Unsupported type: %s" % objType.__name__
        return node

    def jelly(self, obj):
        """Create a document representing the current object, and return it.
        """
        node = self.jellyToNode(obj)
        self.document.appendChild(node)
        return self.document

import sys

def jellyToDOM(object):
    """Convert an Object into an xml.dom.minidom.Document.
    """
    dj = DOMJellier()
    document = dj.jelly(object)
    return document

def unjellyFromDOM(document):
    """Convert an xml.dom.minidom.Document into a Python object.
    """
    du = DOMUnjellier()
    return du.unjelly(document)

def jellyToXML(object, file=None):
    """jellyToXML(object, [file]) -> None | string

    Converts a Python object to an XML stream.  If you pass a file, the XML
    will be written to that file; otherwise, a string of the XML will be
    returned.
    """
    document = jellyToDOM(object)
    if file:
        document.writexml(file, "", "  ", "\n")
    else:
        return document.toprettyxml("  ", "\n")

def unjellyFromXML(stringOrFile):
    """I convert a string or the contents of an XML file into a Python object.
    """
    if hasattr(stringOrFile, "read"):
        document = parse(stringOrFile)
    else:
        document = parseString(stringOrFile)
    return unjellyFromDOM(document)

