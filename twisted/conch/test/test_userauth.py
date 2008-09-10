
from zope.interface import implements

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.portal import IRealm, Portal

try:
    import Crypto.Cipher.DES3, Crypto.Cipher.XOR
except ImportError:
    userauth = transport = None
else:
    from twisted.conch.ssh import userauth, transport

from twisted.conch.error import ConchError
from twisted.conch.ssh.common import NS

from twisted.internet import defer

from twisted.trial import unittest



if transport is not None:
    class FakeTransport(transport.SSHServerTransport):
        """
        L{userauth.SSHUserAuthServer} expects an SSH transport which has a factory
        attribute which has a portal attribute. Because the portal is important for
        testing authentication, we need to be able to provide an interesting portal
        object to the C{SSHUserAuthServer}.

        In addition, we want to be able to capture any packets sent over the
        transport.
        """


        class Service(object):
            name = 'nancy'

            def serviceStarted(self):
                pass


        class Factory(object):
            def _makeService(self):
                return FakeTransport.Service()

            def getService(self, transport, nextService):
                # This has to return a callable.
                return self._makeService


        def __init__(self, portal):
            self.factory = self.Factory()
            self.factory.portal = portal
            self.packets = []


        def sendPacket(self, messageType, message):
            self.packets.append((messageType, message))


        def isEncrypted(self, direction):
            """
            Pretend that this transport encrypts traffic in both directions. The
            SSHUserAuthServer disables password authentication if the transport
            isn't encrypted.
            """
            return True



class Realm(object):
    """
    A mock realm for testing L{userauth.SSHUserAuthServer}.

    This realm is not actually used in the course of testing, so it returns the
    simplest thing that could possibly work.
    """

    implements(IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        return defer.succeed((interfaces[0], None, lambda: None))



class MockChecker(object):
    """
    A very simple username/password checker which authenticates anyone whose
    password matches their username and rejects all others.
    """

    credentialInterfaces = (IUsernamePassword,)
    implements(ICredentialsChecker)


    def requestAvatarId(self, creds):
        if creds.username == creds.password:
            return defer.succeed(creds.username)
        return defer.fail(UnauthorizedLogin("Invalid username/password pair"))



class TestSSHUserAuthServer(unittest.TestCase):
    """
    Tests for SSHUserAuthServer.
    """

    if userauth is None:
        skip = "Cannot run without PyCrypto"

    def setUp(self):
        self.realm = Realm()
        portal = Portal(self.realm)
        portal.registerChecker(MockChecker())
        self.authServer = userauth.SSHUserAuthServer()
        self.authServer.transport = FakeTransport(portal)
        self.authServer.serviceStarted()


    def tearDown(self):
        self.authServer.serviceStopped()
        self.authServer = None


    def test_successfulAuthentication(self):
        """
        When provided with correct authentication information, the server
        should respond by sending a MSG_USERAUTH_SUCCESS message with no other
        data.

        See RFC 4252, Section 5.1.
        """
        packet = NS('foo') + NS('none') + NS('password') + chr(0) + NS('foo')
        d = self.authServer.ssh_USERAUTH_REQUEST(packet)

        def check(ignored):
            # Check that the server reports the failure, including 'password'
            # as a valid authentication type.
            self.assertEqual(
                self.authServer.transport.packets,
                [(userauth.MSG_USERAUTH_SUCCESS, '')])
        return d.addCallback(check)


    def test_failedAuthentication(self):
        """
        When provided with invalid authentication details, the server should
        respond by sending a MSG_USERAUTH_FAILURE message which states whether
        the authentication was partially successful, and provides other, open
        options for authentication.

        See RFC 4252, Section 5.1.
        """
        # packet = username, next_service, authentication type, FALSE, password
        packet = NS('foo') + NS('none') + NS('password') + chr(0) + NS('bar')
        d = self.authServer.ssh_USERAUTH_REQUEST(packet)

        def check(ignored):
            # Check that the server reports the failure, including 'password'
            # as a valid authentication type.
            self.assertEqual(
                self.authServer.transport.packets,
                [(userauth.MSG_USERAUTH_FAILURE, NS('password') + chr(0))])
        return d.addCallback(check)


    def test_requestRaisesConchError(self):
        """
        ssh_USERAUTH_REQUEST should raise a ConchError if tryAuth returns
        None. Added to catch a bug noticed by pyflakes. This is a whitebox
        test.
        """
        def mockTryAuth(kind, user, data):
            return None

        def mockEbBadAuth(reason):
            reason.trap(ConchError)

        self.patch(self.authServer, 'tryAuth', mockTryAuth)
        self.patch(self.authServer, '_ebBadAuth', mockEbBadAuth)

        packet = NS('user') + NS('none') + NS('public-key') + NS('data')
        # If an error other than ConchError is raised, this will trigger an
        # exception.
        return self.authServer.ssh_USERAUTH_REQUEST(packet)
