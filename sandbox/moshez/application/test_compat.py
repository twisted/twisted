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
from twisted.application import service, compat
from twisted.protocols import wire, basic
from twisted.internet import protocol, reactor
import os

class TestInternet(unittest.TestCase):

    def testUNIX(self):
        s = service.MultiService()
        s.startService()
        c = compat.IOldApplication(s)
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        if os.path.exists('.hello.skt'):
            os.remove('hello.skt')
        c.listenUNIX('./hello.skt', factory)
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        c.connectUNIX('./hello.skt', factory)
        while factory.line is None:
            reactor.iterate(0.1)
        s.stopService()
        self.assertEqual(factory.line, 'lalala')

    def testTCP(self):
        s = service.MultiService()
        s.startService()
        c = compat.IOldApplication(s)
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        c.listenTCP(0, factory)
        num = list(s)[0]._port.getHost()[2]
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        c.connectTCP('localhost', num, factory)
        while factory.line is None:
            reactor.iterate(0.1)
        s.stopService()
        self.assertEqual(factory.line, 'lalala')

    def testServices(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        ch = service.Service()
        ch.setName("lala")
        ch.setServiceParent(c)
        self.assertEqual(c.getServiceNamed("lala"), ch)
        ch.disownServiceParent()
