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

    def testCaseSensitiveSoonCloser(self):
	s = """
	      <HTML><BODY>
	      <P ALIGN="CENTER">
		<A HREF="http://www.apache.org/"><IMG SRC="/icons/apache_pb.gif"></A>
	      </P>

	      <P>
		This is an insane set of text nodes that should NOT be gathered under
		the A tag above.
	      </P>
	      </BODY></HTML>
	    """
	d = microdom.parseString(s, beExtremelyLenient=1)
        l = domhelpers.findNodesNamed(d.documentElement, 'a')
	n = domhelpers.gatherTextNodes(l[0],1).replace('&nbsp;',' ')
	self.assertEquals(n.find('insane'), -1)

    def testEmptyError(self):
        self.assertRaises(sux.ParseError, microdom.parseString, "")

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

        <script LANGUAGE="javascript">
function give_answers() {
if (score < 70) {
alert("I hate you");
}}
        </script><a href=/foo.com/lalal name=foo>lalal</a>
        </body>
        </HTML>
        """
        d = microdom.parseString(s, beExtremelyLenient=1)
        l = domhelpers.findNodesNamed(d.documentElement, 'blink')
        self.assertEquals(len(l), 1)

    def testScriptLeniency(self):
        s = """
        <script>(foo < bar) and (bar > foo)</script>
        <script language="javascript">foo </scrip bar </script>
        <script src="foo">
        <script src="foo">baz</script>
        <script /><script></script>
        """
        d = microdom.parseString(s, beExtremelyLenient=1)
        self.assertEquals(d.firstChild().firstChild().firstChild().data,
                          "(foo < bar) and (bar > foo)")
        self.assertEquals(d.firstChild().getElementsByTagName("script")[1].firstChild().data,
                          "foo </scrip bar ")

    def testScriptLeniencyIntelligence(self):
        # if there is comment or CDATA in script, the autoquoting in bEL mode
        # should not happen
        s = """<script><!-- lalal --></script>"""
        self.assertEquals(microdom.parseString(s, beExtremelyLenient=1).firstChild().toxml(), s)
        s = """<script><![CDATA[lalal]]></script>"""
        self.assertEquals(microdom.parseString(s, beExtremelyLenient=1).firstChild().toxml(), s)
        s = """<script> // <![CDATA[
        lalal
        //]]></script>"""
        self.assertEquals(microdom.parseString(s, beExtremelyLenient=1).firstChild().toxml(), s)
        
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
        self.assert_(d.isEqualToDocument(d2), "%r != %r" % (d.toxml(), d2.toxml()))
        self.assert_(d2.isEqualToDocument(d3), "%r != %r" % (d2.toxml(), d3.toxml()))
        # caseInsensitive=0 on the left, NOT perserveCase=1 on the right
        ## XXX THIS TEST IS TURNED OFF UNTIL SOMEONE WHO CARES ABOUT FIXING IT DOES
        #self.failIf(d3.isEqualToDocument(d2), "%r == %r" % (d3.toxml(), d2.toxml()))
        self.assert_(d3.isEqualToDocument(d4), "%r != %r" % (d3.toxml(), d4.toxml()))
        self.assert_(d4.isEqualToDocument(d5), "%r != %r" % (d4.toxml(), d5.toxml()))

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
            self.assert_(n.isEqualToNode(n2))

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
        self.assert_(d.isEqualToNode(d1))

        d.removeChild(child)
        self.assertEquals(len(d.childNodes), 1)
        self.assertEquals(d.childNodes[0].nodeName, "bar")

        t = microdom.Text("foo")
        d.replaceChild(t, d.firstChild())
        self.assertEquals(d.firstChild(), t)
        self.assert_(d.isEqualToNode(d2))

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
        self.failIf(d.isEqualToDocument(d2))
        self.failUnless(d.documentElement.isEqualToNode(d2.documentElement))

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
            self.assert_(d.isEqualToDocument(d2))

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
        self.failUnless(d.isEqualToDocument(d2))
        self.failUnless(d.isEqualToDocument(d3))
        self.failUnless(d4.documentElement.hasAttribute('a'))
        self.failIf(d6.documentElement.hasAttribute('a'))
        self.assertEquals(d4.documentElement.toxml(), '<foo A="b">x</foo>')
        self.assertEquals(d5.documentElement.toxml(), '<foo a="b">x</foo>')
    def testEatingWhitespace(self):
        s = """<hello>
        </hello>"""
        d = microdom.parseString(s)
        self.failUnless(not d.documentElement.hasChildNodes(),
                        d.documentElement.childNodes)
        self.failUnless(d.isEqualToDocument(microdom.parseString('<hello></hello>')))

    def testLenientAmpersand(self):
        prefix = "<?xml version='1.0'?>"
        # we use <pre> so space will be preserved
        for i, o in [("&", "&amp;"),
                     ("& ", "&amp; "),
                     ("&amp;", "&amp;"),
                     ("&hello monkey", "&amp;hello monkey")]:
            d = microdom.parseString("%s<pre>%s</pre>" % (prefix, i), beExtremelyLenient=1)
            self.assertEquals(d.documentElement.toxml(), "<pre>%s</pre>" % o)
        # non-space preserving
        d = microdom.parseString("%s<t>hello & there</t>", beExtremelyLenient=1)
        self.assertEquals(d.documentElement.toxml(), "<t>hello &amp; there</t>")
    
    def testInsensitiveLenient(self):
        # testing issue #537
        d = microdom.parseString("<?xml version='1.0'?><bar><xA><y>c</Xa> <foo></bar>", beExtremelyLenient=1)
        self.assertEquals(d.documentElement.firstChild().toxml(), "<xa><y>c</y></xa>")

    def testSpacing(self):
        # testing issue #414
        s = "<?xml version='1.0'?><p><q>smart</q> <code>HairDryer</code></p>"
        d = microdom.parseString(s, beExtremelyLenient=1)
        self.assertEquals(d.documentElement.toxml(), "<p><q>smart</q> <code>HairDryer</code></p>")

    testSpacing.todo = "AAARGH white space swallowing screws this up"
    
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
        self.assert_(ud.isEqualToDocument(sd))
        self.assert_(ud.isEqualToDocument(urd))
        ud = microdom.parseString(j)
        urd = microdom.parseString(reverseBytes(j2))
        sd = microdom.parseString(j2)
        self.assert_(ud.isEqualToDocument(sd))
        self.assert_(ud.isEqualToDocument(urd))

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

    def testNamedChildren(self):
        tests = {"<foo><bar /><bar unf='1' /><bar>asdfadsf</bar>"
                         "<bam/></foo>" : 3,
                 '<foo>asdf</foo>' : 0,
                 '<foo><bar><bar></bar></bar></foo>' : 1,
                 }
        for t in tests.keys():
            node = microdom.parseString(t).documentElement
            result = domhelpers.namedChildren(node, 'bar')
            self.assertEquals(len(result), tests[t])
            if result:
                self.assert_(hasattr(result[0], 'tagName'))

    def testParseXMLStringWithUnicode(self):
        # this is a regression test. dash fixed something to do with xmlns=
        # and this tests to make sure that a particular case works
        
        str = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n<html lang="en" xml:lang="en" xmlns="http://www.w3.org/1999/xhtml"><head><title>Divmod Quotient</title><link href="/css" rel="stylesheet" /></head><body><img src="/images/anonymous-logo.png" id="anonymous-logo" /><div id="login-sidebar"><img src="/images/sidebar/login-top.png" /><div id="login-content"><h4>Log in.</h4><form action="/__login__/me/" method="POST" id="signin"><dl id="login-form"><dt>Username</dt><dd><input type="text" name="username" id="username" /></dd><dt>Password</dt><dd><input type="password" name="password" id="password" /></dd></dl><input type="submit" id="login" value="go" /></form></div><img src="/images/sidebar/login-bottom.png" /></div><div id="sidebar"><img src="/images/sidebar/dyk-top.png" /><div id="sidebar-content"><p><a href="/signup" id="signup">Sign Up a New User</a></p><p><a href="/claim" id="claim">Claim a Ticket</a></p></div><img src="/images/sidebar/dyk-bottom.png" /></div><div id="anonymous-main-body"><div id="anonymous-main-body-content"><img id="creatures" src="/images/creatures/home.png" />\n<h1>Divmod</h1>\n<h2>Smarter, cleaner, more active</h2>\n<h3>We are all deluged by information. Divmod helps you separate the signal from the\nnoise, so you can relate better.</h3>\n<h4>The Basics</h4>\n<ul>\n\t<li><strong>Fully-featured webmail</strong>  with POP, IMAP and SMTP</li>\n\t<li><strong>VOIP</strong> your own SIP address,\n\tyour internet phone number</li>\n\t<li><strong>Blogging</strong> Elegant and easy &mdash; post from the web or\n\tvia email (coming soon)</li>\n</ul>\n<h4>The Special Sauce</h4>\n<ul>\n\t<li><strong>Spam Filtering</strong> Double protection from\n\t<a href="http://www.postini.com">Postini</a> and <a href="http://spambayes.sf.net">Spambayes</a></li>\n\t<li><strong>Virus protection</strong></li>\n\t<li><strong>No advertisements</strong></li>\n\t<li><strong>No taglines</strong></li>\n\t<li><strong>Complete privacy</strong></li>\n\t<li><strong>Calls to other VOIP</strong> users are free; great rates\n\ton calls to landlines and cell phones</li>\n\t<li><strong>Extraction</strong> Divmod puts phone numbers, URLs,\n\temail addresses and more at your fingertips</li>\n\t<li><strong>Image Album</strong> All images are available in\n\talbum format, cross referenced by sender, recipient, and date</li>\n\t<li><strong>Cross-platform</strong> Works on Windows, Mac and\n\tLinux</li>\n</ul>\n\n<div id="anonymous-news">\n<h4>News</h4>\n<ul>\n\t<li>Divmod is <a href="http://www.divmod.org">open source</a> software.</li>\n\t<li><a href="http://www.divmod.org/Home/Projects/Shtoom/index.html">Shtoom 0.2</a> is out!</li>\n\t<li>Divmod celebrates first paying users with a round of yodeling.</li>\n</ul>\n</div>\n</div><div id="anonymous-main-body-footer"><ul><li><a href="About">About Us</a></li><li><a href="Privacy">Privacy Policy</a></li><li><a href="Terms">Terms of Use</a></li></ul></div></div><div id="anonymous-auxillary"><ol id="static-navigation"><a href="/"><li><img src="/images/anonymous-tabs-highlighted/Divmod.png" /></li></a><a href="Mail"><li><img src="/images/anonymous-tabs/Mail.png" /></li></a><a href="Voice"><li><img src="/images/anonymous-tabs/Voice.png" /></li></a><a href="Chat"><li><img src="/images/anonymous-tabs/Chat.png" /></li></a><a href="People"><li><img src="/images/anonymous-tabs/People.png" /></li></a><a href="Album"><li><img src="/images/anonymous-tabs/Album.png" /></li></a><a href="Calendar"><li><img src="/images/anonymous-tabs/Calendar.png" /></li></a><a href="Todo"><li><img src="/images/anonymous-tabs/Todo.png" /></li></a><a href="Find"><li><img src="/images/anonymous-tabs/Find.png" /></li></a><a href="Settings"><li><img src="/images/anonymous-tabs/Settings.png" /></li></a></ol></div></body></html>'

        node = microdom.parseString(str)

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
        self.assertEquals(node.namespace, clone.namespace)

    def testCloneDocument(self):
        # sorry bout the >80 cols, but whitespace is a sensitive thing
        s = '''<?xml version="1.0"?><!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><foo></foo>'''

        node = microdom.parseString(s)
        clone = node.cloneNode(deep=1)
        self.failIfEquals(node, clone)
        self.assertEquals(len(node.childNodes), len(clone.childNodes))
        self.assertEquals(s, clone.toxml())

        self.failUnless(clone.isEqualToDocument(node))
        self.failUnless(node.isEqualToDocument(clone))


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

    def testNamespaces(self):
        s = '''
        <x xmlns="base">
        <y />
        <y q="1" x:q="2" y:q="3" />
        <y:y xml:space="1">here is    some space </y:y>
        <y:y />
        <x:y />
        </x>
        '''
        d = microdom.parseString(s)
        # at least make sure it doesn't traceback
        s2 = d.toprettyxml()
        self.assertEquals(d.documentElement.namespace,
                          "base")
        self.assertEquals(d.documentElement.getElementsByTagName("y")[0].namespace,
                          "base")
        self.assertEquals(d.documentElement.getElementsByTagName("y")[1].getAttributeNS('base','q'),
                          '1')
        
        d2 = microdom.parseString(s2)
        self.assertEquals(d2.documentElement.namespace,
                          "base")
        self.assertEquals(d2.documentElement.getElementsByTagName("y")[0].namespace,
                          "base")
        self.assertEquals(d2.documentElement.getElementsByTagName("y")[1].getAttributeNS('base','q'),
                          '1')
