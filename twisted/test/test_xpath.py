

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

from twisted.trial import unittest
import sys, os

from twisted.xish.domish import Element
from twisted.xish.xpath import XPathQuery
from twisted.xish import xpath

class XPathTestCase(unittest.TestCase):
    def setUp(self):
        # Build element:
        # <foo xmlns='testns' attrib1='value1'>somecontent<bar/>somemorecontent<bar2 attrib2='value2'/><bar/></foo>
        self.e = Element(("testns", "foo"))
        self.e["attrib1"] = "value1"
        self.e.addContent("somecontent")
        self.bar1 = self.e.addElement("bar")
        self.e.addContent("somemorecontent")
        self.bar2 = self.e.addElement("bar2")
        self.bar2["attrib2"] = "value2"
        self.bar3 = self.e.addElement("bar")
        self.e["attrib3"] = "user@host/resource"

    
    def testStaticMethods(self):
        self.assertEquals(xpath.matches("/foo/bar2", self.e),
                          True)
        self.assertEquals(xpath.queryForNodes("/foo/bar", self.e),
                          [self.bar1, self.bar3])
        self.assertEquals(xpath.queryForString("/foo", self.e),
                          "somecontent")
        self.assertEquals(xpath.queryForStringList("/foo", self.e),
                          ["somecontent", "somemorecontent"])
        
    def testFunctionality(self):
        xp = XPathQuery("/foo/bar2")
        self.assertEquals(xp.matches(self.e), 1)

        xp = XPathQuery("/foo/bar3")
        self.assertEquals(xp.matches(self.e), 0)

        xp = XPathQuery("/foo/*")
        self.assertEquals(xp.matches(self.e), True)
        self.assertEquals(xp.queryForNodes(self.e), [self.bar1, self.bar2, self.bar3])

        xp = XPathQuery("/foo[@attrib1]")
        self.assertEquals(xp.matches(self.e), True)

        xp = XPathQuery("/foo/*[@attrib2='value2']")
        self.assertEquals(xp.matches(self.e), True)
        self.assertEquals(xp.queryForNodes(self.e), [self.bar2])

# XXX: Revist this, given new grammar
#        xp = XPathQuery("/foo/bar[2]")
#        self.assertEquals(xp.matches(self.e), 1)
#        self.assertEquals(xp.queryForNodes(self.e), [self.bar1])

        xp = XPathQuery("/foo[@xmlns='testns']/bar2")
        self.assertEquals(xp.matches(self.e), 1)

        xp = XPathQuery("/foo[@xmlns='badns']/bar2")
        self.assertEquals(xp.matches(self.e), 0)

        xp = XPathQuery("/foo[@attrib1='value1']")
        self.assertEquals(xp.matches(self.e), 1)

        xp = XPathQuery("/foo")
        self.assertEquals(xp.queryForString(self.e), "somecontent")
        self.assertEquals(xp.queryForStringList(self.e), ["somecontent", "somemorecontent"])

        xp = XPathQuery("/foo/bar")
        self.assertEquals(xp.queryForNodes(self.e), [self.bar1, self.bar3])

        xp = XPathQuery("/foo[text() = 'somecontent']")
        self.assertEquals(xp.matches(self.e), True)

        xp = XPathQuery("/foo[not(@nosuchattrib)]")
        self.assertEquals(xp.matches(self.e), True)

        xp = XPathQuery("/foo[juserhost(@attrib3) = 'user@host']")
        self.assertEquals(xp.matches(self.e), True)
