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
from twisted.application import service, compat, internet
from twisted.protocols import wire, basic
from twisted.internet import protocol, reactor
import os, pickle

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

    def testCalling(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        c.listenTCP(None, None)
        c.listenSSL(None, None, None)
        c.listenUDP(None, None)
        c.listenUNIX(None, None)
        c.connectTCP(None, None, None)
        c.connectSSL(None, None, None, None)
        c.connectUDP(None, None, None)
        c.connectUNIX(None, None)

    def testUnlistenersCallable(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        self.assert_(callable(c.unlistenTCP))
        self.assert_(callable(c.unlistenUNIX))
        self.assert_(callable(c.unlistenUDP))
        self.assert_(callable(c.unlistenSSL))

    def testServices(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        ch = service.Service()
        ch.setName("lala")
        ch.setServiceParent(c)
        self.assertEqual(c.getServiceNamed("lala"), ch)
        ch.disownServiceParent()

class Dummy:
    processName = None
    

class TestConvert(unittest.TestCase):

    def testSimpleInternet(self):
        s = "(dp0\nS'udpConnectors'\np1\n(lp2\nsS'unixConnectors'\np3\n(lp4\nsS'twisted.internet.app.Application.persistenceVersion'\np5\nI12\nsS'name'\np6\nS'web'\np7\nsS'sslConnectors'\np8\n(lp9\nsS'sslPorts'\np10\n(lp11\nsS'tcpPorts'\np12\n(lp13\n(I8080\n(itwisted.web.server\nSite\np14\n(dp16\nS'resource'\np17\n(itwisted.web.test\nTest\np18\n(dp19\nS'files'\np20\n(lp21\nsS'paths'\np22\n(dp23\nsS'tmpl'\np24\n(lp25\nS'\\n    Congratulations, twisted.web appears to work!\\n    <ul>\\n    <li>Funky Form:\\n    '\np26\naS'self.funkyForm()'\np27\naS'\\n    <li>Exception Handling:\\n    '\np28\naS'self.raiseHell()'\np29\naS'\\n    </ul>\\n    '\np30\nasS'widgets'\np31\n(dp32\nsS'variables'\np33\n(dp34\nsS'modules'\np35\n(lp36\nsS'children'\np37\n(dp38\nsbsS'logPath'\np39\nNsS'timeOut'\np40\nI43200\nsS'sessions'\np41\n(dp42\nsbI5\nS''\np43\ntp44\nasS'unixPorts'\np45\n(lp46\nsS'services'\np47\n(dp48\nsS'gid'\np49\nI1000\nsS'tcpConnectors'\np50\n(lp51\nsS'extraConnectors'\np52\n(lp53\nsS'udpPorts'\np54\n(lp55\nsS'extraPorts'\np56\n(lp57\nsS'persistStyle'\np58\nS'pickle'\np59\nsS'uid'\np60\nI1000\ns."
        d = pickle.loads(s)
        a = Dummy()
        a.__dict__ = d
        appl = compat.convert(a)
        self.assertEqual(service.IProcess(appl).uid, 1000)
        self.assertEqual(service.IProcess(appl).gid, 1000)
        self.assertEqual(service.IService(appl).name, "web")
        services = list(service.IServiceCollection(appl))
        self.assertEqual(len(services), 1)
        s = services[0]
        self.assertEqual(s.parent, service.IServiceCollection(appl))
        self.assert_(s.privileged)
        self.assert_(isinstance(s, internet.TCPServer))
        args = s.args
        self.assertEqual(args[0], 8080)
        args[1].resource.template
        self.assertEqual(args[3], '')
