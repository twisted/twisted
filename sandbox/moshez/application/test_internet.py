# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#
from twisted.trial import unittest
from twisted.application import service, internet
from twisted.protocols import wire, basic
from twisted.internet import protocol, reactor
import copy

class TestInternet(unittest.TestCase):

    def testTCP(self):
        s = service.MultiService()
        s.startService()
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.TCPServer(0, factory)
        t.setServiceParent(s)
        num = t._port.getHost()[2]
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        internet.TCPClient('localhost', num, factory).setServiceParent(s)
        while factory.line is None:
            reactor.iterate(0.1)
        self.assertEqual(factory.line, 'lalala')

    def testPrivileged(self):
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.TCPServer(0, factory)
        t.privileged = 1
        t.privilegedStartService()
        num = t._port.getHost()[2]
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        internet.TCPClient('localhost', num, factory).startService()
        while factory.line is None:
            reactor.iterate(0.1)
        self.assertEqual(factory.line, 'lalala')

    def testConnectionGettingRefused(self):
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.TCPServer(0, factory)
        t.startService()
        num = t._port.getHost()[2]
        t.stopService()
        l = []
        factory = protocol.ClientFactory()
        factory.clientConnectionFailed = lambda *args: l.append(None)
        c = internet.TCPClient('localhost', num, factory)
        c.startService()
        while not l:
            reactor.iterate(0.1)
        self.assertEqual(l, [None])

    def testUNIX(self):
        s = service.MultiService()
        s.startService()
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.UNIXServer('echo.skt', factory)
        t.setServiceParent(s)
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        internet.UNIXClient('echo.skt', factory).setServiceParent(s)
        while factory.line is None:
            reactor.iterate(0.1)
        self.assertEqual(factory.line, 'lalala')
        s.stopService()

    def testVolatile(self):
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.UNIXServer('echo.skt', factory)
        t.startService()
        self.assert_(hasattr(t, '_port'))
        t1 = copy.copy(t)
        self.assert_(not hasattr(t1, '_port'))
        t.stopService()
        t = internet.TimerService(1, lambda:None)
        t.startService()
        self.assert_(hasattr(t, '_call'))
        t1 = copy.copy(t)
        self.assert_(not hasattr(t1, '_call'))
        t.stopService()
        factory = protocol.ClientFactory()
        factory.protocol = wire.Echo
        t = internet.UNIXClient('echo.skt', factory)
        t.startService()
        self.assert_(hasattr(t, '_connection'))
        t1 = copy.copy(t)
        self.assert_(not hasattr(t1, '_connection'))
        t.stopService()

    def testTimer(self):
        l = []
        t = internet.TimerService(1, l.append, "hello")
        t.startService()
        while not l:
            reactor.iterate(0.1)
        t.stopService()
        self.assertEqual(l, ["hello"])
