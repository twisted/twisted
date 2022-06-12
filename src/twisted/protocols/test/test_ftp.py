# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.protocols.ftp}.
"""


from twisted.protocols import ftp
from twisted.trial import unittest


class MockDefer:
    """
    Mock of L{twisted.internet.defer}.
    """

    def addCallbacks(self, func1, func2):
        pass


class MockPortal:
    """
    Mock of L{twisted.cred.portal.Portal}.
    """

    credentials = None
    mind = None
    interfaces = None

    def login(self, credentials, mind, *interfaces):
        self.credentials = credentials
        self.mind = mind
        self.interfaces = interfaces
        return MockDefer()


class FTPTests(unittest.SynchronousTestCase):
    """
    Test L{twisted.protocols.ftp}, using the C{MockPortal} wrapper.
    """

    def test_ftpPassCredentialsUsingBytes(self):
        """
        C{FTP} constructs a L{twisted.cred.credentials.UsernamePassword} with byte encoded
        username and passwords.
        """
        proto = ftp.FTP()
        proto.factory = ftp.FTPFactory()
        proto.factory.allowAnonymous = False
        proto.portal = MockPortal()
        proto._user = "username"

        # execution
        proto.ftp_PASS("password")

        # validation
        self.assertIsInstance(proto.portal.credentials.username, bytes)
        self.assertIsInstance(proto.portal.credentials.password, bytes)
