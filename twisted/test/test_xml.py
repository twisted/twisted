# -*- test-case-name: twisted.test.test_xml -*-
#
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

"""Some fairly inadequate testcases for Twisted XML support."""

from twisted.trial.unittest import TestCase

from twisted.protocols import sux

from twisted.web import microdom

from twisted.web import domhelpers

class Sux0r(sux.XMLParser):
    def __init__(self):
        self.tokens = []

    def getTagStarts(self):
        return [token for token in self.tokens if token[0] == 'start']

    def gotTagStart(self, name, attrs):
        self.tokens.append(("start", name, attrs))

    def gotText(self, text):
        self.tokens.append(("text", text))

class SUXTest(TestCase):

    def testBork(self):
        s = "<bork><bork><bork>"
        ms = Sux0r()
        ms.connectionMade()
        ms.dataReceived(s)
        self.failUnlessEqual(len(ms.getTagStarts()),3)


class MicroDOMTest(TestCase):

    def testEatingWhitespace(self):
        s = """<hello>   
        </hello>"""
        d = microdom.parseString(s)
        self.failUnless(not d.documentElement.hasChildNodes(),
                        d.documentElement.childNodes)
    
    def testTameDocument(self):
        s = """
        <test>
         <it>
          <is>
           <a>
            test
           </a>
          </is>
         </it>
        </test>
        """
        d = microdom.parseString(s)
        self.assertEquals(
            domhelpers.gatherTextNodes(d.documentElement).strip() ,'test')


    def testAwfulTagSoup(self):
        s = """
        <html>
        <head><title> I send you this message to have your advice!!!!</titl e
        </headd>

        <body bgcolor alink hlink vlink>

        <h1><BLINK>SALE</blINK> TWENTY MILLION EMAILS & FUR COAT NOW
        FREE WITH `ENLARGER'</h1>

        YES THIS WONDERFUL AWFER IS NOW HERER!!!
        
        </body>
        </HTML>
        """
        d = microdom.parseString(s, beExtremelyLenient=1)
        l = domhelpers.findNodesNamed(d.documentElement, 'blink')
        self.assertEquals(len(l), 1)

    def testDifferentQuotes(self):
        s = '<test a="a" b=\'b\' />'
        d = microdom.parseString(s)
        e = d.documentElement
        self.assertEquals(e.getAttribute('a'), 'a')
        self.assertEquals(e.getAttribute('b'), 'b')

    def testMismatchedTags(self):
        for s in '<test>', '<test> </tset>', '</test>':
            self.assertRaises(microdom.MismatchedTags, microdom.parseString, s)

    def testComment(self):
        s = "<bar><!--<foo />--></bar>"
        d = microdom.parseString(s)
        e = d.documentElement
        self.assertEquals(e.nodeName, "bar")
        c = e.childNodes[0]
        self.assert_(isinstance(c, microdom.Comment))
        self.assertEquals(c.value, "<foo />")
        c2 = c.cloneNode()
        self.assert_(c is not c2)
        self.assertEquals(c2.toxml(), "<!--<foo />-->")

    def testText(self):
        d = microdom.parseString("<bar>xxxx</bar>").documentElement
        text = d.childNodes[0]
        self.assert_(isinstance(text, microdom.Text))
        self.assertEquals(text.value, "xxxx")
        clone = text.cloneNode()
        self.assert_(clone is not text)
        self.assertEquals(clone.toxml(), "xxxx")
    
    def testEntities(self):
        nodes = microdom.parseString("<b>&amp;&#12AB;</b>").documentElement.childNodes
        self.assertEquals(len(nodes), 2)
        self.assertEquals(nodes[0].data, "&amp;")
        self.assertEquals(nodes[1].data, "&#12AB;")
        self.assertEquals(nodes[0].cloneNode().toxml(), "&amp;")
        for n in nodes:
            self.assert_(isinstance(n, microdom.EntityReference))

    def testCData(self):
        s = '<x><![CDATA[</x>\r\n & foo]]></x>'
        cdata = microdom.parseString(s).documentElement.childNodes[0]
        self.assert_(isinstance(cdata, microdom.CDATASection))
        self.assertEquals(cdata.data, "</x>\r\n & foo")
        self.assertEquals(cdata.cloneNode().toxml(), "<![CDATA[</x>\r\n & foo]]>")
    
    def testSingletons(self):
        s = "<foo><b/><b /><b\n/></foo>"
        nodes = microdom.parseString(s).documentElement.childNodes
        self.assertEquals(len(nodes), 3)
        for n in nodes:
            self.assert_(isinstance(n, microdom.Element))
            self.assertEquals(n.nodeName, "b")

    def testAttributes(self):
        s = '<foo a="b" />'
        node = microdom.parseString(s).documentElement
        
        self.assertEquals(node.getAttribute("a"), "b")
        self.assertEquals(node.getAttribute("c"), None)
        self.assert_(node.hasAttribute("a"))
        self.assert_(not node.hasAttribute("c"))
        a = node.getAttributeNode("a")
        self.assertEquals(a.value, "b")
        
        node.setAttribute("foo", "bar")
        self.assertEquals(node.getAttribute("foo"), "bar")

    def testChildren(self):
        s = "<foo><bar /><baz /><bax>foo</bax></foo>"
        d = microdom.parseString(s).documentElement
        self.assertEquals([n.nodeName for n in d.childNodes], ["bar", "baz", "bax"])
        self.assertEquals(d.lastChild().nodeName, "bax")
        self.assertEquals(d.firstChild().nodeName, "bar")
        self.assert_(d.hasChildNodes())
        self.assert_(not d.firstChild().hasChildNodes())

    def testMutate(self):
        s = "<foo />"
        d = microdom.parseString(s).documentElement

        d.appendChild(d.cloneNode())
        d.setAttribute("a", "b")
        child = d.childNodes[0]
        self.assertEquals(child.getAttribute("a"), None)
        self.assertEquals(child.nodeName, "foo")
        
        d.insertBefore(microdom.Element("bar"), child)
        self.assertEquals(d.childNodes[0].nodeName, "bar")
        self.assertEquals(d.childNodes[1], child)
        for n in d.childNodes:
            self.assertEquals(n.parentNode, d)
        
        d.removeChild(child)
        self.assertEquals(len(d.childNodes), 1)
        self.assertEquals(d.childNodes[0].nodeName, "bar")

        t = microdom.Text("foo")
        d.replaceChild(t, d.firstChild())
        self.assertEquals(d.firstChild(), t)

    def testSearch(self):
        s = "<foo><bar id='me' /><baz><foo /></baz></foo>"
        d = microdom.parseString(s)
        root = d.documentElement
        self.assertEquals(root.firstChild(), d.getElementById('me'))
        self.assertEquals(d.getElementsByTagName("foo"),
                          [root, root.lastChild().firstChild()])

    def testDoctype(self):
        s = '''<?xml version="1.0"?>
        <!DOCTYPE foo PUBLIC "baz" "http://www.example.com/example.dtd">
        <foo />'''
        d = microdom.parseString(s)
        self.assertEquals(d.doctype, 'foo PUBLIC "baz" "http://www.example.com/example.dtd"')

    samples = [("<foo/>", "<foo />"),
               ("<foo A='b'>x</foo>", '<foo A="b">x</foo>'),
               ("<foo><BAR /></foo>", "<foo><BAR /></foo>"),
               ("<foo>hello there &amp; yoyoy</foo>", "<foo>hello there &amp; yoyoy</foo>"),
               ]
    
    def testOutput(self):
        for s, out in self.samples:
            d = microdom.parseString(s, caseInsensitive=0)
            testOut = d.documentElement.toxml()
            self.assertEquals(out, testOut)

    def testErrors(self):
        for s in ["<foo>&am</foo>", "<foo", "<f>&</f>", "<() />"]:
            self.assertRaises(Exception, microdom.parseString, s)

    def testCaseInsensitive(self):
        s = "<foo a='b'><BAx>x</bax></FOO>"
        out = microdom.parseString(s).documentElement.toxml()
        self.assertEquals(out, '<foo a="b"><bax>x</bax></foo>')

    def testCloneNode(self):
        s = '<foo a="b"><bax>x</bax></foo>'
        node = microdom.parseString(s).documentElement
        clone = node.cloneNode()
        self.failIfEquals(node, clone)
        self.assertEquals(len(node.childNodes), len(clone.childNodes))
        c1, c2 = node.firstChild(), clone.firstChild()
        self.failIfEquals(c1, c2)
        self.assertEquals(len(c1.childNodes), len(c2.childNodes))
        self.failIfEquals(c1.firstChild(), c2.firstChild())
        self.assertEquals(s, clone.toxml())

    def testLMX(self):
        n = microdom.Element("p")
        lmx = microdom.lmx(n)
        lmx.text("foo")
        b = lmx.b(a="c")
        b.foo()["z"] = "foo"
        b.foo()
        b.add("bar", c="y")
        
        s = '<p>foo<b a="c"><foo z="foo" /><foo /><bar c="y" /></b></p>'
        self.assertEquals(s, n.toxml())
