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

