# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest
from twisted.protocols import finger
from twisted.internet import reactor, protocol
from twisted.test import test_protocols

class FingerTestCase(unittest.TestCase):

    def setUp(self):
        self.t = test_protocols.StringIOWithoutClosing()
        self.p = finger.Finger()
        self.p.makeConnection(protocol.FileWrapper(self.t))

    def testSimple(self):
        self.p.dataReceived("moshez\r\n")
        self.failUnlessEqual(self.t.getvalue(),
                             "Login: moshez\nNo such user\n")

    def testSimpleW(self):
        self.p.dataReceived("/w moshez\r\n")
        self.failUnlessEqual(self.t.getvalue(),
                             "Login: moshez\nNo such user\n")

    def testForwarding(self):
        self.p.dataReceived("moshez@example.com\r\n")
        self.failUnlessEqual(self.t.getvalue(),
                             "Finger forwarding service denied\n")

    def testList(self):
        self.p.dataReceived("\r\n")
        self.failUnlessEqual(self.t.getvalue(),
                             "Finger online list denied\n")
