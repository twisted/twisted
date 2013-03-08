# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.tap}.
"""

try:
    import Crypto.Cipher.DES3
except:
    Crypto = None

try:
    import pyasn1
except ImportError:
    pyasn1 = None

try:
    from twisted.conch import unix
except ImportError:
    unix = None

if Crypto and pyasn1 and unix:
    from twisted.conch import tap
    from twisted.conch.openssh_compat.factory import OpenSSHFactory

from twisted.application.internet import StreamServerEndpointService
from twisted.cred import error
from twisted.cred.credentials import IPluggableAuthenticationModules
from twisted.cred.credentials import ISSHPrivateKey
from twisted.cred.credentials import IUsernamePassword, UsernamePassword

from twisted.trial.unittest import TestCase



class MakeServiceTest(TestCase):
    """
    Tests for L{tap.makeService}.
    """

    if not Crypto:
        skip = "can't run w/o PyCrypto"

    if not pyasn1:
        skip = "Cannot run without PyASN1"

    if not unix:
        skip = "can't run on non-posix computers"

    usernamePassword = ('iamuser', 'thisispassword')

    def setUp(self):
        """
        Create a file with two users.
        """
        self.filename = self.mktemp()
        f = open(self.filename, 'wb+')
        f.write(':'.join(self.usernamePassword))
        f.close()
        self.options = tap.Options()


    def test_basic(self):
        """
        L{tap.makeService} returns a L{StreamServerEndpointService} instance
        running on TCP port 22, and the linked protocol factory is an instance
        of L{OpenSSHFactory}.
        """
        config = tap.Options()
        service = tap.makeService(config)
        self.assertIsInstance(service, StreamServerEndpointService)
        self.assertEqual(service.endpoint._port, 22)
        self.assertIsInstance(service.factory, OpenSSHFactory)


    def test_defaultAuths(self):
        """
        Make sure that if the C{--auth} command-line option is not passed,
        the default checkers are (for backwards compatibility): SSH, UNIX, and
        PAM if available
        """
        numCheckers = 2
        try:
            from twisted.cred import pamauth
            self.assertIn(IPluggableAuthenticationModules,
                self.options['credInterfaces'],
                "PAM should be one of the modules")
            numCheckers += 1
        except ImportError:
            pass

        self.assertIn(ISSHPrivateKey, self.options['credInterfaces'],
            "SSH should be one of the default checkers")
        self.assertIn(IUsernamePassword, self.options['credInterfaces'],
            "UNIX should be one of the default checkers")
        self.assertEqual(numCheckers, len(self.options['credCheckers']),
            "There should be %d checkers by default" % (numCheckers,))


    def test_authAdded(self):
        """
        The C{--auth} command-line option will add a checker to the list of
        checkers, and it should be the only auth checker
        """
        self.options.parseOptions(['--auth', 'file:' + self.filename])
        self.assertEqual(len(self.options['credCheckers']), 1)


    def test_multipleAuthAdded(self):
        """
        Multiple C{--auth} command-line options will add all checkers specified
        to the list ofcheckers, and there should only be the specified auth
        checkers (no default checkers).
        """
        self.options.parseOptions(['--auth', 'file:' + self.filename,
                                   '--auth', 'memory:testuser:testpassword'])
        self.assertEqual(len(self.options['credCheckers']), 2)


    def test_authFailure(self):
        """
        The checker created by the C{--auth} command-line option returns a
        L{Deferred} that fails with L{UnauthorizedLogin} when
        presented with credentials that are unknown to that checker.
        """
        self.options.parseOptions(['--auth', 'file:' + self.filename])
        checker = self.options['credCheckers'][-1]
        invalid = UsernamePassword(self.usernamePassword[0], 'fake')
        # Wrong password should raise error
        return self.assertFailure(
            checker.requestAvatarId(invalid), error.UnauthorizedLogin)


    def test_authSuccess(self):
        """
        The checker created by the C{--auth} command-line option returns a
        L{Deferred} that returns the avatar id when presented with credentials
        that are known to that checker.
        """
        self.options.parseOptions(['--auth', 'file:' + self.filename])
        checker = self.options['credCheckers'][-1]
        correct = UsernamePassword(*self.usernamePassword)
        d = checker.requestAvatarId(correct)

        def checkSuccess(username):
            self.assertEqual(username, correct.username)

        return d.addCallback(checkSuccess)


    def test_checkersPamAuth(self):
        """
        The L{OpenSSHFactory} built by L{tap.makeService} has a portal with
        L{IPluggableAuthenticationModules}, L{ISSHPrivateKey} and
        L{IUsernamePassword} interfaces registered as checkers if C{pamauth} is
        available.
        """
        # Fake the presence of pamauth, even if PyPAM is not installed
        self.patch(tap, "pamauth", object())
        config = tap.Options()
        service = tap.makeService(config)
        portal = service.factory.portal
        self.assertEqual(
            set(portal.checkers.keys()),
            set([IPluggableAuthenticationModules, ISSHPrivateKey,
                 IUsernamePassword]))


    def test_checkersWithoutPamAuth(self):
        """
        The L{OpenSSHFactory} built by L{tap.makeService} has a portal with
        L{ISSHPrivateKey} and L{IUsernamePassword} interfaces registered as
        checkers if C{pamauth} is not available.
        """
        # Fake the absence of pamauth, even if PyPAM is installed
        self.patch(tap, "pamauth", None)
        config = tap.Options()
        service = tap.makeService(config)
        portal = service.factory.portal
        self.assertEqual(
            set(portal.checkers.keys()),
            set([ISSHPrivateKey, IUsernamePassword]))
