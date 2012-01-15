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

from twisted.python.compat import set
from twisted.application.internet import StreamServerEndpointService
from twisted.cred.credentials import IPluggableAuthenticationModules
from twisted.cred.credentials import ISSHPrivateKey
from twisted.cred.credentials import IUsernamePassword

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
