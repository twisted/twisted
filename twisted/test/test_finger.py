# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
