

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

class XPathTestCase(unittest.TestCase):
    def testStuff(self):
        # Build element:
        # <foo xmlns='testns' attrib1='value1'>somecontent<bar/>somemorecontent<bar2 attrib2='value2'/><bar/></foo>
        e = Element(("testns", "foo"))
        e["attrib1"] = "value1"
        e.addContent("somecontent")
        bar1 = e.addElement("bar")
        e.addContent("somemorecontent")
        bar2 = e.addElement("bar2")
        bar2["attrib2"] = "value2"
        bar3 = e.addElement("bar")

        xp = XPathQuery("/foo/bar2")
        self.assertEquals(xp.matches(e), 1)

        xp = XPathQuery("/foo/bar3")
        self.assertEquals(xp.matches(e), 0)

        xp = XPathQuery("/foo/*")
        self.assertEquals(xp.matches(e), True)
        self.assertEquals(xp.queryForNodes(e), [bar1, bar2, bar3])

        xp = XPathQuery("/foo/*[@attrib2='value2']")
        self.assertEquals(xp.matches(e), True)
        self.assertEquals(xp.queryForNodes(e), [bar2])

        xp = XPathQuery("/foo/bar[2]")
        self.assertEquals(xp.matches(e), 1)
        self.assertEquals(xp.queryForNodes(e), [bar1])

        xp = XPathQuery("/foo[@xmlns='testns']/bar2")
        self.assertEquals(xp.matches(e), 1)

        xp = XPathQuery("/foo[@xmlns='badns']/bar2")
        self.assertEquals(xp.matches(e), 0)

        xp = XPathQuery("/foo[@attrib1='value1']")
        self.assertEquals(xp.matches(e), 1)

        xp = XPathQuery("/foo")
        self.assertEquals(xp.queryForString(e), "somecontent")
        self.assertEquals(xp.queryForStringList(e), ["somecontent", "somemorecontent"])

        xp = XPathQuery("/foo/bar")
        self.assertEquals(xp.queryForNodes(e), [bar1, bar3])

        xp = XPathQuery("/foo[text() = 'somecontent']")
        self.assertEquals(xp.matches(e), True)

