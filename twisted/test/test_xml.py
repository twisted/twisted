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

from __future__ import nested_scopes

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

    def testEmptyError(self):
        self.assertRaises(sux.ParseError, microdom.parseString, "")

    def testEatingWhitespace(self):
        s = """<hello>
        </hello>"""
        d = microdom.parseString(s)
        self.failUnless(not d.documentElement.hasChildNodes(),
                        d.documentElement.childNodes)
        self.failUnlessEqual(d, microdom.parseString('<hello></hello>'))

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

    def testPreserveCase(self):
        s = '<eNcApSuLaTe><sUxor></sUxor><bOrk><w00T>TeXt</W00t></BoRk></EnCaPsUlAtE>'
        s2 = s.lower().replace('text', 'TeXt')
        # these are the only two option permutations that *can* parse the above
        d = microdom.parseString(s, caseInsensitive=1, preserveCase=1)
        d2 = microdom.parseString(s, caseInsensitive=1, preserveCase=0)
        # caseInsensitive=0 preserveCase=0 is not valid, it's converted to
        # caseInsensitive=0 preserveCase=1
        d3 = microdom.parseString(s2, caseInsensitive=0, preserveCase=1)
        d4 = microdom.parseString(s2, caseInsensitive=1, preserveCase=0)
        d5 = microdom.parseString(s2, caseInsensitive=1, preserveCase=1)
        # this is slightly contrived, toxml() doesn't need to be identical
        # for the documents to be equivalent (i.e. <b></b> to <b/>),
        # however this assertion tests preserving case for start and
        # end tags while still matching stuff like <bOrk></BoRk>
        self.assertEquals(d.documentElement.toxml(), s)
        self.assertEquals(d, d2, "%r != %r" % (d.toxml(), d2.toxml()))
        self.assertEquals(d2, d3, "%r != %r" % (d2.toxml(), d3.toxml()))
        # caseInsensitive=0 on the left, NOT perserveCase=1 on the right
        self.assertNotEquals(d3, d2, "%r == %r" % (d3.toxml(), d2.toxml()))
        self.assertEquals(d3, d4, "%r != %r" % (d3.toxml(), d4.toxml()))
        self.assertEquals(d4, d5, "%r != %r" % (d4.toxml(), d5.toxml()))

    def testDifferentQuotes(self):
        s = '<test a="a" b=\'b\' />'
        d = microdom.parseString(s)
        e = d.documentElement
        self.assertEquals(e.getAttribute('a'), 'a')
        self.assertEquals(e.getAttribute('b'), 'b')

    def testLinebreaks(self):
        s = '<test \na="a"\n\tb="#b" />'
        d = microdom.parseString(s)
        e = d.documentElement
        self.assertEquals(e.getAttribute('a'), 'a')
        self.assertEquals(e.getAttribute('b'), '#b')

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
        s2 = "<foo><b/><b/><b/></foo>"
        nodes = microdom.parseString(s).documentElement.childNodes
        nodes2 = microdom.parseString(s2).documentElement.childNodes
        self.assertEquals(len(nodes), 3)
        for (n, n2) in zip(nodes, nodes2):
            self.assert_(isinstance(n, microdom.Element))
            self.assertEquals(n.nodeName, "b")
            self.assertEquals(n, n2)

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
        s1 = '<foo a="b"><bar/><foo/></foo>'
        s2 = '<foo a="b">foo</foo>'
        d = microdom.parseString(s).documentElement
        d1 = microdom.parseString(s1).documentElement
        d2 = microdom.parseString(s2).documentElement

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
        self.assertEquals(d, d1)

        d.removeChild(child)
        self.assertEquals(len(d.childNodes), 1)
        self.assertEquals(d.childNodes[0].nodeName, "bar")

        t = microdom.Text("foo")
        d.replaceChild(t, d.firstChild())
        self.assertEquals(d.firstChild(), t)
        self.assertEquals(d, d2)

    def testSearch(self):
        s = "<foo><bar id='me' /><baz><foo /></baz></foo>"
        s2 = "<fOo><bAr id='me' /><bAz><fOO /></bAz></fOo>"
        d = microdom.parseString(s)
        d2 = microdom.parseString(s2, caseInsensitive=0, preserveCase=1)
        d3 = microdom.parseString(s2, caseInsensitive=1, preserveCase=1)

        root = d.documentElement
        self.assertEquals(root.firstChild(), d.getElementById('me'))
        self.assertEquals(d.getElementsByTagName("foo"),
                          [root, root.lastChild().firstChild()])

        root = d2.documentElement
        self.assertEquals(root.firstChild(), d2.getElementById('me'))
        self.assertEquals(d2.getElementsByTagName('fOo'), [root])
        self.assertEquals(d2.getElementsByTagName('fOO'),
                          [root.lastChild().firstChild()])
        self.assertEquals(d2.getElementsByTagName('foo'), [])

        root = d3.documentElement
        self.assertEquals(root.firstChild(), d3.getElementById('me'))
        self.assertEquals(d3.getElementsByTagName('FOO'),
                          [root, root.lastChild().firstChild()])
        self.assertEquals(d3.getElementsByTagName('fOo'),
                          [root, root.lastChild().firstChild()])

    def testDoctype(self):
        s = ('<?xml version="1.0"?>'
        '<!DOCTYPE foo PUBLIC "baz" "http://www.example.com/example.dtd">'
        '<foo></foo>')
        s2 = '<foo/>'
        d = microdom.parseString(s)
        d2 = microdom.parseString(s2)
        self.assertEquals(d.doctype, 'foo PUBLIC "baz" "http://www.example.com/example.dtd"')
        self.assertEquals(d.toxml(), s)
        self.failIfEqual(d, d2)
        self.failUnlessEqual(d.documentElement, d2.documentElement)

    samples = [("<img/>", "<img />"),
               ("<foo A='b'>x</foo>", '<foo A="b">x</foo>'),
               ("<foo><BAR /></foo>", "<foo><BAR></BAR></foo>"),
               ("<foo>hello there &amp; yoyoy</foo>", "<foo>hello there &amp; yoyoy</foo>"),
               ]

    def testOutput(self):
        for s, out in self.samples:
            d = microdom.parseString(s, caseInsensitive=0)
            d2 = microdom.parseString(out, caseInsensitive=0)
            testOut = d.documentElement.toxml()
            self.assertEquals(out, testOut)
            self.assertEquals(d, d2)

    def testErrors(self):
        for s in ["<foo>&am</foo>", "<foo", "<f>&</f>", "<() />"]:
            self.assertRaises(Exception, microdom.parseString, s)

    def testCaseInsensitive(self):
        s  = "<foo a='b'><BAx>x</bax></FOO>"
        s2 = '<foo a="b"><bax>x</bax></foo>'
        s3 = "<FOO a='b'><BAx>x</BAx></FOO>"
        s4 = "<foo A='b'>x</foo>"
        d = microdom.parseString(s)
        d2 = microdom.parseString(s2)
        d3 = microdom.parseString(s3, caseInsensitive=1)
        d4 = microdom.parseString(s4, caseInsensitive=1, preserveCase=1)
        d5 = microdom.parseString(s4, caseInsensitive=1, preserveCase=0)
        d6 = microdom.parseString(s4, caseInsensitive=0, preserveCase=0)
        out = microdom.parseString(s).documentElement.toxml()
        self.assertRaises(microdom.MismatchedTags, microdom.parseString,
            s, caseInsensitive=0)
        self.assertEquals(out, s2)
        self.failUnlessEqual(d, d2)
        self.failUnlessEqual(d, d3)
        self.failUnless(d4.documentElement.hasAttribute('a'))
        self.failIf(d6.documentElement.hasAttribute('a'))
        self.assertEquals(d4.documentElement.toxml(), '<foo A="b">x</foo>')
        self.assertEquals(d5.documentElement.toxml(), '<foo a="b">x</foo>')

    def testUnicodeTolerance(self):
        import struct
        s = '<foo><bar><baz /></bar></foo>'
        j =(u'<?xml version="1.0" encoding="UCS-2" ?>\r\n<JAPANESE>\r\n'
            u'<TITLE>\u5c02\u9580\u5bb6\u30ea\u30b9\u30c8 </TITLE></JAPANESE>')
        j2=('\xff\xfe<\x00?\x00x\x00m\x00l\x00 \x00v\x00e\x00r\x00s\x00i\x00o'
            '\x00n\x00=\x00"\x001\x00.\x000\x00"\x00 \x00e\x00n\x00c\x00o\x00d'
            '\x00i\x00n\x00g\x00=\x00"\x00U\x00C\x00S\x00-\x002\x00"\x00 \x00?'
            '\x00>\x00\r\x00\n\x00<\x00J\x00A\x00P\x00A\x00N\x00E\x00S\x00E'
            '\x00>\x00\r\x00\n\x00<\x00T\x00I\x00T\x00L\x00E\x00>\x00\x02\\'
            '\x80\x95\xb6[\xea0\xb90\xc80 \x00<\x00/\x00T\x00I\x00T\x00L\x00E'
            '\x00>\x00<\x00/\x00J\x00A\x00P\x00A\x00N\x00E\x00S\x00E\x00>\x00')
        def reverseBytes(s):
            fmt = str(len(s) / 2) + 'H'
            return struct.pack('<' + fmt, *struct.unpack('>' + fmt, s))
        urd = microdom.parseString(reverseBytes(s.encode('UTF-16')))
        ud = microdom.parseString(s.encode('UTF-16'))
        sd = microdom.parseString(s)
        self.assertEquals(ud, sd)
        self.assertEquals(ud, urd)
        ud = microdom.parseString(j)
        urd = microdom.parseString(reverseBytes(j2))
        sd = microdom.parseString(j2)
        self.assertEquals(ud, sd)
        self.assertEquals(ud, urd)

        # test that raw text still gets encoded
        # test that comments get encoded
        j3=microdom.parseString(u'<foo/>')
        hdr='<?xml version="1.0"?>'
        div=microdom.lmx().text(u'\u221a', raw=1).node
        de=j3.documentElement
        de.appendChild(div)
        de.appendChild(j3.createComment(u'\u221a'))
        self.assertEquals(j3.toxml(), hdr+
                          u'<foo><div>\u221a</div><!--\u221a--></foo>'.encode('utf8'))

        

    def testCloneNode(self):
        s = '<foo a="b"><bax>x</bax></foo>'
        node = microdom.parseString(s).documentElement
        clone = node.cloneNode(deep=1)
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

        s = '<p>foo<b a="c"><foo z="foo"></foo><foo></foo><bar c="y"></bar></b></p>'
        self.assertEquals(s, n.toxml())

    def testDict(self):
        n = microdom.Element("p")
        d = {n : 1} # will fail if Element is unhashable

    def textEscaping(self):
        raw="&'some \"stuff\"', <what up?>"
        cooked="&amp;'some &quot;stuff&quot;', &lt;what up?&gt;"
        esc1=microdom.escape(input)
        self.assertEquals(esc1, cooked)
        self.assertEquals(microdom.unescape(esc1), input)
