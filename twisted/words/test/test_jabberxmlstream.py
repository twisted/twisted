from twisted.trial import unittest

from twisted.internet.error import ConnectionLost
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

    def testCleanup(self):
        """
        Test if the deferred associated with an iq request is removed
        from the list kept in the L{XmlStream} object after it has
        been fired.
        """

        d = self.iq.send()
        xs = self.xmlstream
        xs.dataReceived("<iq type='result' id='%s'/>" % self.iq['id'])
        self.assertNotIn(self.iq['id'], xs.iqDeferreds)
        return d

    def testDisconnectCleanup(self):
        """
        Test if deferreds for iq's that haven't yet received a response
        have their errback called on stream disconnect.
        """

        d = self.iq.send()
        xs = self.xmlstream
        xs.connectionLost("Closed by peer")
        self.assertFailure(d, ConnectionLost)
        return d

    def testNoModifyingDict(self):
        """
        Test to make sure the errbacks cannot cause the iteration of the
        iqDeferreds to blow up in our face.
        """

        def eb(failure):
            d = xmlstream.IQ(self.xmlstream).send()
            d.addErrback(eb)

        d = self.iq.send()
        d.addErrback(eb)
        self.xmlstream.connectionLost("Closed by peer")
        return d
