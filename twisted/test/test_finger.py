# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest
from twisted.protocols import finger
from twisted.internet import reactor, protocol
from twisted.test.proto_helpers import StringTransport


class FingerTestCase(unittest.TestCase):

    def setUp(self):
        self.transport = StringTransport()
        self.protocol = finger.Finger()
        self.protocol.makeConnection(self.transport)

    def testSimple(self):
        self.protocol.dataReceived("moshez\r\n")
        self.assertEqual(
            self.transport.value(),
            "Login: moshez\nNo such user\n")

    def testSimpleW(self):
        self.protocol.dataReceived("/w moshez\r\n")
        self.assertEqual(
            self.transport.value(),
            "Login: moshez\nNo such user\n")

    def testForwarding(self):
        self.protocol.dataReceived("moshez@example.com\r\n")
        self.assertEqual(
            self.transport.value(),
            "Finger forwarding service denied\n")

    def testList(self):
        self.protocol.dataReceived("\r\n")
        self.assertEqual(
            self.transport.value(),
            "Finger online list denied\n")
