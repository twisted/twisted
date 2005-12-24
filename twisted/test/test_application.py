# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
from twisted.trial import unittest, util
from twisted.application import service, compat, internet, app
from twisted.persisted import sob
from twisted.python import components
from twisted.python import log
from twisted.python.runtime import platformType
from twisted.internet import utils, interfaces, defer
from twisted.protocols import wire, basic
from twisted.internet import protocol, reactor
import copy, os, pickle, sys, warnings

try:
    from twisted.web import microdom
    gotMicrodom = True
except ImportError:
    import warnings
    warnings.warn("Not testing xml persistence as twisted.web.microdom "
                  "not available")
    gotMicrodom = False


oldAppSuppressions = [util.suppress(message='twisted.internet.app is deprecated',
                                    category=DeprecationWarning)]

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
        self.assertEqual(p.gid, None)
        p = service.Process(gid=5)
        self.assertEqual(p.uid, None)
        self.assertEqual(p.gid, 5)
        p = service.Process()
        self.assertEqual(p.uid, None)
        self.assertEqual(p.gid, None)

    def testProcessName(self):
        p = service.Process()
        self.assertEqual(p.processName, None)
        p.processName = 'hello'
        self.assertEqual(p.processName, 'hello')


class TestInterfaces(unittest.TestCase):

    def testService(self):
        self.assert_(service.IService.providedBy(service.Service()))

    def testMultiService(self):
        self.assert_(service.IService.providedBy(service.MultiService()))
        self.assert_(service.IServiceCollection.providedBy(service.MultiService()))

    def testProcess(self):
        self.assert_(service.IProcess.providedBy(service.Process()))


