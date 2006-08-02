
"""
Tests for the AMP/Anything chat proxy.
"""

from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import StringTransport

from twisted.internet.defer import maybeDeferred, gatherResults, AlreadyCalledError
from twisted.internet.protocol import Protocol
from twisted.internet.ssl import KeyPair, DN
from twisted.internet.error import ConnectionLost
from twisted.internet import main # ha!
from twisted.python.failure import Failure
from twisted.cred.portal import Portal
from twisted.protocols.amp import COMMAND

from twisted.words.proxy import \
    IProxyUser, CertificateChecker, ProxyRealm, ProxyUser, ProxyServer, \
    ConnectionCache, _PendingEvent


class MockCertificate(object):
    def __init__(self, digest):
        self._digest = digest


    def digest(self, method='md5'):
        return self._digest + ':' + method



class CheckerTestCase(TestCase):

    def _makeSelfSignedCertificate(self, subject, issuer):
        key = KeyPair.generate()
        certRequest = key.requestObject(DN(commonName=subject))
        cert = key.signRequestObject(
            DN(commonName=issuer),
            certRequest,
            1)
        return key, cert

    # TODO: test that checker implements ICredentialsChecker
    # TODO: test that checker declares it can check certificate credentials

    def test_credentialsInterfaces(self):
        Portal(None, [CertificateChecker()])


    def test_knownCertificate(self):
        """
        Test that requesting an avatar identifier from a checker with a
        certificate which is allowed returns the correct avatar identifier.
        """
        checker = CertificateChecker()
        d = maybeDeferred(checker.requestAvatarId, MockCertificate('12:34:56'))
        d.addCallback(self.assertEquals, '12:34:56:md5')
        return d


class RealmTestCase(TestCase):
    def test_requestAvatarReturnsAvatar(self):
        realm = ProxyRealm()
        d = maybeDeferred(realm.requestAvatar, "ab:cd", None, IProxyUser)
        def gotAvatarInfo(r):
            iface, avatar, logout = r
            self.assertIdentical(iface, IProxyUser)
            self.failUnless(iface.providedBy(avatar))
        return d.addCallback(gotAvatarInfo)



class MockSecuredTransport(object):
    def __init__(self, certificate):
        self.certificate = certificate


    def getPeer(self):
        return 'peer'


    def getHost(self):
        return 'host'


    def getHandle(self):
        return self


    def get_peer_certificate(self):
        return self.certificate



class AMPServerTestCase(TestCase):
    """
    Tests for the part of the proxy that talks AMP to clients.
    """

    def setUp(self):
        self.certificate = MockCertificate('abc')
        self.realm = ProxyRealm()
        self.checker = CertificateChecker()
        self.portal = Portal(self.realm, [self.checker])
        self.transport = MockSecuredTransport(self.certificate)


    def test_associateAvatar(self):
        """
        Test that when the AssociateAvatar command completes successfully, the
        proxy server has an avatar matching the authentication user.
        """
        protocol = ProxyServer(self.portal)
        protocol.makeConnection(self.transport)
        associateDeferred = protocol.dispatchCommand({
                COMMAND: 'associateavatar'})
        def associated(result):
            self.assertEquals(result, {})
            self.assertEquals(protocol.avatar.avatarId, 'abc:md5')
        associateDeferred.addCallback(associated)
        return associateDeferred


