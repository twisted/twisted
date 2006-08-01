
"""
Tests for the AMP/Anything chat proxy.
"""

from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import StringTransport

from twisted.internet.defer import maybeDeferred, gatherResults
from twisted.internet.protocol import Protocol
from twisted.internet.ssl import KeyPair, DN
from twisted.cred.portal import Portal
from twisted.protocols.amp import COMMAND

from twisted.words.proxy import (
    IProxyUser, CertificateChecker, ProxyRealm, ProxyUser, ProxyServer,
    ConnectionCache)


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



class ConnectionCacheTestCase(TestCase):


    def setUp(self):
        self.tcpConnectors = []
        self.connCache = ConnectionCache(self)

    # Poop goes here vvv
    def connectTCP(self, hostname, portNumber, factory, bindAddress=None, timeout=None):
        self.tcpConnectors.append((hostname, portNumber, factory, bindAddress, timeout))

    def callLater(self, seconds, thingy, *args, **kwargs):
        # Fuck this shit.
        thingy(*args, **kwargs)

    def _fuckShitUp(self):
        protocols = []
        while self.tcpConnectors:
            connectionAttempt = self.tcpConnectors.pop(0)
            factory = connectionAttempt[2]
            protocol = factory.buildProtocol(None)
            protocol.makeConnection(StringTransport())
            protocols.append(protocol)
        return protocols

    # Poop was here ^^^


    def test_connectServer(self):
        """
        There should be an internal method for connecting to an IRC server that
        returns a Deferred which fires with a protocol.
        """
        d = self.connCache._connectServer('example.net', 6667, Protocol)
        connectionAttempt = self.tcpConnectors[0]
        self.assertEquals(connectionAttempt[0], 'example.net')
        self.assertEquals(connectionAttempt[1], 6667)
        self.assertEquals(connectionAttempt[3], None)

        [protocol] = self._fuckShitUp() # Fuck The What

        self.failUnless(isinstance(protocol, Protocol))
        return d.addCallback(self.assertIdentical, protocol)


    def test_cacheInternalsGetUnavailable(self):
        """
        I should not get a protocol when asking for a cached protocol for a
        thing that I don't have.
        """
        self.assertIdentical(
            self.connCache._getConnectionFromCache('example.com', 6667, object),
            None)


    def test_cacheIntervalsSetAndGet(self):
        """
        I should be able to put a protocol into a cache and get a protocol out
        of the cache.
        """
        o = object()
        self.connCache._addConnectionToCache('example.org', 6667, object, o)
        self.assertIdentical(self.connCache._getConnectionFromCache('example.org', 6667, object), o)


    def test_protocolPartOfCacheKey(self):
        """
        (host, port, protoClass1) and (host, port, protoClass2) should have
        separate connections.
        """
        class X:
            pass

        class Y:
            pass

        self.connCache._addConnectionToCache('example.com', 2129, X, X())
        self.assertIdentical(
            self.connCache._getConnectionFromCache('example.com', 2129, Y), None)


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

        [protocol] = self._fuckShitUp()

        self.failUnless(isinstance(protocol, Protocol))
        return d.addCallback(self.assertIdentical, protocol)


    def test_getConnectionReturnsExistingConnection(self):
        """
        Attempting to connect to a server which we already have a live
        connection to should return the already-connected protocol.
        """
        o = object()
        self.connCache._addConnectionToCache('example.net', 2929, object, o)
        d = self.connCache.getConnection('example.net', 2929, object)
        d.addCallback(self.assertIdentical, o)
        return d


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


    # TODO - test failed connection in all of the various states
    # TODO - test lost connection clears out cache



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