class TestApplication(unittest.TestCase):

    def testConstructor(self):
        service.Application("hello")
        service.Application("hello", 5)
        service.Application("hello", 5, 6)

    def testProcessComponent(self):
        a = service.Application("hello")
        self.assertEqual(service.IProcess(a).uid, None)
        self.assertEqual(service.IProcess(a).gid, None)
        a = service.Application("hello", 5)
        self.assertEqual(service.IProcess(a).uid, 5)
        self.assertEqual(service.IProcess(a).gid, None)
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
            if style == 'xml' and not gotMicrodom:
                continue
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
            if style == 'xml' and not gotMicrodom:
                continue
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
            if instyle == 'xml' and not gotMicrodom:
                continue
            for outstyle in 'xml source pickle'.split():
                if outstyle == 'xml' and not gotMicrodom:
                    continue
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
        if not interfaces.IReactorUNIX(reactor, None):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
        s = service.MultiService()
        c = compat.IOldApplication(s)
        factory = protocol.ServerFactory()
        factory.protocol = TestEcho
        TestEcho.d = defer.Deferred()
        if os.path.exists('.hello.skt'):
            os.remove('hello.skt')
        c.listenUNIX('./hello.skt', factory)
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
                self.transport.loseConnection()
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        c.connectUNIX('./hello.skt', factory)
        s.privilegedStartService()
        s.startService()
        util.spinWhile(lambda :factory.line is None)
        util.wait(defer.maybeDeferred(s.stopService))
        self.assertEqual(factory.line, 'lalala')

        # Cleanup the reactor
        util.wait(TestEcho.d)
    testUNIX.suppress = oldAppSuppressions

    def testTCP(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        factory = protocol.ServerFactory()
        factory.protocol = TestEcho
        TestEcho.d = defer.Deferred()
        c.listenTCP(0, factory)
        s.privilegedStartService()
        s.startService()
        num = list(s)[0]._port.getHost().port
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
                self.transport.loseConnection()
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        c.connectTCP('127.0.0.1', num, factory)
        util.spinWhile(lambda :factory.line is None)
        util.wait(defer.maybeDeferred(s.stopService))
        self.assertEqual(factory.line, 'lalala')

        # Cleanup the reactor
        util.wait(TestEcho.d)
    testTCP.suppress = oldAppSuppressions

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
    testCalling.suppress = oldAppSuppressions

    def testUnlistenersCallable(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        self.assert_(callable(c.unlistenTCP))
        self.assert_(callable(c.unlistenUNIX))
        self.assert_(callable(c.unlistenUDP))
        self.assert_(callable(c.unlistenSSL))
    testUnlistenersCallable.suppress = oldAppSuppressions

    def testServices(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        ch = service.Service()
        ch.setName("lala")
        ch.setServiceParent(c)
        self.assertEqual(c.getServiceNamed("lala"), ch)
        ch.disownServiceParent()
        self.assertEqual(list(s), [])
    testServices.suppress = oldAppSuppressions

    def testInterface(self):
        s = service.MultiService()
        c = compat.IOldApplication(s)
        for key in compat.IOldApplication.__dict__.keys():
            if callable(getattr(compat.IOldApplication, key)):
                self.assert_(callable(getattr(c, key)))
    testInterface.suppress = oldAppSuppressions

class DummyApp:
    processName = None
    def addService(self, service):
        self.services[service.name] = service
    def removeService(self, service):
        del self.services[service.name]


class TestConvert(unittest.TestCase):

    def testSimpleInternet(self):
        # XXX - replace this test with one that does the same thing, but
        # with no web dependencies.
        if not gotMicrodom:
            raise unittest.SkipTest("Need twisted.web to run this test.")
        s = "(dp0\nS'udpConnectors'\np1\n(lp2\nsS'unixConnectors'\np3\n(lp4\nsS'twisted.internet.app.Application.persistenceVersion'\np5\nI12\nsS'name'\np6\nS'web'\np7\nsS'sslConnectors'\np8\n(lp9\nsS'sslPorts'\np10\n(lp11\nsS'tcpPorts'\np12\n(lp13\n(I8080\n(itwisted.web.server\nSite\np14\n(dp16\nS'resource'\np17\n(itwisted.web.demo\nTest\np18\n(dp19\nS'files'\np20\n(lp21\nsS'paths'\np22\n(dp23\nsS'tmpl'\np24\n(lp25\nS'\\n    Congratulations, twisted.web appears to work!\\n    <ul>\\n    <li>Funky Form:\\n    '\np26\naS'self.funkyForm()'\np27\naS'\\n    <li>Exception Handling:\\n    '\np28\naS'self.raiseHell()'\np29\naS'\\n    </ul>\\n    '\np30\nasS'widgets'\np31\n(dp32\nsS'variables'\np33\n(dp34\nsS'modules'\np35\n(lp36\nsS'children'\np37\n(dp38\nsbsS'logPath'\np39\nNsS'timeOut'\np40\nI43200\nsS'sessions'\np41\n(dp42\nsbI5\nS''\np43\ntp44\nasS'unixPorts'\np45\n(lp46\nsS'services'\np47\n(dp48\nsS'gid'\np49\nI1000\nsS'tcpConnectors'\np50\n(lp51\nsS'extraConnectors'\np52\n(lp53\nsS'udpPorts'\np54\n(lp55\nsS'extraPorts'\np56\n(lp57\nsS'persistStyle'\np58\nS'pickle'\np59\nsS'uid'\np60\nI1000\ns."
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
        # XXX - replace this test with one that does the same thing, but
        # with no web dependencies.
        if not interfaces.IReactorUNIX(reactor, None):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
        if not gotMicrodom:
            raise unittest.SkipTest("Need twisted.web to run this test.")
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

class TimerTarget:
    def __init__(self):
        self.l = []
    def append(self, what):
        self.l.append(what)

class TestEcho(wire.Echo):
    def connectionLost(self, reason):
        self.d.callback(True)

class TestInternet2(unittest.TestCase):

    def testTCP(self):
        s = service.MultiService()
        s.startService()
        factory = protocol.ServerFactory()
        factory.protocol = TestEcho
        TestEcho.d = defer.Deferred()
        t = internet.TCPServer(0, factory)
        t.setServiceParent(s)
        num = t._port.getHost().port
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
                self.transport.loseConnection()
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        internet.TCPClient('127.0.0.1', num, factory).setServiceParent(s)
        util.spinWhile(lambda :factory.line is None)
        self.assertEqual(factory.line, 'lalala')

        # Cleanup the reactor
        util.wait(defer.maybeDeferred(s.stopService))
        util.wait(TestEcho.d)

    def testUDP(self):
        if not interfaces.IReactorUDP(reactor, None):
            raise unittest.SkipTest, "This reactor does not support UDP sockets"
        p = protocol.DatagramProtocol()
        t = internet.TCPServer(0, p)
        t.startService()
        num = t._port.getHost().port
        l = []
        defer.maybeDeferred(t.stopService).addCallback(l.append)
        util.spinWhile(lambda :not l)
        t = internet.TCPServer(num, p)
        t.startService()
        l = []
        defer.maybeDeferred(t.stopService).addCallback(l.append)
        util.spinWhile(lambda :not l)

    def testPrivileged(self):
        factory = protocol.ServerFactory()
        factory.protocol = TestEcho
        TestEcho.d = defer.Deferred()
        t = internet.TCPServer(0, factory)
        t.privileged = 1
        t.privilegedStartService()
        num = t._port.getHost().port
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
                self.transport.loseConnection()
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        c = internet.TCPClient('127.0.0.1', num, factory)
        c.startService()
        util.spinWhile(lambda :factory.line is None)
        self.assertEqual(factory.line, 'lalala')

        # Cleanup the reactor
        util.wait(defer.maybeDeferred(c.stopService))
        util.wait(defer.maybeDeferred(t.stopService))
        util.wait(TestEcho.d)

    def testConnectionGettingRefused(self):
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.TCPServer(0, factory)
        t.startService()
        num = t._port.getHost().port
        t.stopService()
        l = []
        factory = protocol.ClientFactory()
        factory.clientConnectionFailed = lambda *args: l.append(None)
        c = internet.TCPClient('127.0.0.1', num, factory)
        c.startService()
        util.spinWhile(lambda :not l)
        self.assertEqual(l, [None])

    def testUNIX(self):
        # FIXME: This test is far too dense.  It needs comments.
        #  -- spiv, 2004-11-07
        if not interfaces.IReactorUNIX(reactor, None):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
        s = service.MultiService()
        s.startService()
        factory = protocol.ServerFactory()
        factory.protocol = TestEcho
        TestEcho.d = defer.Deferred()
        t = internet.UNIXServer('echo.skt', factory)
        t.setServiceParent(s)
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.transport.write('lalala\r\n')
            def lineReceived(self, line):
                self.factory.line = line
                self.transport.loseConnection()
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.line = None
        internet.UNIXClient('echo.skt', factory).setServiceParent(s)
        util.spinWhile(lambda :factory.line is None)
        self.assertEqual(factory.line, 'lalala')
        util.wait(defer.maybeDeferred(s.stopService))
        util.wait(TestEcho.d)

        TestEcho.d = defer.Deferred()
        factory.line = None
        s.startService()
        util.spinWhile(lambda :factory.line is None)
        self.assertEqual(factory.line, 'lalala')

        # Cleanup the reactor
        util.wait(defer.maybeDeferred(s.stopService))
        util.wait(TestEcho.d)

    def testVolatile(self):
        if not interfaces.IReactorUNIX(reactor, None):
            raise unittest.SkipTest, "This reactor does not support UNIX domain sockets"
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.UNIXServer('echo.skt', factory)
        t.startService()
        self.failIfIdentical(t._port, None)
        t1 = copy.copy(t)
        self.assertIdentical(t1._port, None)
        t.stopService()
        self.assertIdentical(t._port, None)
        self.failIf(t.running)

        factory = protocol.ClientFactory()
        factory.protocol = wire.Echo
        t = internet.UNIXClient('echo.skt', factory)
        t.startService()
        self.failIfIdentical(t._connection, None)
        t1 = copy.copy(t)
        self.assertIdentical(t1._connection, None)
        t.stopService()
        self.assertIdentical(t._connection, None)
        self.failIf(t.running)

    def testStoppingServer(self):
        if not interfaces.IReactorUNIX(reactor, None):
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
        util.spinWhile(lambda :not l)
        self.assertEqual(l, [None])

    def testTimer(self):
        l = []
        t = internet.TimerService(1, l.append, "hello")
        t.startService()
        util.spinWhile(lambda :not l, timeout=30)
        t.stopService()
        self.failIf(t.running)
        self.assertEqual(l, ["hello"])
        l.pop()

        # restart the same TimerService
        t.startService()
        util.spinWhile(lambda :not l, timeout=30)

        t.stopService()
        self.failIf(t.running)
        self.assertEqual(l, ["hello"])
        l.pop()
        t = internet.TimerService(0.01, l.append, "hello")
        t.startService()
        util.spinWhile(lambda :len(l) < 10, timeout=30)
        t.stopService()
        self.assertEqual(l, ["hello"]*10)

    def testPickledTimer(self):
        target = TimerTarget()
        t0 = internet.TimerService(1, target.append, "hello")
        t0.startService()
        s = pickle.dumps(t0)
        t0.stopService()

        t = pickle.loads(s)
        self.failIf(t.running)

    def testBrokenTimer(self):
        t = internet.TimerService(1, lambda: 1 / 0)
        t.startService()
        util.spinWhile(lambda :t._loop.running, timeout=30)
        t.stopService()
        self.assertEquals([ZeroDivisionError],
                          [o.value.__class__ for o in log.flushErrors(ZeroDivisionError)])

    def testEverythingThere(self):
        trans = 'TCP UNIX SSL UDP UNIXDatagram Multicast'.split()
        for tran in trans[:]:
            if not getattr(interfaces, "IReactor"+tran)(reactor, None):
                trans.remove(tran)
        if interfaces.IReactorArbitrary(reactor, None) is not None:
            trans.insert(0, "Generic")
        for tran in trans:
            for side in 'Server Client'.split():
                if tran == "Multicast" and side == "Client":
                    continue
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
    testService.suppress = oldAppSuppressions

    def testOldApplication(self):
        from twisted.internet import app as oapp
        application = oapp.Application("HELLO")
        oapp.MultiService("HELLO", application)
        compat.convert(application)
    testOldApplication.suppress = oldAppSuppressions
