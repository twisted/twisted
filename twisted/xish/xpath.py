# -*- test-case-name: twisted.test.test_xpath -*-
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

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

def _isStr(s):
    """ Internal method to determine if an object is a string """
    return isinstance(s, type('')) or isinstance(s, type(u''))

class LiteralValue(str):
    def value(self, elem):
        return self
    
class IndexValue:
    def __init__(self, index):
        self.index = int(index) - 1

    def value(self, elem):
        return elem.children[self.index]

class AttribValue:
    def __init__(self, attribname):        
        self.attribname = attribname
        if self.attribname == "xmlns":
            self.value = self.value_ns

    def value_ns(self, elem):
        return elem.uri 

    def value(self, elem):
        if self.attribname in elem.attributes:
            return elem.attributes[self.attribname]
        else:
            return None

class CompareValue:
    def __init__(self, lhs, op, rhs):
        self.lhs = lhs
        self.rhs = rhs
        if op == "=":
            self.value = self._compareEqual
        else:
            self.value = self._compareNotEqual

    def _compareEqual(self, elem):
        return self.lhs.value(elem) == self.rhs.value(elem)

    def _compareNotEqual(self, elem):
        return self.lhs.value(elem) != self.rhs.value(elem)

def Function(fname):
    """ Internal method which selects the function object """
    klassname = "_%s_Function" % fname
    c = globals()[klassname]()
    return c

class _not_Function:
    def __init__(self):
        self.baseValue = None

    def setParams(self, baseValue):
        self.baseValue = baseValue
        
    def value(self, elem):
        return not self.baseValue.value(elem)

class _text_Function:
    def setParams(self):
        pass
    
    def value(self, elem):
        return str(elem)

class _juserhost_Function:
    def setParams(self, sourceValue):
        self.sourceValue = sourceValue
        
    def value(self, elem):
        from twisted.protocols.jabber import jid
        try:
            user, host, resource = jid.parse(self.sourceValue.value(elem))
            if user:
                return "%s@%s" % (user, host)
            else:
                return None
        except jid.InvalidFormat:
            return None

class _Location:
    def __init__(self):
        self.predicates = []
        self.elementName  = None
        self.childLocation = None

    def matchesPredicates(self, elem):
        if self.elementName != None and self.elementName != elem.name:
            return 0
                
        for p in self.predicates:
            if not p.value(elem):
                return 0

        return 1

    def matches(self, elem):
        if not self.matchesPredicates(elem):
            return 0

        if self.childLocation != None:
            for c in elem.elements():
                if self.childLocation.matches(c):
                    return 1
        else:
            return 1

        return 0

    def queryForString(self, elem, resultbuf):
        if not self.matchesPredicates(elem):
            return 

        if self.childLocation != None:
            for c in elem.elements():
                self.childLocation.queryForString(c, resultbuf)
        else:            
            resultbuf.write(str(elem))

    def queryForNodes(self, elem, resultlist):
        if not self.matchesPredicates(elem):
            return 

        if self.childLocation != None:
            for c in elem.elements():
                self.childLocation.queryForNodes(c, resultlist)
        else:
            resultlist.append(elem)

    def queryForStringList(self, elem, resultlist):
        if not self.matchesPredicates(elem):
            return

        if self.childLocation != None:
            for c in elem.elements():
                self.childLocation.queryForStringList(c, resultlist)
        else:
            for c in elem.children:
                if _isStr(c): resultlist.append(c)

class _AnyLocation:
    def __init__(self):
        self.predicates = []
        self.elementName = None
        self.childLocation = None

    def matchesPredicates(self, elem):
        for p in self.predicates:
            if not p.value(elem):
                return 0
        return 1

    def listParents(self, elem, parentlist):
        if elem.parent != None:
            self.listParents(elem.parent, parentlist)
        parentlist.append(elem.name)

    def isRootMatch(self, elem):
        if (self.elementName == None or self.elementName == elem.name) and self.matchesPredicates(elem):
            if self.childLocation != None:
                for c in elem.elements():
                    if self.childLocation.matches(c):
                        return True
            else:
                return True
        return False

    def findFirstRootMatch(self, elem):
        if (self.elementName == None or self.elementName == elem.name) and self.matchesPredicates(elem):
            # Thus far, the name matches and the predicates match,
            # now check into the children and find the first one
            # that matches the rest of the structure
            # the rest of the structure
            if self.childLocation != None:
                for c in elem.elements():
                    if self.childLocation.matches(c):
                        return c
                return None
            else:
                # No children locations; this is a match!
                return elem
        else:
            # Ok, predicates or name didn't match, so we need to start
            # down each child and treat it as the root and try
            # again
            for c in elem.elements():
                if self.matches(c):
                    return c
            # No children matched...
            return None

    def matches(self, elem):
        if self.isRootMatch(elem):
            return True
        else:
            # Ok, initial element isn't an exact match, walk
            # down each child and treat it as the root and try
            # again
            for c in elem.elements():
                if self.matches(c):
                    return True
            # No children matched...
            return False

    def queryForString(self, elem, resultbuf):
        raise "UnsupportedOperation"

    def queryForNodes(self, elem, resultlist):
        # First check to see if _this_ element is a root
        if self.isRootMatch(elem):
            resultlist.append(elem)

        # Now check each child
        for c in elem.elements():
            self.queryForNodes(c, resultlist)            
        

    def queryForStringList(self, elem, resultlist):
        if self.isRootMatch(elem):
            for c in elem.children:
                if _isStr(c): resultlist.append(c)
        for c in elem.elements():
            self.queryForStringList(c, resultlist)
        


class XPathQuery:
    def __init__(self, queryStr):
        from twisted.xish.xpathparser import parse
        self.baseLocation = parse('XPATH', queryStr)

    def matches(self, elem):
        return self.baseLocation.matches(elem)

    def queryForString(self, elem):
        result = StringIO.StringIO()
        self.baseLocation.queryForString(elem, result)
        return result.getvalue()

    def queryForNodes(self, elem):
        result = []
        self.baseLocation.queryForNodes(elem, result)
        if len(result) == 0:
            return None
        else:
            return result

    def queryForStringList(self, elem):
        result = []
        self.baseLocation.queryForStringList(elem, result)
        if len(result) == 0:
            return None
        else:
            return result

__internedQueries = {}

def intern(queryString):
    if queryString not in __internedQueries:
        __internedQueries[queryString] = XPathQuery(queryString)
    return __internedQueries[queryString]

def matches(xpathstr, elem):
    return intern(xpathstr).matches(elem)

def queryForStringList(xpathstr, elem):
    return intern(xpathstr).queryForStringList(elem)

def queryForString(xpathstr, elem):
    return intern(xpathstr).queryForString(elem)

def queryForNodes(xpathstr, elem):
    return intern(xpathstr).queryForNodes(elem)

# Convenience main to generate new xpathparser.py
if __name__ == "__main__":
    from twisted.python import yapps2
    yapps2.generate('xpathparser.g')
