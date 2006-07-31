
"""
Tests for the AMP/Anything chat proxy.
"""

from twisted.trial.unittest import TestCase
from twisted.internet.defer import maybeDeferred
from twisted.internet.ssl import KeyPair, DN

from twisted.words.proxy import (CertificateChecker, Realm, IProxyUser,
                                 ProxyServer)


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

    def test_knownCertificate(self):
        """
        Test that requesting an avatar identifier from a checker with a
        certificate which is allowed returns the correct avatar identifier.
        """
        serverKey = KeyPair.generate()

        clientKey = KeyPair.generate()
        certRequest = clientKey.requestObject(DN(commonName='testuser@testdomain'))
        cert = serverKey.signRequestObject(
            DN(commonName='admin@authoritativedomain'),
            certRequest,
            1)

        checker = CertificateChecker()
        d = maybeDeferred(checker.requestAvatarId, cert)
        d.addCallback(self.assertEquals, cert.digest())
        return d


class RealmTestCase(TestCase):
    def test_requestAvatarReturnsAvatar(self):
        realm = Realm()
        d = maybeDeferred(realm.requestAvatar, "ab:cd", None, IProxyUser)
        def gotAvatarInfo(r):
            iface, avatar, logout = r
            self.assertIdentical(iface, IProxyUser)
            self.failUnless(iface.providedBy(avatar))
        return d.addCallback(gotAvatarInfo)


class AMPServerTestCase(TestCase):
    """
    Tests for the part of the proxy that talks AMP to clients.
    """

    def test_login(self):
        """
        Test the initial command with which clients authenticate themselves to
        the chat proxy.
        """
        ps = ProxyServer()
        self.assertEquals(ps.login(), {'tls_started': ps._startedTLS})

    def test_loginSetsAvatar(self):
        """
        The 'TLS started', callback implementation should set the avatar on the
        protocol.
        """
        ps = ProxyServer()
        self.assertEquals(ps.avatar, None)
        ps._startedTLS()
        self.failUnless(IProxyUser.providedBy(ps.avatar))