class PendingEventTestCase(TestCase):
    def setUp(self):
        """
        Create a pending event.
        """
        self.pe = _PendingEvent()


    def test_positivePath1(self):
        """
        Verify that a callback works properly with one deferred.
        """
        d = self.pe.deferred()
        self.pe.callback(7)
        return d.addCallback(self.assertEquals, 7)

    def test_positivePathN(self):
        """
        Verify that a callback works properly with more than one deferred.
        """
        d1 = self.pe.deferred()
        d2 = self.pe.deferred()
        self.pe.callback(7)
        d1.addCallback(self.assertEquals, 7)
        d2.addCallback(self.assertEquals, 7)
        return gatherResults([d1, d2])


    def test_positivePathAfterN(self):
        d1 = self.pe.deferred()
        d2 = self.pe.deferred()
        self.pe.callback(7)
        d1.addCallback(self.assertEquals, 7)
        d2.addCallback(self.assertEquals, 7)
        d3 = self.pe.deferred()
        d3.addCallback(self.assertEquals, 7)
        return gatherResults([d1, d2, d3])


    def test_apiAbuse0(self):
        """
        Verify that attempting multiple callbacks fails with one deferred.
        """
        self.pe.callback(7)
        self.assertRaises(AlreadyCalledError, self.pe.callback, 7)


    def test_apiAbuse1(self):
        """
        Verify that attempting multiple callbacks fails with one deferred.
        """
        d = self.pe.deferred()
        self.pe.callback(7)
        self.assertRaises(AlreadyCalledError, self.pe.callback, 9999)
        return d.addCallback(self.assertEquals, 7)


    def test_apiAbuseN(self):
        """
        Verify that attempting multiple callbacks fails with one deferred.
        """
        d1 = self.pe.deferred()
        d2 = self.pe.deferred()
        self.pe.callback(7)
        self.assertRaises(AlreadyCalledError, self.pe.callback, 9999)
        d1.addCallback(self.assertEquals, 7)
        d2.addCallback(self.assertEquals, 7)
        return gatherResults([d1, d2])
        

    def test_apiAbuseNegative1(self):
        """
        Verify that attempting multiple errbacks fails with more than
        one deferred.
        """
        d = self.pe.deferred()
        self.pe.errback(Failure(ZeroDivisionError()))
        self.assertRaises(AlreadyCalledError, self.pe.errback, Failure(RuntimeError()))
        return self.assertFailure(d, ZeroDivisionError)


    def test_apiAbuseNegativeN(self):
        """ 
        Verify that attempting multiple errbacks fails with more than
        one deferred.
        """
        d1 = self.pe.deferred()
        d2 = self.pe.deferred()
        self.pe.errback(Failure(ZeroDivisionError()))
        self.assertRaises(AlreadyCalledError, self.pe.errback, Failure(RuntimeError()))
        d1 = self.assertFailure(d1, ZeroDivisionError)
        d2 = self.assertFailure(d2, ZeroDivisionError)
        return gatherResults([d1, d2])


    def test_negativePath1(self):
        """
        Verify that errback works with one deferred.
        """
        d = self.pe.deferred()
        self.pe.errback(Failure(ZeroDivisionError()))
        return self.assertFailure(d, ZeroDivisionError)


    def test_negativePathN(self):
        """
        Verify that errback works with many deferreds.
        """
        d1 = self.pe.deferred()
        d2 = self.pe.deferred()
        self.pe.errback(Failure(ZeroDivisionError()))
        d1 = self.assertFailure(d1, ZeroDivisionError)
        d2 = self.assertFailure(d2, ZeroDivisionError)
        return gatherResults([d1, d2])


    def test_negativePathNAfter(self):
        """
        Verify that errback works with many deferreds even after errback.
        """
        d1 = self.pe.deferred()
        d2 = self.pe.deferred()
        self.pe.errback(Failure(ZeroDivisionError()))
        d1 = self.assertFailure(d1, ZeroDivisionError)
        d2 = self.assertFailure(d2, ZeroDivisionError)
        d3 = self.pe.deferred()
        d3 = self.assertFailure(d3, ZeroDivisionError)
        return gatherResults([d1, d2, d3])


