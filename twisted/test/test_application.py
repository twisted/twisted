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
from twisted.application import service, compat, internet, app
from twisted.persisted import sob
from twisted.python import components
from twisted.python import log
from twisted.python.runtime import platformType
from twisted.internet import utils, interfaces, defer
from twisted.protocols import wire, basic
from twisted.internet import protocol, reactor
import copy, os, pickle, sys

class Dummy:
    processName=None

class TestService(unittest.TestCase):

    def testName(self):
        s = service.Service()
        s.setName("hello")
        self.failUnlessEqual(s.name, "hello")

    def testParent(self):
        s = service.Service()
        p = service.MultiService()
        s.setServiceParent(p)
        self.failUnlessEqual(list(p), [s])
        self.failUnlessEqual(s.parent, p)

    def testApplicationAsParent(self):
        s = service.Service()
        p = service.Application("")
        s.setServiceParent(p)
        self.failUnlessEqual(list(service.IServiceCollection(p)), [s])
        self.failUnlessEqual(s.parent, service.IServiceCollection(p))

    def testNamedChild(self):
        s = service.Service()
        p = service.MultiService()
        s.setName("hello")
        s.setServiceParent(p)
        self.failUnlessEqual(list(p), [s])
        self.failUnlessEqual(s.parent, p)
        self.failUnlessEqual(p.getServiceNamed("hello"), s)

    def testDoublyNamedChild(self):
        s = service.Service()
        p = service.MultiService()
        s.setName("hello")
        s.setServiceParent(p)
        self.failUnlessRaises(RuntimeError, s.setName, "lala")

    def testDuplicateNamedChild(self):
        s = service.Service()
        p = service.MultiService()
        s.setName("hello")
        s.setServiceParent(p)
        s = service.Service()
        s.setName("hello")
        self.failUnlessRaises(RuntimeError, s.setServiceParent, p)

    def testDisowning(self):
        s = service.Service()
        p = service.MultiService()
        s.setServiceParent(p)
        self.failUnlessEqual(list(p), [s])
        self.failUnlessEqual(s.parent, p)
        s.disownServiceParent()
        self.failUnlessEqual(list(p), [])
        self.failUnlessEqual(s.parent, None)

    def testRunning(self):
        s = service.Service()
        self.assert_(not s.running)
        s.startService()
        self.assert_(s.running)
        s.stopService()
        self.assert_(not s.running)

    def testRunningChildren(self):
        s = service.Service()
        p = service.MultiService()
        s.setServiceParent(p)
        self.assert_(not s.running)
        self.assert_(not p.running)
        p.startService()
        self.assert_(s.running)
        self.assert_(p.running)
        p.stopService()
        self.assert_(not s.running)
        self.assert_(not p.running)

    def testRunningChildren(self):
        s = service.Service()
        def checkRunning():
            self.assert_(s.running)
        t = service.Service()
        t.stopService = checkRunning
        t.startService = checkRunning
        p = service.MultiService()
        s.setServiceParent(p)
        t.setServiceParent(p)
        p.startService()
        p.stopService()

    def testAddingIntoRunning(self):
        p = service.MultiService()
        p.startService()
        s = service.Service()
        self.assert_(not s.running)
        s.setServiceParent(p)
        self.assert_(s.running)
        s.disownServiceParent()
        self.assert_(not s.running)

    def testPrivileged(self):
        s = service.Service()
        def pss():
            s.privilegedStarted = 1
        s.privilegedStartService = pss
        s1 = service.Service()
        p = service.MultiService()
        s.setServiceParent(p)
        s1.setServiceParent(p)
        p.privilegedStartService()
        self.assert_(s.privilegedStarted)

    def testCopying(self):
        s = service.Service()
        s.startService()
        s1 = copy.copy(s)
        self.assert_(not s1.running)
        self.assert_(s.running)


if hasattr(os, "getuid"):
    curuid = os.getuid()
    curgid = os.getgid()
else:
    curuid = curgid = 0


