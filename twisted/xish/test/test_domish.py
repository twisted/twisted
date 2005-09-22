# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

import sys, os

from twisted.xish import domish, xpath

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

xml1 = """<stream:stream xmlns:stream='etherx' xmlns='jabber'>
             <message to='bar'><x xmlns='xdelay'>some&amp;data&gt;</x></message>
          </stream:stream>"""
query1_root = xpath.internQuery("/stream[@xmlns='etherx']")    
query1_elem1 = xpath.internQuery("/message[@to='bar']/x[@xmlns='xdelay'][text()='some&data>']")

xml2 = """<stream>
             <error xmlns='etherx'/>
          </stream>"""
query2_root = xpath.internQuery("/stream[not(@xmlns)]")    
query2_elem1 = xpath.internQuery("/error[@xmlns='etherx']")

xml3 = """<stream:stream xmlns:stream='etherx'>
             <error/>
      </stream:stream>"""
query3_root = xpath.internQuery("/stream[@xmlns='etherx']")    
query3_elem1 = xpath.internQuery("/error[not(@xmlns)]")

class DomishStreamTestCase(unittest.TestCase):    
    def setUp(self):
        self.doc_started = False
        self.packet_count = 0
        self.doc_ended = False

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
        self.match_list = matches
    
    def testSuxStream(self):
        if domish.SuxElementStream is None:
            raise unittest.SkipTest, "Skipping SuxElementStream test, since twisted.web is not available."
        # Setup the stream
        self.setupStream(domish.SuxElementStream(),
                         [query1_root, query1_elem1])

        # Run the test
        self.stream.parse(xml1)

        # Check result vars
        self.assertEquals(self.doc_started, True)
        self.assertEquals(self.packet_count, 1)
        self.assertEquals(self.doc_ended, True)
        
        # Setup the 2nd stream
        self.setupStream(domish.ExpatElementStream(),
                 [query2_root, query2_elem1])

        # Run the test
        self.stream.parse(xml2)

        # Setup the 3nd stream
        self.setupStream(domish.ExpatElementStream(),
                 [query3_root, query3_elem1])

        # Run the test
        self.stream.parse(xml3)

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

            # Setup the 2nd stream
            self.setupStream(domish.ExpatElementStream(),
                             [query2_root, query2_elem1])

            # Run the test
            self.stream.parse(xml2)

            # Setup the 3nd stream
            self.setupStream(domish.ExpatElementStream(),
                     [query3_root, query3_elem1])

            # Run the test
            self.stream.parse(xml3)

        except ImportError:
            raise unittest.SkipTest, "Skipping ExpatElementStream test, since no expat wrapper is available."

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

