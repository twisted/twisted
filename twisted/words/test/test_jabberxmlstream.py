from twisted.trial import unittest

from twisted.internet import defer, task
from twisted.internet.error import ConnectionLost
from twisted.test import proto_helpers
from twisted.words.xish import domish
from twisted.words.protocols.jabber import error, xmlstream

NS_XMPP_TLS = 'urn:ietf:params:xml:ns:xmpp-tls'

class IQTest(unittest.TestCase):
    """
    Tests both IQ and the associated IIQResponseTracker callback.
    """

    def setUp(self):
        authenticator = xmlstream.ConnectAuthenticator('otherhost')
        authenticator.namespace = 'testns'
        self.xmlstream = xmlstream.XmlStream(authenticator)
        self.clock = task.Clock()
        self.xmlstream._callLater = self.clock.callLater
        self.xmlstream.makeConnection(proto_helpers.StringTransport())
        self.xmlstream.dataReceived(
           "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                          "xmlns='testns' from='otherhost' version='1.0'>")
        self.iq = xmlstream.IQ(self.xmlstream, type='get')

    def testBasic(self):
        self.assertEquals(self.iq['type'], 'get')
        self.assert_(self.iq['id'])

    def testSend(self):
        self.xmlstream.transport.clear()
        self.iq.send()
        self.assertEquals("<iq type='get' id='%s'/>" % self.iq['id'],
                          self.xmlstream.transport.value())

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

    def testNonTrackedResponse(self):
        """
        Test that untracked iq responses don't trigger any action.

        Untracked means that the id of the incoming response iq is not
        in the stream's C{iqDeferreds} dictionary.
        """
        xs = self.xmlstream
        xmlstream.upgradeWithIQResponseTracker(xs)

        # Make sure we aren't tracking any iq's.
        self.failIf(xs.iqDeferreds)

        # Set up a fallback handler that checks the stanza's handled attribute.
        # If that is set to True, the iq tracker claims to have handled the
        # response.
        def cb(iq):
            self.failIf(getattr(iq, 'handled', False))

        xs.addObserver("/iq", cb, -1)

        # Receive an untracked iq response
        xs.dataReceived("<iq type='result' id='test'/>")

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

    def testRequestTimingOut(self):
        """
        Test that an iq request with a defined timeout times out.
        """
        self.iq.timeout = 60
        d = self.iq.send()
        self.assertFailure(d, xmlstream.TimeoutError)

        self.clock.pump([1, 60])
        self.failIf(self.clock.calls)
        self.failIf(self.xmlstream.iqDeferreds)
        return d

    def testRequestNotTimingOut(self):
        """
        Test that an iq request with a defined timeout does not time out
        when a response was received before the timeout period elapsed.
        """
        self.iq.timeout = 60
        d = self.iq.send()
        self.clock.callLater(1, self.xmlstream.dataReceived,
                             "<iq type='result' id='%s'/>" % self.iq['id'])
        self.clock.pump([1, 1])
        self.failIf(self.clock.calls)
        return d

    def testDisconnectTimeoutCancellation(self):
        """
        Test if timeouts for iq's that haven't yet received a response
        are cancelled on stream disconnect.
        """

        self.iq.timeout = 60
        d = self.iq.send()
        
        xs = self.xmlstream
        xs.connectionLost("Closed by peer")
        self.assertFailure(d, ConnectionLost)
        self.failIf(self.clock.calls)
        return d

class XmlStreamTest(unittest.TestCase):

    def onStreamStart(self, obj):
        self.gotStreamStart = True


    def onStreamEnd(self, obj):
        self.gotStreamEnd = True


    def onStreamError(self, obj):
        self.gotStreamError = True


    def setUp(self):
        """
        Set up XmlStream and several observers.
        """
        self.gotStreamStart = False
        self.gotStreamEnd = False
        self.gotStreamError = False
        xs = xmlstream.XmlStream(xmlstream.Authenticator())
        xs.addObserver('//event/stream/start', self.onStreamStart)
        xs.addObserver('//event/stream/end', self.onStreamEnd)
        xs.addObserver('//event/stream/error', self.onStreamError)
        xs.makeConnection(proto_helpers.StringTransportWithDisconnection())
        xs.transport.protocol = xs
        xs.namespace = 'testns'
        xs.version = (1, 0)
        self.xmlstream = xs


    def testSendHeaderBasic(self):
        """
        Basic test on the header sent by sendHeader.
        """
        xs = self.xmlstream
        xs.sendHeader()
        splitHeader = self.xmlstream.transport.value()[0:-1].split(' ')
        self.assertIn("<stream:stream", splitHeader)
        self.assertIn("xmlns:stream='http://etherx.jabber.org/streams'",
                      splitHeader)
        self.assertIn("xmlns='testns'", splitHeader)
        self.assertIn("version='1.0'", splitHeader)
        self.assertEquals(True, xs._headerSent)


    def testSendHeaderInitiating(self):
        """
        Test addressing when initiating a stream.
        """
        xs = self.xmlstream
        xs.thisHost = 'thisHost'
        xs.otherHost = 'otherHost'
        xs.initiating = True
        xs.sendHeader()
        splitHeader = xs.transport.value()[0:-1].split(' ')
        self.assertIn("to='otherHost'", splitHeader)
        self.assertNotIn("from='thisHost'", splitHeader)


    def testSendHeaderReceiving(self):
        """
        Test addressing when receiving a stream.
        """
        xs = self.xmlstream
        xs.thisHost = 'thisHost'
        xs.otherHost = 'otherHost'
        xs.initiating = False
        xs.sid = 'session01'
        xs.sendHeader()
        splitHeader = xs.transport.value()[0:-1].split(' ')
        self.assertNotIn("to='otherHost'", splitHeader)
        self.assertIn("from='thisHost'", splitHeader)
        self.assertIn("id='session01'", splitHeader)


    def testReceiveStreamError(self):
        """
        Test events when a stream error is received.
        """
        xs = self.xmlstream
        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345' version='1.0'>")
        xs.dataReceived("<stream:error/>")
        self.assert_(self.gotStreamError)
        self.assert_(self.gotStreamEnd)


    def testSendStreamErrorInitiating(self):
        """
        Test sendStreamError on an initiating xmlstream with a header sent.

        An error should be sent out and the connection lost.
        """
        xs = self.xmlstream
        xs.initiating = True
        xs.sendHeader()
        xs.transport.clear()
        xs.sendStreamError(error.StreamError('version-unsupported'))
        self.assertNotEqual('', xs.transport.value())
        self.assert_(self.gotStreamEnd)


    def testSendStreamErrorInitiatingNoHeader(self):
        """
        Test sendStreamError on an initiating xmlstream without having sent a
        header.

        In this case, no header should be generated. Also, the error should
        not be sent out on the stream. Just closing the connection.
        """
        xs = self.xmlstream
        xs.initiating = True
        xs.transport.clear()
        xs.sendStreamError(error.StreamError('version-unsupported'))
        self.assertNot(xs._headerSent)
        self.assertEqual('', xs.transport.value())
        self.assert_(self.gotStreamEnd)


    def testSendStreamErrorReceiving(self):
        """
        Test sendStreamError on a receiving xmlstream with a header sent.

        An error should be sent out and the connection lost.
        """
        xs = self.xmlstream
        xs.initiating = False
        xs.sendHeader()
        xs.transport.clear()
        xs.sendStreamError(error.StreamError('version-unsupported'))
        self.assertNotEqual('', xs.transport.value())
        self.assert_(self.gotStreamEnd)


    def testSendStreamErrorReceivingNoHeader(self):
        """
        Test sendStreamError on a receiving xmlstream without having sent a
        header.

        In this case, a header should be generated. Then, the error should
        be sent out on the stream followed by closing the connection.
        """
        xs = self.xmlstream
        xs.initiating = False
        xs.transport.clear()
        xs.sendStreamError(error.StreamError('version-unsupported'))
        self.assert_(xs._headerSent)
        self.assertNotEqual('', xs.transport.value())
        self.assert_(self.gotStreamEnd)


    def testOnDocumentStart(self):
        """
        Test onDocumentStart to fill the appropriate attributes from the
        stream header and stream start event.
        """
        xs = self.xmlstream
        xs.initiating = True
        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                         "xmlns:stream='http://etherx.jabber.org/streams' "
                         "from='example.com' id='12345' version='1.0'>")
        self.assert_(self.gotStreamStart)
        self.assertEqual((1, 0), xs.version)
        self.assertEqual('12345', xs.sid)
        xs.dataReceived("<stream:features>"
                          "<test xmlns='testns'/>"
                        "</stream:features>")
        self.assertIn(('testns', 'test'), xs.features)


    def testOnDocumentStartLegacy(self):
        """
        Test onDocumentStart to fill the appropriate attributes from the
        stream header and stream start event for a pre-XMPP-1.0 header.
        """
        xs = self.xmlstream
        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345'>")
        self.assert_(self.gotStreamStart)
        self.assertEqual((0, 0), xs.version)


    def testReset(self):
        """
        Test resetting the XML stream to start a new layer.
        """
        xs = self.xmlstream
        xs.sendHeader()
        stream = xs.stream
        xs.reset()
        self.assertNotEqual(stream, xs.stream)
        self.assertNot(xs._headerSent)


    def testSend(self):
        """
        Test send with various types of objects.
        """
        xs = self.xmlstream
        xs.send('<presence/>')
        self.assertEqual(xs.transport.value(), '<presence/>')

        xs.transport.clear()
        el = domish.Element(('testns', 'presence'))
        xs.send(el)
        self.assertEqual(xs.transport.value(), '<presence/>')

        xs.transport.clear()
        el = domish.Element(('http://etherx.jabber.org/streams', 'features'))
        xs.send(el)
        self.assertEqual(xs.transport.value(), '<stream:features/>')


    def testAuthenticator(self):
        """
        Test that the associated authenticator is correctly called.
        """
        connectionMade = []
        streamStarted = []
        associateWithStream = []

        class TestAuthenticator:
            def connectionMade(self):
                connectionMade.append(None)

            def streamStarted(self):
                streamStarted.append(None)

            def associateWithStream(self, xs):
                associateWithStream.append(xs)

        a = TestAuthenticator()
        xs = xmlstream.XmlStream(a)
        self.assertEqual([xs], associateWithStream)
        xs.connectionMade()
        self.assertEqual([None], connectionMade)
        xs.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345'>")
        self.assertEqual([None], streamStarted)
        xs.reset()
        self.assertEqual([None], connectionMade)



