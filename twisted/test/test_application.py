# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application} and its interaction with
L{twisted.persisted.sob}.
"""

import copy, os, pickle
from StringIO import StringIO

from twisted.trial import unittest, util
from twisted.application import service, internet, app
from twisted.persisted import sob
from twisted.python import usage
from twisted.internet import interfaces, defer
from twisted.protocols import wire, basic
from twisted.internet import protocol, reactor
from twisted.application import reactors
from twisted.test.proto_helpers import MemoryReactor


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

    def testRunningChildren1(self):
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

    def testRunningChildren2(self):
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
        for style in 'source pickle'.split():
            p.setStyle(style)
            p.save()
            a1 = service.loadApplication("hello.ta"+style[0], style)
            self.assertEqual(service.IService(a1).name, "hello")
        f = open("hello.tac", 'w')
        f.writelines([
        "from twisted.application import service\n",
        "application = service.Application('hello')\n",
        ])
        f.close()
        a1 = service.loadApplication("hello.tac", 'python')
        self.assertEqual(service.IService(a1).name, "hello")



class TestAppSupport(unittest.TestCase):

    def testPassphrase(self):
        self.assertEqual(app.getPassphrase(0), None)

    def testLoadApplication(self):
        """
        Test loading an application file in different dump format.
        """
        a = service.Application("hello")
        baseconfig = {'file': None, 'source': None, 'python':None}
        for style in 'source pickle'.split():
            config = baseconfig.copy()
            config[{'pickle': 'file'}.get(style, style)] = 'helloapplication'
            sob.IPersistable(a).setStyle(style)
            sob.IPersistable(a).save(filename='helloapplication')
            a1 = app.getApplication(config, None)
            self.assertEqual(service.IService(a1).name, "hello")
        config = baseconfig.copy()
        config['python'] = 'helloapplication'
        f = open("helloapplication", 'w')
        f.writelines([
        "from twisted.application import service\n",
        "application = service.Application('hello')\n",
        ])
        f.close()
        a1 = app.getApplication(config, None)
        self.assertEqual(service.IService(a1).name, "hello")

    def test_convertStyle(self):
        appl = service.Application("lala")
        for instyle in 'source pickle'.split():
            for outstyle in 'source pickle'.split():
                sob.IPersistable(appl).setStyle(instyle)
                sob.IPersistable(appl).save(filename="converttest")
                app.convertStyle("converttest", instyle, None,
                                 "converttest.out", outstyle, 0)
                appl2 = service.loadApplication("converttest.out", outstyle)
                self.assertEqual(service.IService(appl2).name, "lala")


    def test_startApplication(self):
        appl = service.Application("lala")
        app.startApplication(appl, 0)
        self.assert_(service.IService(appl).running)


class Foo(basic.LineReceiver):
    def connectionMade(self):
        self.transport.write('lalala\r\n')
    def lineReceived(self, line):
        self.factory.line = line
        self.transport.loseConnection()
    def connectionLost(self, reason):
        self.factory.d.callback(self.factory.line)


class DummyApp:
    processName = None
    def addService(self, service):
        self.services[service.name] = service
    def removeService(self, service):
        del self.services[service.name]


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
        factory = protocol.ClientFactory()
        factory.d = defer.Deferred()
        factory.protocol = Foo
        factory.line = None
        internet.TCPClient('127.0.0.1', num, factory).setServiceParent(s)
        factory.d.addCallback(self.assertEqual, 'lalala')
        factory.d.addCallback(lambda x : s.stopService())
        factory.d.addCallback(lambda x : TestEcho.d)
        return factory.d


    def test_UDP(self):
        """
        Test L{internet.UDPServer} with a random port: starting the service
        should give it valid port, and stopService should free it so that we
        can start a server on the same port again.
        """
        if not interfaces.IReactorUDP(reactor, None):
            raise unittest.SkipTest("This reactor does not support UDP sockets")
        p = protocol.DatagramProtocol()
        t = internet.UDPServer(0, p)
        t.startService()
        num = t._port.getHost().port
        self.assertNotEquals(num, 0)
        def onStop(ignored):
            t = internet.UDPServer(num, p)
            t.startService()
            return t.stopService()
        return defer.maybeDeferred(t.stopService).addCallback(onStop)


    def testPrivileged(self):
        factory = protocol.ServerFactory()
        factory.protocol = TestEcho
        TestEcho.d = defer.Deferred()
        t = internet.TCPServer(0, factory)
        t.privileged = 1
        t.privilegedStartService()
        num = t._port.getHost().port
        factory = protocol.ClientFactory()
        factory.d = defer.Deferred()
        factory.protocol = Foo
        factory.line = None
        c = internet.TCPClient('127.0.0.1', num, factory)
        c.startService()
        factory.d.addCallback(self.assertEqual, 'lalala')
        factory.d.addCallback(lambda x : c.stopService())
        factory.d.addCallback(lambda x : t.stopService())
        factory.d.addCallback(lambda x : TestEcho.d)
        return factory.d

    def testConnectionGettingRefused(self):
        factory = protocol.ServerFactory()
        factory.protocol = wire.Echo
        t = internet.TCPServer(0, factory)
        t.startService()
        num = t._port.getHost().port
        t.stopService()
        d = defer.Deferred()
        factory = protocol.ClientFactory()
        factory.clientConnectionFailed = lambda *args: d.callback(None)
        c = internet.TCPClient('127.0.0.1', num, factory)
        c.startService()
        return d

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
        factory = protocol.ClientFactory()
        factory.protocol = Foo
        factory.d = defer.Deferred()
        factory.line = None
        internet.UNIXClient('echo.skt', factory).setServiceParent(s)
        factory.d.addCallback(self.assertEqual, 'lalala')
        factory.d.addCallback(lambda x : s.stopService())
        factory.d.addCallback(lambda x : TestEcho.d)
        factory.d.addCallback(self._cbTestUnix, factory, s)
        return factory.d

    def _cbTestUnix(self, ignored, factory, s):
        TestEcho.d = defer.Deferred()
        factory.line = None
        factory.d = defer.Deferred()
        s.startService()
        factory.d.addCallback(self.assertEqual, 'lalala')
        factory.d.addCallback(lambda x : s.stopService())
        factory.d.addCallback(lambda x : TestEcho.d)
        return factory.d

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
        d = defer.Deferred()
        factory.clientConnectionFailed = lambda *args: d.callback(None)
        reactor.connectUNIX('echo.skt', factory)
        return d

    def testPickledTimer(self):
        target = TimerTarget()
        t0 = internet.TimerService(1, target.append, "hello")
        t0.startService()
        s = pickle.dumps(t0)
        t0.stopService()

        t = pickle.loads(s)
        self.failIf(t.running)

    def testBrokenTimer(self):
        d = defer.Deferred()
        t = internet.TimerService(1, lambda: 1 / 0)
        oldFailed = t._failed
        def _failed(why):
            oldFailed(why)
            d.callback(None)
        t._failed = _failed
        t.startService()
        d.addCallback(lambda x : t.stopService)
        d.addCallback(lambda x : self.assertEqual(
            [ZeroDivisionError],
            [o.value.__class__ for o in self.flushLoggedErrors(ZeroDivisionError)]))
        return d


    def test_genericServerDeprecated(self):
        """
        Instantiating L{GenericServer} emits a deprecation warning.
        """
        internet.GenericServer()
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_genericServerDeprecated])
        self.assertEquals(
            warnings[0]['message'],
            'GenericServer was deprecated in Twisted 10.1.')
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertEquals(len(warnings), 1)


    def test_genericClientDeprecated(self):
        """
        Instantiating L{GenericClient} emits a deprecation warning.
        """
        internet.GenericClient()
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_genericClientDeprecated])
        self.assertEquals(
            warnings[0]['message'],
            'GenericClient was deprecated in Twisted 10.1.')
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertEquals(len(warnings), 1)


    def test_everythingThere(self):
        """
        L{twisted.application.internet} dynamically defines a set of
        L{service.Service} subclasses that in general have corresponding
        reactor.listenXXX or reactor.connectXXX calls.
        """
        trans = 'TCP UNIX SSL UDP UNIXDatagram Multicast'.split()
        for tran in trans[:]:
            if not getattr(interfaces, "IReactor" + tran)(reactor, None):
                trans.remove(tran)
        if interfaces.IReactorArbitrary(reactor, None) is not None:
            trans.insert(0, "Generic")
        for tran in trans:
            for side in 'Server Client'.split():
                if tran == "Multicast" and side == "Client":
                    continue
                self.assertTrue(hasattr(internet, tran + side))
                method = getattr(internet, tran + side).method
                prefix = {'Server': 'listen', 'Client': 'connect'}[side]
                self.assertTrue(hasattr(reactor, prefix + method) or
                        (prefix == "connect" and method == "UDP"))
                o = getattr(internet, tran + side)()
                self.assertEquals(service.IService(o), o)
    test_everythingThere.suppress = [
        util.suppress(message='GenericServer was deprecated in Twisted 10.1.',
                      category=DeprecationWarning),
        util.suppress(message='GenericClient was deprecated in Twisted 10.1.',
                      category=DeprecationWarning),
        util.suppress(message='twisted.internet.interfaces.IReactorArbitrary was '
                      'deprecated in Twisted 10.1.0: See IReactorFDSet.')]


    def test_importAll(self):
        """
        L{twisted.application.internet} dynamically defines L{service.Service}
        subclasses. This test ensures that the subclasses exposed by C{__all__}
        are valid attributes of the module.
        """
        for cls in internet.__all__:
            self.assertTrue(
                hasattr(internet, cls),
                '%s not importable from twisted.application.internet' % (cls,))


    def test_reactorParametrizationInServer(self):
        """
        L{internet._AbstractServer} supports a C{reactor} keyword argument
        that can be used to parametrize the reactor used to listen for
        connections.
        """
        reactor = MemoryReactor()

        factory = object()
        t = internet.TCPServer(1234, factory, reactor=reactor)
        t.startService()
        self.assertEquals(reactor.tcpServers.pop()[:2], (1234, factory))


    def test_reactorParametrizationInClient(self):
        """
        L{internet._AbstractClient} supports a C{reactor} keyword arguments
        that can be used to parametrize the reactor used to create new client
        connections.
        """
        reactor = MemoryReactor()

        factory = object()
        t = internet.TCPClient('127.0.0.1', 1234, factory, reactor=reactor)
        t.startService()
        self.assertEquals(
            reactor.tcpClients.pop()[:3], ('127.0.0.1', 1234, factory))


    def test_reactorParametrizationInServerMultipleStart(self):
        """
        Like L{test_reactorParametrizationInServer}, but stop and restart the
        service and check that the given reactor is still used.
        """
        reactor = MemoryReactor()

        factory = object()
        t = internet.TCPServer(1234, factory, reactor=reactor)
        t.startService()
        self.assertEquals(reactor.tcpServers.pop()[:2], (1234, factory))
        t.stopService()
        t.startService()
        self.assertEquals(reactor.tcpServers.pop()[:2], (1234, factory))


    def test_reactorParametrizationInClientMultipleStart(self):
        """
        Like L{test_reactorParametrizationInClient}, but stop and restart the
        service and check that the given reactor is still used.
        """
        reactor = MemoryReactor()

        factory = object()
        t = internet.TCPClient('127.0.0.1', 1234, factory, reactor=reactor)
        t.startService()
        self.assertEquals(
            reactor.tcpClients.pop()[:3], ('127.0.0.1', 1234, factory))
        t.stopService()
        t.startService()
        self.assertEquals(
            reactor.tcpClients.pop()[:3], ('127.0.0.1', 1234, factory))



class TestTimerBasic(unittest.TestCase):

    def testTimerRuns(self):
        d = defer.Deferred()
        self.t = internet.TimerService(1, d.callback, 'hello')
        self.t.startService()
        d.addCallback(self.assertEqual, 'hello')
        d.addCallback(lambda x : self.t.stopService())
        d.addCallback(lambda x : self.failIf(self.t.running))
        return d

    def tearDown(self):
        return self.t.stopService()

    def testTimerRestart(self):
        # restart the same TimerService
        d1 = defer.Deferred()
        d2 = defer.Deferred()
        work = [(d2, "bar"), (d1, "foo")]
        def trigger():
            d, arg = work.pop()
            d.callback(arg)
        self.t = internet.TimerService(1, trigger)
        self.t.startService()
        def onFirstResult(result):
            self.assertEqual(result, 'foo')
            return self.t.stopService()
        def onFirstStop(ignored):
            self.failIf(self.t.running)
            self.t.startService()
            return d2
        def onSecondResult(result):
            self.assertEqual(result, 'bar')
            self.t.stopService()
        d1.addCallback(onFirstResult)
        d1.addCallback(onFirstStop)
        d1.addCallback(onSecondResult)
        return d1

    def testTimerLoops(self):
        l = []
        def trigger(data, number, d):
            l.append(data)
            if len(l) == number:
                d.callback(l)
        d = defer.Deferred()
        self.t = internet.TimerService(0.01, trigger, "hello", 10, d)
        self.t.startService()
        d.addCallback(self.assertEqual, ['hello'] * 10)
        d.addCallback(lambda x : self.t.stopService())
        return d


class FakeReactor(reactors.Reactor):
    """
    A fake reactor with a hooked install method.
    """

    def __init__(self, install, *args, **kwargs):
        """
        @param install: any callable that will be used as install method.
        @type install: C{callable}
        """
        reactors.Reactor.__init__(self, *args, **kwargs)
        self.install = install



class PluggableReactorTestCase(unittest.TestCase):
    """
    Tests for the reactor discovery/inspection APIs.
    """

    def setUp(self):
        """
        Override the L{reactors.getPlugins} function, normally bound to
        L{twisted.plugin.getPlugins}, in order to control which
        L{IReactorInstaller} plugins are seen as available.

        C{self.pluginResults} can be customized and will be used as the
        result of calls to C{reactors.getPlugins}.
        """
        self.pluginCalls = []
        self.pluginResults = []
        self.originalFunction = reactors.getPlugins
        reactors.getPlugins = self._getPlugins


    def tearDown(self):
        """
        Restore the original L{reactors.getPlugins}.
        """
        reactors.getPlugins = self.originalFunction


    def _getPlugins(self, interface, package=None):
        """
        Stand-in for the real getPlugins method which records its arguments
        and returns a fixed result.
        """
        self.pluginCalls.append((interface, package))
        return list(self.pluginResults)


    def test_getPluginReactorTypes(self):
        """
        Test that reactor plugins are returned from L{getReactorTypes}
        """
        name = 'fakereactortest'
        package = __name__ + '.fakereactor'
        description = 'description'
        self.pluginResults = [reactors.Reactor(name, package, description)]
        reactorTypes = reactors.getReactorTypes()

        self.assertEqual(
            self.pluginCalls,
            [(reactors.IReactorInstaller, None)])

        for r in reactorTypes:
            if r.shortName == name:
                self.assertEqual(r.description, description)
                break
        else:
            self.fail("Reactor plugin not present in getReactorTypes() result")


    def test_reactorInstallation(self):
        """
        Test that L{reactors.Reactor.install} loads the correct module and
        calls its install attribute.
        """
        installed = []
        def install():
            installed.append(True)
        installer = FakeReactor(install,
                                'fakereactortest', __name__, 'described')
        installer.install()
        self.assertEqual(installed, [True])


    def test_installReactor(self):
        """
        Test that the L{reactors.installReactor} function correctly installs
        the specified reactor.
        """
        installed = []
        def install():
            installed.append(True)
        name = 'fakereactortest'
        package = __name__
        description = 'description'
        self.pluginResults = [FakeReactor(install, name, package, description)]
        reactors.installReactor(name)
        self.assertEqual(installed, [True])


    def test_installNonExistentReactor(self):
        """
        Test that L{reactors.installReactor} raises L{reactors.NoSuchReactor}
        when asked to install a reactor which it cannot find.
        """
        self.pluginResults = []
        self.assertRaises(
            reactors.NoSuchReactor,
            reactors.installReactor, 'somereactor')


    def test_installNotAvailableReactor(self):
        """
        Test that L{reactors.installReactor} raises an exception when asked to
        install a reactor which doesn't work in this environment.
        """
        def install():
            raise ImportError("Missing foo bar")
        name = 'fakereactortest'
        package = __name__
        description = 'description'
        self.pluginResults = [FakeReactor(install, name, package, description)]
        self.assertRaises(ImportError, reactors.installReactor, name)


    def test_reactorSelectionMixin(self):
        """
        Test that the reactor selected is installed as soon as possible, ie
        when the option is parsed.
        """
        executed = []
        INSTALL_EVENT = 'reactor installed'
        SUBCOMMAND_EVENT = 'subcommands loaded'

        class ReactorSelectionOptions(usage.Options, app.ReactorSelectionMixin):
            def subCommands(self):
                executed.append(SUBCOMMAND_EVENT)
                return [('subcommand', None, lambda: self, 'test subcommand')]
            subCommands = property(subCommands)

        def install():
            executed.append(INSTALL_EVENT)
        self.pluginResults = [
            FakeReactor(install, 'fakereactortest', __name__, 'described')
        ]

        options = ReactorSelectionOptions()
        options.parseOptions(['--reactor', 'fakereactortest', 'subcommand'])
        self.assertEqual(executed[0], INSTALL_EVENT)
        self.assertEqual(executed.count(INSTALL_EVENT), 1)
        self.assertEquals(options["reactor"], "fakereactortest")


    def test_reactorSelectionMixinNonExistent(self):
        """
        Test that the usage mixin exits when trying to use a non existent
        reactor (the name not matching to any reactor), giving an error
        message.
        """
        class ReactorSelectionOptions(usage.Options, app.ReactorSelectionMixin):
            pass
        self.pluginResults = []

        options = ReactorSelectionOptions()
        options.messageOutput = StringIO()
        e = self.assertRaises(usage.UsageError, options.parseOptions,
                              ['--reactor', 'fakereactortest', 'subcommand'])
        self.assertIn("fakereactortest", e.args[0])
        self.assertIn("help-reactors", e.args[0])


    def test_reactorSelectionMixinNotAvailable(self):
        """
        Test that the usage mixin exits when trying to use a reactor not
        available (the reactor raises an error at installation), giving an
        error message.
        """
        class ReactorSelectionOptions(usage.Options, app.ReactorSelectionMixin):
            pass
        message = "Missing foo bar"
        def install():
            raise ImportError(message)

        name = 'fakereactortest'
        package = __name__
        description = 'description'
        self.pluginResults = [FakeReactor(install, name, package, description)]

        options = ReactorSelectionOptions()
        options.messageOutput = StringIO()
        e =  self.assertRaises(usage.UsageError, options.parseOptions,
                               ['--reactor', 'fakereactortest', 'subcommand'])
        self.assertIn(message, e.args[0])
        self.assertIn("help-reactors", e.args[0])
