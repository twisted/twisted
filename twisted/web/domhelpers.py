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

from twisted.web import microdom
import cStringIO

class NodeLookupError(Exception): pass

def substitute(request, node, subs):
    """
    Look through the given node's children for strings, and
    attempt to do string substitution with the given parameter.
    """
    for child in node.childNodes:
        if child.nodeValue:
            child.replaceData(0, len(child.nodeValue), child.nodeValue % subs)
        substitute(request, child, subs)

def _get(node, nodeId):
    """
    (internal) Get a node with the specified C{nodeId} as any of the C{class},
    C{id} or C{model} attributes.
    """
    if hasattr(node, 'hasAttributes') and node.hasAttributes() and ((str(node.getAttribute("id")) == nodeId) or (str(node.getAttribute("class")) == nodeId) or (str(node.getAttribute("model")) == nodeId) or (str(node.getAttribute("pattern")) == nodeId)):
        return node
    if node.hasChildNodes():
        if hasattr(node.childNodes, 'length'):
            length = node.childNodes.length
        else:
            length = len(node.childNodes)
        for childNum in range(length):
            result = _get(node.childNodes[childNum], nodeId)
            if result: return result

def get(node, nodeId):
    """
    Get a node with the specified C{nodeId} as any of the C{class},
    C{id} or C{model} attributes. If there is no such node, raise
    L{NodeLookupError}.
    """
    result = _get(node, nodeId)
    if result: return result
    raise NodeLookupError, nodeId

def getIfExists(node, nodeId):
    """
    Get a node with the specified C{nodeId} as any of the C{class},
    C{id} or C{model} attributes.  If there is no such node, return
    C{None}.
    """
    return _get(node, nodeId)

def getAndClear(node, nodeId):
    result = get(node, nodeId)
    if result:
        clearNode(result)
    return result

def clearNode(node):
    """
    Remove all children from the given node.
    """
    if node.hasChildNodes():
        while len(node.childNodes):
            node.removeChild(node.lastChild())

def locateNodes(nodeList, key, value):
    """
    Find subnodes in the given node where the given attribute
    has the given value.
    """
    returnList = []
    if not isinstance(nodeList, type([])):
        return locateNodes(nodeList.childNodes, key, value)
    
    for childNode in nodeList:
        if not hasattr(childNode, 'getAttribute'):
            continue
        if str(childNode.getAttribute(key)) == value:
            returnList.append(childNode)
        returnList.extend(locateNodes(childNode, key, value))
    return returnList
    
def superSetAttribute(node, key, value):
    if not hasattr(node, 'setAttribute'): return
    node.setAttribute(key, value)
    if node.hasChildNodes():
        for child in node.childNodes:
            superSetAttribute(child, key, value)

def superPrependAttribute(node, key, value):
    if not hasattr(node, 'setAttribute'): return
    old = node.getAttribute(key)
    if old:
        node.setAttribute(key, value+'/'+old)
    else:
        node.setAttribute(key, value)
    if node.hasChildNodes():
        for child in node.childNodes:
            superPrependAttribute(child, key, value)

def superAppendAttribute(node, key, value):
    if not hasattr(node, 'setAttribute'): return
    old = node.getAttribute(key)
    if old:
        node.setAttribute(key, old + '/' + value)
    else:
        node.setAttribute(key, value)
    if node.hasChildNodes():
        for child in node.childNodes:
            superAppendAttribute(child, key, value)

def getElementsByTagName(iNode, name):
    childNodes = iNode.childNodes[:]
    gathered = []
    while childNodes:
        node = childNodes.pop(0)
        if node.childNodes:
            childNodes.extend(node.childNodes)
        if node.nodeName == name:
            gathered.append(node)
    return gathered

def gatherTextNodes(iNode):
    childNodes = iNode.childNodes[:]
    gathered = []
    while childNodes:
        node = childNodes.pop(0)
        if node.childNodes:
            childNodes.extend(node.childNodes)
        if hasattr(node, 'nodeValue'):
            gathered.append(node.nodeValue)
    return ''.join(gathered)


class RawText(microdom.Text):
    """This is an evil and horrible speed hack. Basically, if you have a big
    chunk of XML that you want to insert into the DOM, but you don't want
    to incur the cost of parsing it, you can construct one of these and insert 
    it into the DOM. This will most certainly only work with minidom as the 
    API for converting nodes to xml is different in every DOM implementation.
    
    This could be improved by making this class a Lazy parser, so if you
    inserted this into the DOM and then later actually tried to mutate
    this node, it would be parsed then.
    """
    def writexml(self, writer, indent="", addindent="", newl=""):
        writer.write("%s%s%s" % (indent, self.data, newl))

def findNodes(parent, matcher, accum=None):
    if accum is None:
        accum = []
    if not hasattr(parent, 'childNodes'):
        return accum
    for child in parent.childNodes:
        # print child, child.nodeType, child.nodeName
        findNodes(child, matcher, accum)
        if matcher(child):
            accum.append(child)
    return accum

def findElements(parent, matcher):
    return findNodes(
        parent,
        lambda n, matcher=matcher: isinstance(n, microdom.Element) and
                                   matcher(n))

def findElementsWithAttribute(parent, attribute, value=None):
    if value:
        return findElements(
            parent,
            lambda n, attribute=attribute, value=value:
              n.hasAttribute(attribute) and n.getAttribute(attribute) == value)
    else:
        return findElements(
            parent,
            lambda n, attribute=attribute: n.hasAttribute(attribute))


def findNodesNamed(parent, name):
    return findNodes(parent, lambda n, name=name: n.nodeName == name)


def writeNodeData(node, oldio):
    for subnode in node.childNodes:
        if hasattr(subnode, 'data'):
            oldio.write(str(subnode.data))
        else:
            writeNodeData(subnode, oldio)


def getNodeText(node):
    oldio = cStringIO.StringIO()
    writeNodeData(node, oldio)
    return oldio.getvalue()