class TestError(Exception):
    pass



class ConnectAuthenticatorTest(unittest.TestCase):

    def setUp(self):
        self.gotAuthenticated = False
        self.initFailure = None
        self.authenticator = xmlstream.ConnectAuthenticator('otherHost')
        self.xmlstream = xmlstream.XmlStream(self.authenticator)
        self.xmlstream.addObserver('//event/stream/authd', self.onAuthenticated)
        self.xmlstream.addObserver('//event/xmpp/initfailed', self.onInitFailed)


    def onAuthenticated(self, obj):
        self.gotAuthenticated = True


    def onInitFailed(self, failure):
        self.initFailure = failure


    def testSucces(self):
        """
        Test successful completion of an initialization step.
        """
        class Initializer:
            def initialize(self):
                pass

        init = Initializer()
        self.xmlstream.initializers = [init]

        self.authenticator.initializeStream()
        self.assertEqual([], self.xmlstream.initializers)
        self.assert_(self.gotAuthenticated)


    def testFailure(self):
        """
        Test failure of an initialization step.
        """
        class Initializer:
            def initialize(self):
                raise TestError

        init = Initializer()
        self.xmlstream.initializers = [init]

        self.authenticator.initializeStream()
        self.assertEqual([init], self.xmlstream.initializers)
        self.assertFalse(self.gotAuthenticated)
        self.assertNotIdentical(None, self.initFailure)
        self.assert_(self.initFailure.check(TestError))