class TestProcess(unittest.TestCase):

    def testID(self):
        p = service.Process(5, 6)
        self.assertEqual(p.uid, 5)
        self.assertEqual(p.gid, 6)

    def testDefaults(self):
        p = service.Process(5)
        self.assertEqual(p.uid, 5)
        self.assertEqual(p.gid, curgid)
        p = service.Process(gid=5)
        self.assertEqual(p.uid, curuid)
        self.assertEqual(p.gid, 5)
        p = service.Process()
        self.assertEqual(p.uid, curuid)
        self.assertEqual(p.gid, curgid)

    def testProcessName(self):
        p = service.Process()
        self.assertEqual(p.processName, None)
        p.processName = 'hello'
        self.assertEqual(p.processName, 'hello')


class TestInterfaces(unittest.TestCase):

    def testService(self):
        self.assert_(components.implements(service.Service(),
                                           service.IService))

    def testMultiService(self):
        self.assert_(components.implements(service.MultiService(),
                                           service.IService))
        self.assert_(components.implements(service.MultiService(),
                                           service.IServiceCollection))

    def testProcess(self):
        self.assert_(components.implements(service.Process(),
                                           service.IProcess))


class TestApplication(unittest.TestCase):

    def testConstructor(self):
        service.Application("hello")
        service.Application("hello", 5)
        service.Application("hello", 5, 6)

    def testProcessComponent(self):
        a = service.Application("hello")
        self.assertEqual(service.IProcess(a).uid, curuid)
        self.assertEqual(service.IProcess(a).gid, curgid)
        a = service.Application("hello", 5)
        self.assertEqual(service.IProcess(a).uid, 5)
        self.assertEqual(service.IProcess(a).gid, curgid)
        a = service.Application("hello", 5, 6)
        self.assertEqual(service.IProcess(a).uid, 5)
        self.assertEqual(service.IProcess(a).gid, 6)

    def testServiceComponent(self):
        a = service.Application("hello")
        self.assert_(service.IService(a) is service.IServiceCollection(a))
        self.assertEqual(service.IService(a).name, "hello")
        self.assertEqual(service.IService(a).parent, None)

    def testPersistableComponent(self):
        a = service.Application("hello")
        p = sob.IPersistable(a)
        self.assertEqual(p.style, 'pickle')
        self.assertEqual(p.name, 'hello')
        self.assert_(p.original is a)

class TestLoading(unittest.TestCase):

    def test_simpleStoreAndLoad(self):
        a = service.Application("hello")
        p = sob.IPersistable(a)
        for style in 'xml source pickle'.split():
            p.setStyle(style)
            p.save()
            a1 = service.loadApplication("hello.ta"+style[0], style)
            self.assertEqual(service.IService(a1).name, "hello")
        open("hello.tac", 'w').writelines([
        "from twisted.application import service\n",
        "application = service.Application('hello')\n",
        ])
        a1 = service.loadApplication("hello.tac", 'python')
        self.assertEqual(service.IService(a1).name, "hello")

    def test_implicitConversion(self):
        a = Dummy()
        a.__dict__ = {'udpConnectors': [], 'unixConnectors': [],
                      '_listenerDict': {}, 'name': 'dummy',
                      'sslConnectors': [], 'unixPorts': [],
                      '_extraListeners': {}, 'sslPorts': [], 'tcpPorts': [],
                      'services': {}, 'gid': 0, 'tcpConnectors': [],
                      'extraConnectors': [], 'udpPorts': [], 'extraPorts': [],
                      'uid': 0}
        pickle.dump(a, open("file.tap", 'wb'))
        a1 = service.loadApplication("file.tap", "pickle", None)
        self.assertEqual(service.IService(a1).name, "dummy")
        self.assertEqual(list(service.IServiceCollection(a1)), [])


