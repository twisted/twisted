# -*- test-case-name: twisted.test.test_persisted -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Marmalade: jelly, with just a hint of bitterness.

I can serialize a Python object to an XML DOM tree (twisted.web.microdom), and
therefore to XML data, similarly to twisted.spread.jelly.  Because both Python
lists and DOM trees are tree data-structures, many of the idioms used here are
identical.

"""

import warnings
warnings.warn("twisted.persisted.marmalade is deprecated", DeprecationWarning, stacklevel=2)

import new

from twisted.python.reflect import namedModule, namedClass, namedObject, fullFuncName, qual
from twisted.persisted.crefutil import NotKnown, _Tuple, _InstanceMethod, _DictKeyAndValue, _Dereference, _Defer

try:
    from new import instancemethod
except:
    from org.python.core import PyMethod
    instancemethod = PyMethod

import types
import copy_reg

#for some reason, __builtins__ == __builtin__.__dict__ in the context where this is used.
#Can someone tell me why?
import __builtin__ 


def instance(klass, d):
    if isinstance(klass, types.ClassType):
        return new.instance(klass, d)
    elif isinstance(klass, type):
        o = object.__new__(klass)
        o.__dict__ = d
        return o
    else:
        raise TypeError, "%s is not a class" % klass


def getValueElement(node):
    """Get the one child element of a given element.

    If there is more than one child element, raises ValueError.  Otherwise,
    returns the value element.
    """
    valueNode = None
    for subnode in node.childNodes:
        if isinstance(subnode, Element):
            if valueNode is None:
                valueNode = subnode
            else:
                raise ValueError("Only one value node allowed per instance!")
    return valueNode


class DOMJellyable:

    jellyDOMVersion = 1

    def jellyToDOM(self, jellier, element):
        element.setAttribute("marmalade:version", str(self.jellyDOMVersion))
        method = getattr(self, "jellyToDOM_%s" % self.jellyDOMVersion, None)
        if method:
            method(jellier, element)
        else:
            element.appendChild(jellier.jellyToNode(self.__dict__))

    def unjellyFromDOM(self, unjellier, element):
        pDOMVersion = element.getAttribute("marmalade:version") or "0"
        method = getattr(self, "unjellyFromDOM_%s" % pDOMVersion, None)
        if method:
            method(unjellier, element)
        else:
            # XXX: DOMJellyable.unjellyNode does not exist
            # XXX: 'node' is undefined - did you mean 'self', 'element', or 'Node'?
            state = self.unjellyNode(getValueElement(node))
            if hasattr(self.__class__, "__setstate__"):
                self.__setstate__(state)
            else:
                self.__dict__ = state



class DOMUnjellier:
    def __init__(self):
        self.references = {}
        self._savedLater = []

    def unjellyLater(self, node):
        """Unjelly a node, later.
        """
        d = _Defer()
        self.unjellyInto(d, 0, node)
        self._savedLater.append(d)
        return d

    def unjellyInto(self, obj, loc, node):
        """Utility method for unjellying one object into another.

        This automates the handling of backreferences.
        """
        o = self.unjellyNode(node)
        obj[loc] = o
        if isinstance(o, NotKnown):
            o.addDependant(obj, loc)
        return o

    def unjellyAttribute(self, instance, attrName, valueNode):
        """Utility method for unjellying into instances of attributes.

        Use this rather than unjellyNode unless you like surprising bugs!
        Alternatively, you can use unjellyInto on your instance's __dict__.
        """
        self.unjellyInto(instance.__dict__, attrName, valueNode)

    def unjellyNode(self, node):
        if node.tagName.lower() == "none":
            retval = None
        elif node.tagName == "string":
            # XXX FIXME this is obviously insecure
            # if you doubt:
            # >>> unjellyFromXML('''<string value="h&quot;+str(__import__(&quot;sys&quot;))+&quot;i" />''')
            # "h<module 'sys' (built-in)>i"
            retval = str(eval('"%s"' % node.getAttribute("value")))
        elif node.tagName == "int":
            retval = int(node.getAttribute("value"))
        elif node.tagName == "float":
            retval = float(node.getAttribute("value"))
        elif node.tagName == "longint":
            retval = long(node.getAttribute("value"))
        elif node.tagName == "bool":
            retval = int(node.getAttribute("value"))
            if retval:
                retval = True
            else:
                retval = False
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
                elif isinstance(im_self, NotKnown):
                    retval = _InstanceMethod(im_name, im_self, im_class)
                else:
                    retval = instancemethod(im_class.__dict__[im_name],
                                            im_self,
                                            im_class)
            else:
                raise TypeError("instance method changed")
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
                            raise TypeError("Unjellying Error: key role not set")
                        self.unjellyInto(kvd, 0, subnode)
                    else:
                        self.unjellyInto(kvd, 1, subnode)
                    keyMode = not keyMode
            retval = d
        elif node.tagName == "instance":
            className = node.getAttribute("class")
            clasz = namedClass(className)
            if issubclass(clasz, DOMJellyable):
                retval = instance(clasz, {})
                retval.unjellyFromDOM(self, node)
            else:
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
        elif node.tagName == "copyreg":
            nodefunc = namedObject(node.getAttribute("loadfunc"))
            loaddef = self.unjellyLater(getValueElement(node)).addCallback(
                lambda result, _l: apply(_l, result), nodefunc)
            retval = loaddef
        else:
            raise TypeError("Unsupported Node Type: %s" % (node.tagName,))
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
        l = [None]
        self.unjellyInto(l, 0, doc.childNodes[0])
        for svd in self._savedLater:
            svd.unpause()
        return l[0]


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
        #immutable (We don't care if these have multiple refs)
        if objType is types.NoneType:
            node = self.document.createElement("None")
        elif objType is types.StringType:
            node = self.document.createElement("string")
            r = repr(obj)
            if r[0] == '"':
                r = r.replace("'", "\\'")
            else:
                r = r.replace('"', '\\"')
            node.setAttribute("value", r[1:-1])
            # node.appendChild(CDATASection(obj))
        elif objType is types.IntType:
            node = self.document.createElement("int")
            node.setAttribute("value", str(obj))
        elif objType is types.LongType:
            node = self.document.createElement("longint")
            s = str(obj)
            if s[-1] == 'L':
                s = s[:-1]
            node.setAttribute("value", s)
        elif objType is types.FloatType:
            node = self.document.createElement("float")
            node.setAttribute("value", repr(obj))
        elif objType is types.MethodType:
            node = self.document.createElement("method")
            node.setAttribute("name", obj.im_func.__name__)
            node.setAttribute("class", qual(obj.im_class))
            # TODO: make methods 'prefer' not to jelly the object internally,
            # so that the object will show up where it's referenced first NOT
            # by a method.
            node.appendChild(self.jellyToNode(obj.im_self))
        elif hasattr(types, 'BooleanType') and objType is types.BooleanType:
            node = self.document.createElement("bool")
            node.setAttribute("value", str(int(obj)))
        elif objType is types.ModuleType:
            node = self.document.createElement("module")
            node.setAttribute("name", obj.__name__)
        elif objType==types.ClassType or issubclass(objType, type):
            node = self.document.createElement("class")
            node.setAttribute("name", qual(obj))
        elif objType is types.UnicodeType:
            node = self.document.createElement("unicode")
            obj = obj.encode('raw_unicode_escape')
            s = obj.replace("\n", "\\n").replace("\t", "\\t")
            node.setAttribute("value", s)
        elif objType in (types.FunctionType, types.BuiltinFunctionType):
            # TODO: beat pickle at its own game, and do BuiltinFunctionType
            # separately, looking for __self__ attribute and unpickling methods
            # of C objects when possible.
            node = self.document.createElement("function")
            node.setAttribute("name", fullFuncName(obj))
        else:
            #mutable!
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
                node = self.document.createElement("reference")
                node.setAttribute("key", key)
                return node
            node = self.document.createElement("UNNAMED")
            self.prepareElement(node, obj)
            if objType is types.ListType or __builtin__.__dict__.has_key('object') and isinstance(obj, NodeList):
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
            elif copy_reg.dispatch_table.has_key(objType):
                unpickleFunc, state = copy_reg.dispatch_table[objType](obj)
                node = self.document.createElement("copyreg")
                # node.setAttribute("type", objType.__name__)
                node.setAttribute("loadfunc", fullFuncName(unpickleFunc))
                node.appendChild(self.jellyToNode(state))
            elif objType is types.InstanceType or hasattr(objType, "__module__"):
                className = qual(obj.__class__)
                node.tagName = "instance"
                node.setAttribute("class", className)
                if isinstance(obj, DOMJellyable):
                    obj.jellyToDOM(self, node)
                else:
                    if hasattr(obj, "__getstate__"):
                        state = obj.__getstate__()
                    else:
                        state = obj.__dict__
                    n = self.jellyToNode(state)
                    node.appendChild(n)
            else:
                raise TypeError("Unsupported type: %s" % (objType.__name__,))
        return node

    def jelly(self, obj):
        """Create a document representing the current object, and return it.
        """
        node = self.jellyToNode(obj)
        self.document.appendChild(node)
        return self.document


def jellyToDOM(object):
    """Convert an Object into an twisted.web.microdom.Document.
    """
    dj = DOMJellier()
    document = dj.jelly(object)
    return document


def unjellyFromDOM(document):
    """Convert an twisted.web.microdom.Document into a Python object.
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


from twisted.web.microdom import Element, Document, parse, parseString, NodeList