class TLSInitiatingInitializerTest(unittest.TestCase):
    def setUp(self):
        self.output = []
        self.done = []

        self.savedSSL = xmlstream.ssl

        self.authenticator = xmlstream.Authenticator()
        self.xmlstream = xmlstream.XmlStream(self.authenticator)
        self.xmlstream.send = self.output.append
        self.xmlstream.connectionMade()
        self.xmlstream.dataReceived("<stream:stream xmlns='jabber:client' "
                        "xmlns:stream='http://etherx.jabber.org/streams' "
                        "from='example.com' id='12345' version='1.0'>")
        self.init = xmlstream.TLSInitiatingInitializer(self.xmlstream)


    def tearDown(self):
        xmlstream.ssl = self.savedSSL


    def testWantedSupported(self):
        """
        Test start when TLS is wanted and the SSL library available.
        """
        self.xmlstream.transport = proto_helpers.StringTransport()
        self.xmlstream.transport.startTLS = lambda ctx: self.done.append('TLS')
        self.xmlstream.reset = lambda: self.done.append('reset')
        self.xmlstream.sendHeader = lambda: self.done.append('header')

        d = self.init.start()
        d.addCallback(self.assertEquals, xmlstream.Reset)
        starttls = self.output[0]
        self.assertEquals('starttls', starttls.name)
        self.assertEquals(NS_XMPP_TLS, starttls.uri)
        self.xmlstream.dataReceived("<proceed xmlns='%s'/>" % NS_XMPP_TLS)
        self.assertEquals(['TLS', 'reset', 'header'], self.done)

        return d

    if not xmlstream.ssl:
        testWantedSupported.skip = "SSL not available"

    def testWantedNotSupportedNotRequired(self):
        """
        Test start when TLS is wanted and the SSL library available.
        """
        xmlstream.ssl = None

        d = self.init.start()
        d.addCallback(self.assertEquals, None)
        self.assertEquals([], self.output)

        return d


    def testWantedNotSupportedRequired(self):
        """
        Test start when TLS is wanted and the SSL library available.
        """
        xmlstream.ssl = None
        self.init.required = True

        d = self.init.start()
        self.assertFailure(d, xmlstream.TLSNotSupported)
        self.assertEquals([], self.output)

        return d


    def testNotWantedRequired(self):
        """
        Test start when TLS is not wanted, but required by the server.
        """
        tls = domish.Element(('urn:ietf:params:xml:ns:xmpp-tls', 'starttls'))
        tls.addElement('required')
        self.xmlstream.features = {(tls.uri, tls.name): tls}
        self.init.wanted = False

        d = self.init.start()
        self.assertEquals([], self.output)
        self.assertFailure(d, xmlstream.TLSRequired)

        return d


    def testNotWantedNotRequired(self):
        """
        Test start when TLS is not wanted, but required by the server.
        """
        tls = domish.Element(('urn:ietf:params:xml:ns:xmpp-tls', 'starttls'))
        self.xmlstream.features = {(tls.uri, tls.name): tls}
        self.init.wanted = False

        d = self.init.start()
        d.addCallback(self.assertEqual, None)
        self.assertEquals([], self.output)
        return d


    def testFailed(self):
        """
        Test failed TLS negotiation.
        """
        # Pretend that ssl is supported, it isn't actually used when the
        # server starts out with a failure in response to our initial
        # C{starttls} stanza.
        xmlstream.ssl = 1

        d = self.init.start()
        self.assertFailure(d, xmlstream.TLSFailed)
        self.xmlstream.dataReceived("<failure xmlns='%s'/>" % NS_XMPP_TLS)
        return d



class TestFeatureInitializer(xmlstream.BaseFeatureInitiatingInitializer):
    feature = ('testns', 'test')

    def start(self):
        return defer.succeed(None)



class BaseFeatureInitiatingInitializerTest(unittest.TestCase):

    def setUp(self):
        self.xmlstream = xmlstream.XmlStream(xmlstream.Authenticator())
        self.init = TestFeatureInitializer(self.xmlstream)


    def testAdvertized(self):
        """
        Test that an advertized feature results in successful initialization.
        """
        self.xmlstream.features = {self.init.feature:
                                   domish.Element(self.init.feature)}
        return self.init.initialize()


    def testNotAdvertizedRequired(self):
        """
        Test that when the feature is not advertized, but required by the
        initializer, an exception is raised.
        """
        self.init.required = True
        self.assertRaises(xmlstream.FeatureNotAdvertized, self.init.initialize)


    def testNotAdvertizedNotRequired(self):
        """
        Test that when the feature is not advertized, and not required by the
        initializer, the initializer silently succeeds.
        """
        self.init.required = False
        self.assertIdentical(None, self.init.initialize())