class TestAppSupport(unittest.TestCase):

    def testPassphrase(self):
        self.assertEqual(app.getPassphrase(0), None)

    def testLoadApplication(self):
        a = service.Application("hello")
        baseconfig = {'file': None, 'xml': None, 'source': None, 'python':None}
        for style in 'source xml pickle'.split():
            config = baseconfig.copy()
            config[{'pickle': 'file'}.get(style, style)] = 'helloapplication'
            sob.IPersistable(a).setStyle(style)
            sob.IPersistable(a).save(filename='helloapplication')
            a1 = app.getApplication(config, None)
            self.assertEqual(service.IService(a1).name, "hello")
        config = baseconfig.copy()
        config['python'] = 'helloapplication'
        open("helloapplication", 'w').writelines([
        "from twisted.application import service\n",
        "application = service.Application('hello')\n",
        ])
        a1 = app.getApplication(config, None)
        self.assertEqual(service.IService(a1).name, "hello")

    def test_convertStyle(self):
        appl = service.Application("lala")
        for instyle in 'xml source pickle'.split():
            for outstyle in 'xml source pickle'.split():
                sob.IPersistable(appl).setStyle(instyle)
                sob.IPersistable(appl).save(filename="converttest")
                app.convertStyle("converttest", instyle, None,
                                 "converttest.out", outstyle, 0)
                appl2 = service.loadApplication("converttest.out", outstyle)
                self.assertEqual(service.IService(appl2).name, "lala")

    def test_getLogFile(self):
        os.mkdir("logfiledir")
        l = app.getLogFile(os.path.join("logfiledir", "lala"))
        self.assertEqual(l.path,
                         os.path.abspath(os.path.join("logfiledir", "lala")))
        self.assertEqual(l.name, "lala")
        self.assertEqual(l.directory, os.path.abspath("logfiledir"))

    def test_startApplication(self):
        appl = service.Application("lala")
        app.startApplication(appl, 0)
        self.assert_(service.IService(appl).running)

