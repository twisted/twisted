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

from twisted.xish import domish, xpath

class DomishTestCase(unittest.TestCase):
    def testEscaping(self):
        s = "&<>'\""
        self.assertEquals(domish.escapeToXml(s), "&amp;&lt;&gt;'\"")
        self.assertEquals(domish.escapeToXml(s, 1), "&amp;&lt;&gt;&apos;&quot;")

    def testSerialization(self):
        e = domish.Element(("testns", "foo"))
        self.assertEquals(e.toXml(), "<foo/>")
        self.assertEquals(e.toXml(closeElement = 0), "<foo>")

    def testRawXMLSerialization(self):
        e = domish.Element(("testns", "foo"))
        e.addRawXml("<abc123>")
        # The testcase below should NOT generate valid XML -- that's
        # the whole point of using the raw XML call -- it's the callers
        # responsiblity to ensure that the data inserted is valid
        self.assertEquals(e.toXml(), "<foo><abc123></foo>")

    def testUnicodeSerialization(self):
        for s in (domish._Serializer, domish._ListSerializer):
            domish.SerializerClass = s
            e = domish.Element(("testns", "foo"))
            e["test"] = u"my value\u0221e"
            e.addContent(u"A degree symbol...\u00B0")
            self.assertEquals(e.toXml(),
                              u"<foo test='my value\u0221e'>A degree symbol...\u00B0</foo>".encode("utf-8"))

    def testNamespaceObject(self):
        ns = domish.Namespace("testns")
        self.assertEquals(ns.foo, ("testns", "foo"))

    def testElementInit(self):
        e = domish.Element(("testns", "foo"))
        self.assertEquals(e.name, "foo")
        self.assertEquals(e.uri, "testns")
        self.assertEquals(e.defaultUri, "testns")
        self.assertEquals(e.parent, None)

        e = domish.Element(("testns", "foo"), "test2ns")
        self.assertEquals(e.name, "foo")
        self.assertEquals(e.uri, "testns")
        self.assertEquals(e.defaultUri, "test2ns")

    def testChildOps(self):
        e = domish.Element(("testns", "foo"))
        e.addContent("somecontent")
        b2 = e.addElement(("testns2", "bar2"))
        e["attrib1"] = "value1"
        e[("testns2", "attrib2")] = "value2"
        e[("testns", "attrib3")] = "value3"
        e.addElement("bar")
        e.addElement("bar")
        e.addContent("abc")
        e.addContent("123")

        # Check content merging
        self.assertEquals(e.children[-1], "abc123")

        # Check str()/content extraction
        self.assertEquals(str(e), "somecontent")

        # Check direct child accessor
        self.assertEquals(e.bar2, b2)
        e.bar2.addContent("subcontent")
        e.bar2["bar2value"] = "somevalue"

        # Check child ops
        self.assertEquals(e.children[1], e.bar2)
        self.assertEquals(e.children[2], e.bar)
        
        # Check attribute ops
        self.assertEquals(e["attrib1"], "value1")
        del e["attrib1"]
        self.assertEquals(e.hasAttribute("attrib1"), 0)
        self.assertEquals(e["attrib3"], "value3")
        self.assertEquals(e.hasAttribute("attrib2"), 0)
        self.assertEquals(e[("testns2", "attrib2")], "value2")

xml1 = """<stream:stream xmlns:stream='etherx' xmlns='jabber'>
             <message to='bar'><x xmlns='xdelay'>some&amp;data&gt;</x></message>
          </stream:stream>"""
query1_root = xpath.intern("/stream[@xmlns='etherx']")    
query1_elem1 = xpath.intern("/message[@to='bar']/x[@xmlns='xdelay'][text()='some&data>']")

class DomishStreamTestCase(unittest.TestCase):    
    def __init__(self):
        self.doc_started = False
        self.packet_count = 0
        self.doc_ended = False
        self.match_list = []

    def _docStarted(self, root):
        self.doc_started = True
        assert self.match_list.pop(0).matches(root)

    def _elementMatched(self, elem):
        self.packet_count = self.packet_count + 1
        assert self.match_list.pop(0).matches(elem)

    def _docEnded(self):
        self.doc_ended = True

    def setupStream(self, stream, matches):
        self.stream = stream
        self.stream.DocumentStartEvent = self._docStarted
        self.stream.ElementEvent = self._elementMatched
        self.stream.DocumentEndEvent = self._docEnded
        self.doc_started = False
        self.packet_count = 0
        self.doc_ended = False
        self.match_list = matches
    
    def testSuxStream(self):
        # Setup the stream
        self.setupStream(domish.SuxElementStream(),
                         [query1_root, query1_elem1])

        # Run the test
        self.stream.parse(xml1)

        # Check result vars
        self.assertEquals(self.doc_started, True)
        self.assertEquals(self.packet_count, 1)
        self.assertEquals(self.doc_ended, True)
        
    def testExpatStream(self):
        try: 
            # Setup the stream
            self.setupStream(domish.ExpatElementStream(),
                             [query1_root, query1_elem1])

            # Run the test
            self.stream.parse(xml1)

            # Check result vars
            self.assertEquals(self.doc_started, True)
            self.assertEquals(self.packet_count, 1)
            self.assertEquals(self.doc_ended, True)
        except ImportError:
            raise unittest.SkipTest, "Skipping ExpatElementStream test, since no expat wrapper is available."


