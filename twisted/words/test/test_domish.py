# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

import sys, os

from twisted.words.xish import domish, xpath

class DomishTestCase(unittest.TestCase):
    def testEscaping(self):
        s = "&<>'\""
        self.assertEquals(domish.escapeToXml(s), "&amp;&lt;&gt;'\"")
        self.assertEquals(domish.escapeToXml(s, 1), "&amp;&lt;&gt;&apos;&quot;")

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

class DomishStreamTests:
    def setUp(self):
        self.doc_started = False
        self.packet_count = 0
        self.doc_ended = False
        self.stream = self.streamClass()
        self.stream.DocumentStartEvent = self._docStarted
        self.stream.ElementEvent = self._elementMatched
        self.stream.DocumentEndEvent = self._docEnded

    def _docStarted(self, root):
        self.doc_started = True
        assert self.match_root.matches(root)

    def _elementMatched(self, elem):
        self.packet_count = self.packet_count + 1
        assert self.match_elem.matches(elem)

    def _docEnded(self):
        self.doc_ended = True

    def doTest(self, xml):
        self.stream.parse(xml)
        self.assertEquals(self.doc_started, True)
        self.assertEquals(self.packet_count, 1)
        self.assertEquals(self.doc_ended, True)

    def testBasic(self):
        xml = "<stream:stream xmlns:stream='etherx' xmlns='jabber'>\n" + \
              "  <message to='bar'>" + \
              "    <x xmlns='xdelay'>some&amp;data&gt;</x>" + \
              "  </message>" + \
              "</stream:stream>"

        self.match_root = xpath.internQuery("/stream[@xmlns='etherx']")
        self.match_elem = xpath.internQuery("/message[@to='bar']/x[@xmlns='xdelay'][text()='some&data>']")

        self.doTest(xml)

    def testNoRootNS(self):
        xml = "<stream><error xmlns='etherx'/></stream>"

        self.match_root = xpath.internQuery("/stream[not(@xmlns)]")    
        self.match_elem = xpath.internQuery("/error[@xmlns='etherx']")
        
        self.doTest(xml)

    def testNoDefaultNS(self):
        xml = "<stream:stream xmlns:stream='etherx'><error/></stream:stream>"""
        self.match_root = xpath.internQuery("/stream[@xmlns='etherx']")    
        self.match_elem = xpath.internQuery("/error[not(@xmlns)]")
        
        self.doTest(xml)

    def testUnclosedElement(self):
        self.match_root = xpath.internQuery("/root")    
        self.assertRaises(domish.ParserError, self.stream.parse, 
                                              "<root><error></root>")

class DomishExpatStreamTestCase(unittest.TestCase, DomishStreamTests):
    def setUp(self):
        DomishStreamTests.setUp(self)

    def setUpClass(self):
        try: 
            import pyexpat
        except ImportError:
            raise unittest.SkipTest, "Skipping ExpatElementStream test, since no expat wrapper is available."

        self.streamClass = domish.ExpatElementStream

class DomishSuxStreamTestCase(unittest.TestCase, DomishStreamTests):
    def setUp(self):
        DomishStreamTests.setUp(self)

    def setUpClass(self):
        if domish.SuxElementStream is None:
            raise unittest.SkipTest, "Skipping SuxElementStream test, since twisted.web is not available."

        self.streamClass = domish.SuxElementStream

class SerializerTests:
    def testSerialization(self):
        e = domish.Element(("testns", "foo"))
        self.assertEquals(e.toXml(), "<foo/>")
        self.assertEquals(e.toXml(closeElement = 0), "<foo>")

    def testQualifiedAttributeSerialization(self):
        e = domish.Element(("testns", "foo"),
                           attribs = {("testns2", "bar"): "baz"})
        self.assertEquals(e.toXml({"testns2": "bar"}), "<foo bar:bar='baz'/>")

    def testRawXMLSerialization(self):
        e = domish.Element(("testns", "foo"))
        e.addRawXml("<abc123>")
        # The testcase below should NOT generate valid XML -- that's
        # the whole point of using the raw XML call -- it's the callers
        # responsiblity to ensure that the data inserted is valid
        self.assertEquals(e.toXml(), "<foo><abc123></foo>")

    def testRawXMLWithUnicodeSerialization(self):
        e = domish.Element(("testns", "foo"))
        e.addRawXml(u"<degree>\u00B0</degree>")
        self.assertEquals(e.toXml(), u"<foo><degree>\u00B0</degree></foo>")

    def testUnicodeSerialization(self):
        e = domish.Element(("testns", "foo"))
        e["test"] = u"my value\u0221e"
        e.addContent(u"A degree symbol...\u00B0")
        self.assertEquals(e.toXml(),
                          u"<foo test='my value\u0221e'>A degree symbol...\u00B0</foo>")

class DomishTestListSerializer(unittest.TestCase, SerializerTests):
    def setUpClass(self):
        self.__serializerClass = domish.SerializerClass
        domish.SerializerClass = domish._ListSerializer

    def tearDownClass(self):
        domish.SerializerClass = self.__serializerClass

