# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.protocols.finger}.
"""

from twisted.trial import unittest
from twisted.protocols import finger
from twisted.test.proto_helpers import StringTransport


class FingerTests(unittest.TestCase):
    """
    Tests for L{finger.Finger}.
    """
    def setUp(self):
        """
        Create and connect a L{finger.Finger} instance.
        """
        self.transport = StringTransport()
        self.protocol = finger.Finger()
        self.protocol.makeConnection(self.transport)


    def test_simple(self):
        """
        When L{finger.Finger} receives a CR LF terminated line, it responds
        with the default user status message - that no such user exists.
        """
        self.protocol.dataReceived("moshez\r\n")
        self.assertEqual(
            self.transport.value(),
            "Login: moshez\nNo such user\n")


    def test_simpleW(self):
        """
        The behavior for a query which begins with C{"/w"} is the same as the
        behavior for one which does not.  The user is reported as not existing.
        """
        self.protocol.dataReceived("/w moshez\r\n")
        self.assertEqual(
            self.transport.value(),
            "Login: moshez\nNo such user\n")


    def test_forwarding(self):
        """
        When L{finger.Finger} receives a request for a remote user, it responds
        with a message rejecting the request.
        """
        self.protocol.dataReceived("moshez@example.com\r\n")
        self.assertEqual(
            self.transport.value(),
            "Finger forwarding service denied\n")


    def test_list(self):
        """
        When L{finger.Finger} receives a blank line, it responds with a message
        rejecting the request for all online users.
        """
        self.protocol.dataReceived("\r\n")
        self.assertEqual(
            self.transport.value(),
            "Finger online list denied\n")
