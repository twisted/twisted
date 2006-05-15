from twisted.trial import unittest

from twisted.words.protocols.jabber import error, xmlstream

class IQTest(unittest.TestCase):
    """ Tests both IQ and the associated IIQResponseTracker callback. """

    def setUp(self):
        self.outlist = []

        authenticator = xmlstream.ConnectAuthenticator('otherhost')
        authenticator.namespace = 'testns'
        self.xmlstream = xmlstream.XmlStream(authenticator)
        self.xmlstream.transport = self
        self.xmlstream.transport.write = self.outlist.append
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived(
           "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                          "xmlns='testns' from='otherhost' version='1.0'>")
        self.iq = xmlstream.IQ(self.xmlstream, type='get')

    def testBasic(self):
        self.assertEquals(self.iq['type'], 'get')
        self.assert_(self.iq['id'])

    def testSend(self):
        self.iq.send()
        self.assertEquals("<iq type='get' id='%s'/>" % self.iq['id'],
                          self.outlist[-1])

    def testResultResponse(self):
        def cb(result):
            self.assertEquals(result['type'], 'result')

        d = self.iq.send()
        d.addCallback(cb)

        xs = self.xmlstream
        xs.dataReceived("<iq type='result' id='%s'/>" % self.iq['id'])
        return d

    def testErrorResponse(self):
        d = self.iq.send()
        self.assertFailure(d, error.StanzaError)

        xs = self.xmlstream
        xs.dataReceived("<iq type='error' id='%s'/>" % self.iq['id'])
        return d
