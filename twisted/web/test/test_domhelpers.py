# -*- test-case-name: twisted.web.test.test_domhelpers -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""Specific tests for (some of) the methods in t.web.domhelpers"""

from twisted.trial.unittest import TestCase

from twisted.web import microdom

from twisted.web import domhelpers

class DomHelpersTest(TestCase):
    def test_getElementsByTagName(self):
        doc1=microdom.parseString('<foo/>')
        actual=domhelpers.getElementsByTagName(doc1, 'foo')[0].nodeName
        expected='foo'
        self.assertEquals(actual, expected)
        el1=doc1.documentElement
        actual=domhelpers.getElementsByTagName(el1, 'foo')[0].nodeName
        self.assertEqual(actual, expected)

        doc2_xml='<a><foo in="a"/><b><foo in="b"/></b><c><foo in="c"/></c><foo in="d"/><foo in="ef"/><g><foo in="g"/><h><foo in="h"/></h></g></a>'
        doc2=microdom.parseString(doc2_xml)
        tag_list=domhelpers.getElementsByTagName(doc2, 'foo')
        actual=''.join([node.getAttribute('in') for node in tag_list])
        expected='abcdefgh'
        self.assertEquals(actual, expected)
        el2=doc2.documentElement
        tag_list=domhelpers.getElementsByTagName(el2, 'foo')
        actual=''.join([node.getAttribute('in') for node in tag_list])
        self.assertEqual(actual, expected)

        doc3_xml='''
<a><foo in="a"/>
    <b><foo in="b"/>
        <d><foo in="d"/>
            <g><foo in="g"/></g>
            <h><foo in="h"/></h>
        </d>
        <e><foo in="e"/>
            <i><foo in="i"/></i>
        </e>
    </b>
    <c><foo in="c"/>
        <f><foo in="f"/>
            <j><foo in="j"/></j>
        </f>
    </c>
</a>'''
        doc3=microdom.parseString(doc3_xml)
        tag_list=domhelpers.getElementsByTagName(doc3, 'foo')
        actual=''.join([node.getAttribute('in') for node in tag_list])
        expected='abdgheicfj'
        self.assertEquals(actual, expected)
        el3=doc3.documentElement
        tag_list=domhelpers.getElementsByTagName(el3, 'foo')
        actual=''.join([node.getAttribute('in') for node in tag_list])
        self.assertEqual(actual, expected)

        doc4_xml='<foo><bar></bar><baz><foo/></baz></foo>'
        doc4=microdom.parseString(doc4_xml)
        actual=domhelpers.getElementsByTagName(doc4, 'foo')
        root=doc4.documentElement
        expected=[root, root.lastChild().firstChild()]
        self.assertEquals(actual, expected)
        actual=domhelpers.getElementsByTagName(root, 'foo')
        self.assertEqual(actual, expected)


    def test_gatherTextNodes(self):
        doc1=microdom.parseString('<a>foo</a>')
        actual=domhelpers.gatherTextNodes(doc1)
        expected='foo'
        self.assertEqual(actual, expected)
        actual=domhelpers.gatherTextNodes(doc1.documentElement)
        self.assertEqual(actual, expected)

        doc2_xml='<a>a<b>b</b><c>c</c>def<g>g<h>h</h></g></a>'
        doc2=microdom.parseString(doc2_xml)
        actual=domhelpers.gatherTextNodes(doc2)
        expected='abcdefgh'
        self.assertEqual(actual, expected)
        actual=domhelpers.gatherTextNodes(doc2.documentElement)
        self.assertEqual(actual, expected)

        doc3_xml=('<a>a<b>b<d>d<g>g</g><h>h</h></d><e>e<i>i</i></e></b>' +
                  '<c>c<f>f<j>j</j></f></c></a>')
        doc3=microdom.parseString(doc3_xml)
        actual=domhelpers.gatherTextNodes(doc3)
        expected='abdgheicfj'
        self.assertEqual(actual, expected)
        actual=domhelpers.gatherTextNodes(doc3.documentElement)
        self.assertEqual(actual, expected)

        doc4_xml='''<html>
  <head>
  </head>
  <body>
    stuff
  </body>
</html>
'''
        doc4=microdom.parseString(doc4_xml)
        actual=domhelpers.gatherTextNodes(doc4)
        expected='\n    stuff\n  '
        assert actual==expected, 'expected %s, got %s' % (expected, actual)
        actual=domhelpers.gatherTextNodes(doc4.documentElement)
        self.assertEqual(actual, expected)
        
        doc5_xml='<x>Souffl&eacute;</x>'
        doc5=microdom.parseString(doc5_xml)
        actual=domhelpers.gatherTextNodes(doc5)
        expected='Souffl&eacute;'
        self.assertEqual(actual, expected)
        actual=domhelpers.gatherTextNodes(doc5.documentElement)
        self.assertEqual(actual, expected)

    def test_clearNode(self):
        doc1=microdom.parseString('<a><b><c><d/></c></b></a>')
        a_node=doc1.documentElement
        domhelpers.clearNode(a_node)
        actual=doc1.documentElement.toxml()
        expected='<a></a>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)
 
        doc2=microdom.parseString('<a><b><c><d/></c></b></a>')
        b_node=doc2.documentElement.childNodes[0]
        domhelpers.clearNode(b_node)
        actual=doc2.documentElement.toxml()
        expected='<a><b></b></a>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

        doc3=microdom.parseString('<a><b><c><d/></c></b></a>')
        c_node=doc3.documentElement.childNodes[0].childNodes[0]
        domhelpers.clearNode(c_node)
        actual=doc3.documentElement.toxml()
        expected='<a><b><c></c></b></a>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

    def test_get(self):
        doc1=microdom.parseString('<a><b id="bar"/><c class="foo"/></a>')
        node=domhelpers.get(doc1, "foo")
        actual=node.toxml()
        expected='<c class="foo"></c>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

        node=domhelpers.get(doc1, "bar")
        actual=node.toxml()
        expected='<b id="bar"></b>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

        self.assertRaises(domhelpers.NodeLookupError, 
                          domhelpers.get, 
                          doc1, 
                          "pzork")

    def test_getIfExists(self):
        doc1=microdom.parseString('<a><b id="bar"/><c class="foo"/></a>')
        node=domhelpers.getIfExists(doc1, "foo")
        actual=node.toxml()
        expected='<c class="foo"></c>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

        node=domhelpers.getIfExists(doc1, "pzork")
        assert node==None, 'expected None, didn\'t get None'

    def test_getAndClear(self):
        doc1=microdom.parseString('<a><b id="foo"><c></c></b></a>')
        node=domhelpers.getAndClear(doc1, "foo")
        actual=node.toxml()
        expected='<b id="foo"></b>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

    def test_locateNodes(self):
        doc1=microdom.parseString('<a><b foo="olive"><c foo="olive"/></b><d foo="poopy"/></a>')
        node_list=domhelpers.locateNodes(doc1.childNodes, 'foo', 'olive',
                                         noNesting=1)
        actual=''.join([node.toxml() for node in node_list])
        expected='<b foo="olive"><c foo="olive"></c></b>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

        node_list=domhelpers.locateNodes(doc1.childNodes, 'foo', 'olive',
                                         noNesting=0)
        actual=''.join([node.toxml() for node in node_list])
        expected='<b foo="olive"><c foo="olive"></c></b><c foo="olive"></c>'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

    def test_getParents(self):
        doc1=microdom.parseString('<a><b><c><d/></c><e/></b><f/></a>')
        node_list=domhelpers.getParents(doc1.childNodes[0].childNodes[0].childNodes[0])
        actual=''.join([node.tagName for node in node_list
                        if hasattr(node, 'tagName')])
        expected='cba'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

    def test_findElementsWithAttribute(self):
        doc1=microdom.parseString('<a foo="1"><b foo="2"/><c foo="1"/><d/></a>')
        node_list=domhelpers.findElementsWithAttribute(doc1, 'foo')
        actual=''.join([node.tagName for node in node_list])
        expected='abc'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

        node_list=domhelpers.findElementsWithAttribute(doc1, 'foo', '1')
        actual=''.join([node.tagName for node in node_list])
        expected='ac'
        assert actual==expected, 'expected %s, got %s' % (expected, actual)

    def test_findNodesNamed(self):
        doc1=microdom.parseString('<doc><foo/><bar/><foo>a</foo></doc>')
        node_list=domhelpers.findNodesNamed(doc1, 'foo')
        actual=len(node_list)
        expected=2
        assert actual==expected, 'expected %d, got %d' % (expected, actual)

    # NOT SURE WHAT THESE ARE SUPPOSED TO DO..
    # def test_RawText  FIXME
    # def test_superSetAttribute FIXME
    # def test_superPrependAttribute FIXME
    # def test_superAppendAttribute FIXME
    # def test_substitute FIXME

    def test_escape(self):
        j='this string " contains many & characters> xml< won\'t like'
        expected='this string &quot; contains many &amp; characters&gt; xml&lt; won\'t like'
        self.assertEqual(domhelpers.escape(j), expected)

    def test_unescape(self):
        j='this string &quot; has &&amp; entities &gt; &lt; and some characters xml won\'t like<'
        expected='this string " has && entities > < and some characters xml won\'t like<'
        self.assertEqual(domhelpers.unescape(j), expected)