class ConnectionCacheTestCase(TestCase):


    def setUp(self):
        self.tcpConnectors = []
        self.connCache = ConnectionCache(self)

    # Poop goes here vvv
    def connectTCP(self, hostname, portNumber, factory, bindAddress=None,
                   timeout=None):
        self.tcpConnectors.append((hostname, portNumber, factory,
                                   bindAddress, timeout))


    def _fuckShitUp(self):
        protocols = []
        while self.tcpConnectors:
            connectionAttempt = self.tcpConnectors.pop(0)
            factory = connectionAttempt[2]
            protocol = factory.buildProtocol(None)
            protocol.makeConnection(StringTransport())
            protocols.append((protocol, factory))
        return protocols

    # Poop was here ^^^

    def test_protocolPartOfCacheKey(self):
        """
        (host, port, protoClass1) and (host, port, protoClass2) should have
        separate connections.
        """
        class NotProtocol(Protocol):
            pass
        d1 = self.connCache.getConnection('example.net', 6667, Protocol)
        d2 = self.connCache.getConnection('example.net', 6667, NotProtocol)
        [(protocol, factory),
         (protocol2, factory2)] = self._fuckShitUp()
        self.assertNotIdentical(protocol, protocol2)
        

    def test_getConnectionMakesNewConnection(self):
        """
        The first time this is called, it should have exactly the same
        semantics as _connectServer.
        """
        d = self.connCache.getConnection('example.net', 6667, Protocol)
        connectionAttempt = self.tcpConnectors[0]
        self.assertEquals(connectionAttempt[0], 'example.net')
        self.assertEquals(connectionAttempt[1], 6667)
        self.assertEquals(connectionAttempt[3], None)

        [(protocol, factory)] = self._fuckShitUp()

        self.failUnless(isinstance(protocol, Protocol))
        return d.addCallback(self.assertIdentical, protocol)


    def test_getConnectionReturnsExistingConnection(self):
        """
        Attempting to connect to a server which we already have a live
        connection to should return the already-connected protocol.
        """
        d1 = self.connCache.getConnection('example.net', 2929, Protocol)
        self._fuckShitUp()      # establish the connection.
        d2 = self.connCache.getConnection('example.net', 2929, Protocol)
        return gatherResults([d1, d2]).addCallback(
            lambda (r1, r2): self.assertIdentical(r1, r2))


    def test_concurrentConnectionAttempts(self):
        """
        Attempting to connect to a server which we are currently attempting to
        connect to should return a deferred which fires with that connection.
        """
        d = self.connCache.getConnection('example.net', 2929, Protocol)
        d2 = self.connCache.getConnection('example.net', 2929, Protocol)
        d3 = gatherResults([d, d2])
        def gotBothConnection(result):
            self.assertIdentical(result[0], result[1])
        d3.addCallback(gotBothConnection)

        self._fuckShitUp()
        return d3


    def test_loseConnection(self):
        """
        A protocol which loses its connection should be removed from
        the cache.
        """
        d = self.connCache.getConnection('example.net', 1239, Protocol)
        [(protocol, factory)] = self._fuckShitUp()
        # Twisted actually delivers notifications to the factory *and*
        # the protocol, but we only hook into the factory's, so we are
        # not sending one to the protocol.
        factory.clientConnectionLost(None, Failure(main.CONNECTION_DONE))
        connection = self.connCache._connections.get(('example.net', 1239,
                                                      Protocol))
        self.assertIdentical(connection, None)


    def test_connectionFailed(self):
        d = self.connCache.getConnection('example.net', 1239, Protocol)
        self.tcpConnectors[0][2].clientConnectionFailed(
            None, Failure(main.CONNECTION_LOST))
        return self.assertFailure(d, ConnectionLost)


    def test_connectionFailedErrbacksAllInProgressConnectionDeferreds(self):
        d1 = self.connCache.getConnection('example.net', 1239, Protocol)
        d2 = self.connCache.getConnection('example.net', 1239, Protocol)
        self.assertEquals(len(self.tcpConnectors), 1)
        self.tcpConnectors[0][2].clientConnectionFailed(
            None, Failure(main.CONNECTION_LOST))
        return gatherResults([self.assertFailure(d1, ConnectionLost),
                              self.assertFailure(d2, ConnectionLost)])


    # TODO - test failed connection in all of the various states


    # TODO - Test that protocolClass is involved in the in-progress checks



class ProxyUserTestCase(TestCase):
    """
    Test the proxy server application logic: connecting to servers, joining
    groups, etc.
    """


    def setUp(self):
        self.ircConfig = {
            'name': 'Example Server',
            'hostname': 'example.com',
            'portNumber': 6667,
            'nickname': 'nickname',
            'password': 'password',
            'username': 'username',
            'realname': 'realname'}
        self.user = ProxyUser('testuser', reactor=self)


    def test_addIRCServer(self):
        self.user.addIRCServer(**self.ircConfig)
        self.assertEquals(
            self.user.getIRCServers(),
            [self.ircConfig])




    





# FIXME: Test the all-encompassing "joinIRCChannel"
#         user = ProxyUser('testuser', reactor=self)
#         user.addIRCServer(**self.ircConfig)

#         group = Group(server='irc.freenode.net',
#                       name='testchannel')

#         d = user.joinIRCChannel(self.ircConfig['name'], "testchannel")
#         def channelJoined(result):
#             self.assertIdentical(
#                 result,
