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

def _functionFactory(fname, comparator, value):
    """ Internal method which selects the function object """
    klassname = "_%sFunction" % fname
    c = globals()[klassname](comparator, value)
    return c

class _textFunction:
    def __init__(self, comparator = None, value = None):
        if comparator == "=":
            self.matches = self.isEqual
        else:
            self.matches = self.isNotEqual
        self.value = value

    def isEqual(self, elem):
        return str(elem) == self.value

    def isNotEqual(self, elem):
        return str(elem) != self.value        

class _Location:
    def __init__(self):
        self.predicates = []
        self.elementName  = None
        self.childLocation = None

    def matchesPredicates(self, elem):
        if self.elementName != None and self.elementName != elem.name:
            return 0
                
        for p in self.predicates:
            if not p.matches(elem):
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

class _SpecificChild:
    def __init__(self, index):
        self.index = int(index) - 1

    def matches(self, elem):
        if elem.parent != None:
           try:
               ndx = elem.parent.children.index(elem)
               return ndx == self.index 
           except:
               return False
        else:
            return False

class _AttribExists:
    def __init__(self, attribName):
        self.attribName = attribName

    def matches(self, elem):
        assert self.attribName != "xmlns"
        return elem.hasAttrib(self.attribName)

class _AttribValue:
    def __init__(self, attribName, cmp, value):
        self.attribName = attribName
        self.value = value
        if cmp == "!=":
            if self.attribName == "xmlns":
                self.__dict__["matches"] = self.NSIsNotEqual
            else:
                self.__dict__["matches"] = self.isNotEqual
        else:
            if self.attribName == "xmlns":
                self.__dict__["matches"] = self.NSIsEqual
            else:
                self.__dict__["matches"] = self.isEqual

    def NSIsNotEqual(self, elem):
         return elem.uri == self.value

    def NSIsEqual(self, elem):
         return elem.uri == self.value
    
    def isNotEqual(self, elem):
         return elem.compareAttribute(self.attribName, self.value) == 0

    def isEqual(self, elem):
         return elem.compareAttribute(self.attribName, self.value) == 1


class XPathQuery:
    def __init__(self, queryStr):
        from twisted.xish.xpathparser import parse
        self.baseLocation = parse('EXPRESSION', queryStr)

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

def internQuery(queryString):
    if queryString not in __internedQueries:
        __internedQueries[queryString] = XPathQuery(queryString)
    return __internedQueries[queryString]

def matches(xpathstr, elem):
    return internQuery(xpathstr).matches(elem)

def queryForStringList(xpathstr, elem):
    return internQuery(xpathstr).queryForStringList(elem)

def queryForNodes(xpathstr, elem):
    return internQuery(xpathstr).queryForNodes(elem)

# Convenience main to generate new xpathparser.py
if __name__ == "__main__":
    from twisted.python import yapps2
    yapps2.generate('xpathparser.g')
