# -*- test-case-name: twisted.test.test_xml -*-

# Some woefully inadequate testcases for our XML stuff.

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

    def testText(self):
        d = microdom.parseString("<bar>xxxx</bar>").documentElement
        text = d.childNodes[0]
        self.assert_(isinstance(text, microdom.Text))
        self.assertEquals(text.value, "xxxx")
        
    def testEntities(self):
        nodes = microdom.parseString("<b>&amp;&#12AB;</b>").documentElement.childNodes
        self.assertEquals(len(nodes), 2)
        self.assertEquals(nodes[0].data, "&amp;")
        self.assertEquals(nodes[1].data, "&#12AB;")
        for n in nodes:
            self.assert_(isinstance(n, microdom.EntityReference))

    def testCData(self):
        s = '<x><![CDATA[</x>\r\n & foo]]></x>'
        cdata = microdom.parseString(s).documentElement.childNodes[0]
        self.assert_(isinstance(cdata, microdom.CDATASection))
        self.assertEquals(cdata.data, "</x>\r\n & foo")

    def testSingletons(self):
        s = "<foo><b/><b /><b\n/></foo>"
        nodes = microdom.parseString(s).documentElement.childNodes
        self.assertEquals(len(nodes), 3)
        for n in nodes:
            self.assert_(isinstance(n, microdom.Element))
            self.assertEquals(n.nodeName, "b")
