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

    def testTimer(self):
        l = []
        t = internet.TimerService(1, l.append, "hello")
        t.startService()
        while not l:
            reactor.iterate(0.1)
        t.stopService()
        self.assertEqual(l, ["hello"])