class TestInternet(unittest.TestCase):

    def testUNIX(self):
        if not components.implements(reactor, interfaces.IReactorUNIX):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
        s = service.MultiService()
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
        s.privilegedStartService()
        s.startService()
        while factory.line is None:
            reactor.iterate(0.1)
        s.stopService()
        self.assertEqual(factory.line, 'lalala')

    def testTCP(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        c.listenTCP(0, factory)
        s.privilegedStartService()
        s.startService()
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
        c.listenWith(None)
        self.assertEqual(list(s)[0].args[0], None)
        c.listenTCP(None, None)
        self.assertEqual(list(s)[1].args[:2], (None,)*2)
        c.listenSSL(None, None, None)
        self.assertEqual(list(s)[2].args[:3], (None,)*3)
        c.listenUDP(None, None)
        self.assertEqual(list(s)[3].args[:2], (None,)*2)
        c.listenUNIX(None, None)
        self.assertEqual(list(s)[4].args[:2], (None,)*2)
        for ch in s:
            self.assert_(ch.privileged)
        c.connectWith(None)
        self.assertEqual(list(s)[5].args[0], None)
        c.connectTCP(None, None, None)
        self.assertEqual(list(s)[6].args[:3], (None,)*3)
        c.connectSSL(None, None, None, None)
        self.assertEqual(list(s)[7].args[:4], (None,)*4)
        c.connectUDP(None, None, None)
        self.assertEqual(list(s)[8].args[:3], (None,)*3)
        c.connectUNIX(None, None)
        self.assertEqual(list(s)[9].args[:2], (None,)*2)
        self.assertEqual(len(list(s)), 10)
        for ch in s:
            self.failIf(ch.kwargs)
            self.assertEqual(ch.name, None)

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
        self.assertEqual(list(s), [])

    def testInterface(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        for key in compat.IOldApplication.__dict__.keys():
            if callable(getattr(compat.IOldApplication, key)):
                self.assert_(callable(getattr(c, key)))


class DummyApp:
    processName = None
    def addService(self, service):
        self.services[service.name] = service
    def removeService(self, service):
        del self.services[service.name]


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
        self.assertEqual(args[3], '')

    def testSimpleUNIX(self):
        if not components.implements(reactor, interfaces.IReactorUNIX):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
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

    def testSimpleService(self):
        a = DummyApp()
        a.__dict__ = {'udpConnectors': [], 'unixConnectors': [],
                      '_listenerDict': {}, 'name': 'dummy',
                      'sslConnectors': [], 'unixPorts': [],
                      '_extraListeners': {}, 'sslPorts': [], 'tcpPorts': [],
                      'services': {}, 'gid': 0, 'tcpConnectors': [],
                      'extraConnectors': [], 'udpPorts': [], 'extraPorts': [],
                      'uid': 0}
        s = service.Service()
        s.setName("lala")
        s.setServiceParent(a)
        appl = compat.convert(a)
        services = list(service.IServiceCollection(appl))
        self.assertEqual(len(services), 1)
        s1 = services[0]
        self.assertEqual(s, s1)

class TestInternet2(unittest.TestCase):

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

    def testUDP(self):
        if not components.implements(reactor, interfaces.IReactorUDP):
            raise unittest.SkipTest, "This reactor does not support UDP sockets"
        p = protocol.DatagramProtocol()
        t = internet.TCPServer(0, p)
        t.startService()
        num = t._port.getHost()[2]
        l = []
        defer.maybeDeferred(t.stopService).addCallback(l.append)
        while not l:
            reactor.iterate(0.1)
        t = internet.TCPServer(num, p)
        t.startService()
        l = []
        defer.maybeDeferred(t.stopService).addCallback(l.append)
        while not l:
            reactor.iterate(0.1)

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
        if not components.implements(reactor, interfaces.IReactorUNIX):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
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
        d = s.stopService()
        l = []
        d.addCallback(l.append)
        while not l:
            reactor.iterate(0.1)
        factory.line = None
        s.startService()
        while factory.line is None:
            reactor.iterate(0.1)
        self.assertEqual(factory.line, 'lalala')
        d = s.stopService()
        l = []
        d.addCallback(l.append)
        while not l:
            reactor.iterate(0.1)

    def testVolatile(self):
        if not components.implements(reactor, interfaces.IReactorUNIX):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
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
        self.failIf(t.running)

    def testStoppingServer(self):
        if not components.implements(reactor, interfaces.IReactorUNIX):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.UNIXServer('echo.skt', factory)
        t.startService()
        t.stopService()
        self.failIf(t.running)
        factory = protocol.ClientFactory()
        l = []
        factory.clientConnectionFailed = lambda *args: l.append(None)
        reactor.connectUNIX('echo.skt', factory)
        while not l:
            reactor.iterate(0.1)
        self.assertEqual(l, [None])

    def testTimer(self):
        l = []
        t = internet.TimerService(1, l.append, "hello")
        t.startService()
        while not l:
            reactor.iterate(0.1)
        t.stopService()
        self.failIf(t.running)
        self.assertEqual(l, ["hello"])
        l = []
        t = internet.TimerService(0.01, l.append, "hello")
        t.startService()
        while len(l)<10:
            reactor.iterate(0.1)
        t.stopService()
        self.assertEqual(l, ["hello"]*10)

    def testBrokenTimer(self):
        t = internet.TimerService(1, lambda: 1 / 0)
        t.startService()
        while t.loop is not None:
            reactor.iterate(0.1)
        t.stopService()
        self.assertEquals([ZeroDivisionError],
                          [o.value.__class__ for o in log.flushErrors(ZeroDivisionError)])

    def testEverythingThere(self):
        trans = 'TCP UNIX SSL UDP UNIXDatagram Multicast'.split()
        for tran in trans[:]:
            if not components.implements(reactor, getattr(interfaces, "IReactor"+tran)):
                trans.remove(tran)
        if components.implements(reactor, interfaces.IReactorArbitrary):
            trans.insert(0, "Generic")
        for tran in trans:
            for side in 'Server Client'.split():
                self.assert_(hasattr(internet, tran+side))
                method = getattr(internet, tran+side).method
                prefix = {'Server': 'listen', 'Client': 'connect'}[side]
                self.assert_(hasattr(reactor, prefix+method) or
                        (prefix == "connect" and method == "UDP"))
                o = getattr(internet, tran+side)()
                self.assertEqual(service.IService(o), o)


class TestCompat(unittest.TestCase):

    def testService(self):
        # test old services with new application
        s = service.MultiService()
        c = compat.IOldApplication(s)
        from twisted.internet.app import ApplicationService
        svc = ApplicationService("foo", serviceParent=c)
        self.assertEquals(c.getServiceNamed("foo"), svc)
        self.assertEquals(s.getServiceNamed("foo").name, "foo")
        c.removeService(svc)

    def testOldApplication(self):
        from twisted.internet import app as oapp
        application = oapp.Application("HELLO")
        oapp.MultiService("HELLO", application)
        compat.convert(application)

"""
if not components.implements(reactor, interfaces.IReactorUNIX):
    unixmethods = [TestInternet.testUNIX, TestConvert.testSimpleUNIX, \
        TestInternet2.testUNIX, TestInternet2.testVolatile, TestInternet2.testStoppingServer]
    for m in unixmethods:
        m.im_func.skip = "This reactor does not support UNIX domain sockets"
    del unixmethods # what's this good for?
if not components.implements(reactor, interfaces.IReactorUDP):
    TestInternet2.testUDP.im_func.skip = "This reactor does not support UDP"
"""
