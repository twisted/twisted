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

"""
Test cases for twisted.internet.app.
"""

from twisted.trial import unittest
from twisted.internet import app, protocol, error


class AppTestCase(unittest.TestCase):

    def testListenUnlistenTCP(self):
        a = app.Application("foo")
        f = protocol.ServerFactory()
        a.listenTCP(9999, f)
        a.listenTCP(9998, f)
        self.assertEquals(len(a.tcpPorts), 2)
        a.unlistenTCP(9999)
        self.assertEquals(len(a.tcpPorts), 1)
        a.listenTCP(9999, f, interface='127.0.0.1')
        self.assertEquals(len(a.tcpPorts), 2)
        a.unlistenTCP(9999, '127.0.0.1')
        self.assertEquals(len(a.tcpPorts), 1)
        a.unlistenTCP(9998)
        self.assertEquals(len(a.tcpPorts), 0)

    def testListenUnlistenUDP(self):
        a = app.Application("foo")
        f = protocol.DatagramProtocol()
        a.listenUDP(9999, f)
        a.listenUDP(9998, f)
        self.assertEquals(len(a.udpPorts), 2)
        a.unlistenUDP(9999)
        self.assertEquals(len(a.udpPorts), 1)
        a.listenUDP(9999, f, interface='127.0.0.1')
        self.assertEquals(len(a.udpPorts), 2)
        a.unlistenUDP(9999, '127.0.0.1')
        self.assertEquals(len(a.udpPorts), 1)
        a.unlistenUDP(9998)
        self.assertEquals(len(a.udpPorts), 0)

    def testListenUnlistenUNIX(self):
        a = app.Application("foo")
        f = protocol.ServerFactory()
        a.listenUNIX("xxx", f)
        self.assertEquals(len(a.unixPorts), 1)
        a.unlistenUNIX("xxx")
        self.assertEquals(len(a.unixPorts), 0)

    def testIllegalUnlistens(self):
        a = app.Application("foo")

        self.assertRaises(error.NotListeningError, a.unlistenTCP, 1010)
        self.assertRaises(error.NotListeningError, a.unlistenUNIX, '1010')
        self.assertRaises(error.NotListeningError, a.unlistenSSL, 1010)
        self.assertRaises(error.NotListeningError, a.unlistenUDP, 1010)

class ServiceTestCase(unittest.TestCase):

    def testRegisterService(self):
        a = app.Application("foo")
        svc = app.ApplicationService("service", a)
        self.assertEquals(a.getServiceNamed("service"), svc)
        self.assertEquals(a, svc.serviceParent)
