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

    def testSimpleUNIX(self):
        s = "(dp0\nS'udpConnectors'\np1\n(lp2\nsS'unixConnectors'\np3\n(lp4\nsS'twisted.internet.app.Application.persistenceVersion'\np5\nI12\nsS'name'\np6\nS'web'\np7\nsS'sslConnectors'\np8\n(lp9\nsS'sslPorts'\np10\n(lp11\nsS'tcpPorts'\np12\n(lp13\nsS'unixPorts'\np14\n(lp15\n(S'/home/moshez/.twistd-web-pb'\np16\n(itwisted.spread.pb\nBrokerFactory\np17\n(dp19\nS'objectToBroker'\np20\n(itwisted.web.distrib\nResourcePublisher\np21\n(dp22\nS'twisted.web.distrib.ResourcePublisher.persistenceVersion'\np23\nI2\nsS'site'\np24\n(itwisted.web.server\nSite\np25\n(dp26\nS'resource'\np27\n(itwisted.web.static\nFile\np28\n(dp29\nS'ignoredExts'\np30\n(lp31\nsS'defaultType'\np32\nS'text/html'\np33\nsS'registry'\np34\n(itwisted.web.static\nRegistry\np35\n(dp36\nS'twisted.web.static.Registry.persistenceVersion'\np37\nI1\nsS'twisted.python.components.Componentized.persistenceVersion'\np38\nI1\nsS'_pathCache'\np39\n(dp40\nsS'_adapterCache'\np41\n(dp42\nS'twisted.internet.interfaces.IServiceCollection'\np43\n(itwisted.internet.app\nApplication\np44\n(dp45\ng1\ng2\nsg3\ng4\nsg5\nI12\nsg6\ng7\nsg8\ng9\nsg10\ng11\nsg12\ng13\nsg14\ng15\nsS'extraPorts'\np46\n(lp47\nsS'gid'\np48\nI1053\nsS'tcpConnectors'\np49\n(lp50\nsS'extraConnectors'\np51\n(lp52\nsS'udpPorts'\np53\n(lp54\nsS'services'\np55\n(dp56\nsS'persistStyle'\np57\nS'pickle'\np58\nsS'delayeds'\np59\n(lp60\nsS'uid'\np61\nI1053\nsbssbsS'encoding'\np62\nNsS'twisted.web.static.File.persistenceVersion'\np63\nI6\nsS'path'\np64\nS'/home/moshez/public_html.twistd'\np65\nsS'type'\np66\ng33\nsS'children'\np67\n(dp68\nsS'processors'\np69\n(dp70\nS'.php3'\np71\nctwisted.web.twcgi\nPHP3Script\np72\nsS'.rpy'\np73\nctwisted.web.script\nResourceScript\np74\nsS'.php'\np75\nctwisted.web.twcgi\nPHPScript\np76\nsS'.cgi'\np77\nctwisted.web.twcgi\nCGIScript\np78\nsS'.epy'\np79\nctwisted.web.script\nPythonScript\np80\nsS'.trp'\np81\nctwisted.web.trp\nResourceUnpickler\np82\nssbsS'logPath'\np83\nNsS'sessions'\np84\n(dp85\nsbsbsS'twisted.spread.pb.BrokerFactory.persistenceVersion'\np86\nI3\nsbI5\nI438\ntp87\nasg55\ng56\nsg48\nI1053\nsg49\ng50\nsg51\ng52\nsg53\ng54\nsg46\ng47\nsg57\ng58\nsg61\nI1053\nsg59\ng60\ns."
        d = pickle.loads(s)
        a = Dummy()
        a.__dict__ = d
        appl = compat.convert(a)
        self.assertEqual(service.IProcess(appl).uid, 1053)
        self.assertEqual(service.IProcess(appl).gid, 1053)
        self.assertEqual(service.IService(appl).name, "web")
        services = list(service.IServiceCollection(appl))
        self.assertEqual(len(services), 1)
        s = services[0]
        self.assertEqual(s.parent, service.IServiceCollection(appl))
        self.assert_(s.privileged)
        self.assert_(isinstance(s, internet.UNIXServer))
        args = s.args
        self.assertEqual(args[0], '/home/moshez/.twistd-web-pb')
