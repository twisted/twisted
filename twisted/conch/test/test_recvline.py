# -*- test-case-name: twisted.conch.test.test_recvline -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.recvline} and fixtures for testing related
functionality.
"""

import sys, os

from twisted.conch.insults import insults
from twisted.conch import recvline

from twisted.python import reflect, components
from twisted.internet import defer, error
from twisted.trial import unittest
from twisted.cred import portal
from twisted.test.proto_helpers import StringTransport

class Arrows(unittest.TestCase):
    def setUp(self):
        self.underlyingTransport = StringTransport()
        self.pt = insults.ServerProtocol()
        self.p = recvline.HistoricRecvLine()
        self.pt.protocolFactory = lambda: self.p
        self.pt.factory = self
        self.pt.makeConnection(self.underlyingTransport)
        # self.p.makeConnection(self.pt)

    def testPrintableCharacters(self):
        self.p.keystrokeReceived('x', None)
        self.p.keystrokeReceived('y', None)
        self.p.keystrokeReceived('z', None)

        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

    def testHorizontalArrows(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)
        for ch in 'xyz':
            kR(ch)

        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

        kR(self.pt.RIGHT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

        kR(self.pt.LEFT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('xy', 'z'))

        kR(self.pt.LEFT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('x', 'yz'))

        kR(self.pt.LEFT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('', 'xyz'))

        kR(self.pt.LEFT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('', 'xyz'))

        kR(self.pt.RIGHT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('x', 'yz'))

        kR(self.pt.RIGHT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('xy', 'z'))

        kR(self.pt.RIGHT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

        kR(self.pt.RIGHT_ARROW)
        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

    def testNewline(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)

        for ch in 'xyz\nabc\n123\n':
            kR(ch)

        self.assertEquals(self.p.currentHistoryBuffer(),
                          (('xyz', 'abc', '123'), ()))

        kR('c')
        kR('b')
        kR('a')
        self.assertEquals(self.p.currentHistoryBuffer(),
                          (('xyz', 'abc', '123'), ()))

        kR('\n')
        self.assertEquals(self.p.currentHistoryBuffer(),
                          (('xyz', 'abc', '123', 'cba'), ()))

    def testVerticalArrows(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)

        for ch in 'xyz\nabc\n123\n':
            kR(ch)

        self.assertEquals(self.p.currentHistoryBuffer(),
                          (('xyz', 'abc', '123'), ()))
        self.assertEquals(self.p.currentLineBuffer(), ('', ''))

        kR(self.pt.UP_ARROW)
        self.assertEquals(self.p.currentHistoryBuffer(),
                          (('xyz', 'abc'), ('123',)))
        self.assertEquals(self.p.currentLineBuffer(), ('123', ''))

        kR(self.pt.UP_ARROW)
        self.assertEquals(self.p.currentHistoryBuffer(),
                          (('xyz',), ('abc', '123')))
        self.assertEquals(self.p.currentLineBuffer(), ('abc', ''))

        kR(self.pt.UP_ARROW)
        self.assertEquals(self.p.currentHistoryBuffer(),
                          ((), ('xyz', 'abc', '123')))
        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

        kR(self.pt.UP_ARROW)
        self.assertEquals(self.p.currentHistoryBuffer(),
                          ((), ('xyz', 'abc', '123')))
        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

        for i in range(4):
            kR(self.pt.DOWN_ARROW)
        self.assertEquals(self.p.currentHistoryBuffer(),
                          (('xyz', 'abc', '123'), ()))

    def testHome(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)

        for ch in 'hello, world':
            kR(ch)
        self.assertEquals(self.p.currentLineBuffer(), ('hello, world', ''))

        kR(self.pt.HOME)
        self.assertEquals(self.p.currentLineBuffer(), ('', 'hello, world'))

    def testEnd(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)

        for ch in 'hello, world':
            kR(ch)
        self.assertEquals(self.p.currentLineBuffer(), ('hello, world', ''))

        kR(self.pt.HOME)
        kR(self.pt.END)
        self.assertEquals(self.p.currentLineBuffer(), ('hello, world', ''))

    def testBackspace(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)

        for ch in 'xyz':
            kR(ch)
        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

        kR(self.pt.BACKSPACE)
        self.assertEquals(self.p.currentLineBuffer(), ('xy', ''))

        kR(self.pt.LEFT_ARROW)
        kR(self.pt.BACKSPACE)
        self.assertEquals(self.p.currentLineBuffer(), ('', 'y'))

        kR(self.pt.BACKSPACE)
        self.assertEquals(self.p.currentLineBuffer(), ('', 'y'))

    def testDelete(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)

        for ch in 'xyz':
            kR(ch)
        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

        kR(self.pt.DELETE)
        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

        kR(self.pt.LEFT_ARROW)
        kR(self.pt.DELETE)
        self.assertEquals(self.p.currentLineBuffer(), ('xy', ''))

        kR(self.pt.LEFT_ARROW)
        kR(self.pt.DELETE)
        self.assertEquals(self.p.currentLineBuffer(), ('x', ''))

        kR(self.pt.LEFT_ARROW)
        kR(self.pt.DELETE)
        self.assertEquals(self.p.currentLineBuffer(), ('', ''))

        kR(self.pt.DELETE)
        self.assertEquals(self.p.currentLineBuffer(), ('', ''))

    def testInsert(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)

        for ch in 'xyz':
            kR(ch)

        # kR(self.pt.INSERT)

        kR(self.pt.LEFT_ARROW)
        kR('A')
        self.assertEquals(self.p.currentLineBuffer(), ('xyA', 'z'))

        kR(self.pt.LEFT_ARROW)
        kR('B')
        self.assertEquals(self.p.currentLineBuffer(), ('xyB', 'Az'))

    def testTypeover(self):
        kR = lambda ch: self.p.keystrokeReceived(ch, None)

        for ch in 'xyz':
            kR(ch)

        kR(self.pt.INSERT)

        kR(self.pt.LEFT_ARROW)
        kR('A')
        self.assertEquals(self.p.currentLineBuffer(), ('xyA', ''))

        kR(self.pt.LEFT_ARROW)
        kR('B')
        self.assertEquals(self.p.currentLineBuffer(), ('xyB', ''))


from twisted.conch import telnet
from twisted.conch.insults import helper
from twisted.protocols import loopback

class EchoServer(recvline.HistoricRecvLine):
    def lineReceived(self, line):
        self.terminal.write(line + '\n' + self.ps[self.pn])

# An insults API for this would be nice.
left = "\x1b[D"
right = "\x1b[C"
up = "\x1b[A"
down = "\x1b[B"
insert = "\x1b[2~"
home = "\x1b[1~"
delete = "\x1b[3~"
end = "\x1b[4~"
backspace = "\x7f"

from twisted.cred import checkers

try:
    from twisted.conch.ssh import userauth, transport, channel, connection, session
    from twisted.conch.manhole_ssh import TerminalUser, TerminalSession, TerminalRealm, TerminalSessionTransport, ConchFactory
except ImportError:
    ssh = False
else:
    ssh = True
    class SessionChannel(channel.SSHChannel):
        name = 'session'

        def __init__(self, protocolFactory, protocolArgs, protocolKwArgs, width, height, *a, **kw):
            channel.SSHChannel.__init__(self, *a, **kw)

            self.protocolFactory = protocolFactory
            self.protocolArgs = protocolArgs
            self.protocolKwArgs = protocolKwArgs

            self.width = width
            self.height = height

        def channelOpen(self, data):
            term = session.packRequest_pty_req("vt102", (self.height, self.width, 0, 0), '')
            self.conn.sendRequest(self, 'pty-req', term)
            self.conn.sendRequest(self, 'shell', '')

            self._protocolInstance = self.protocolFactory(*self.protocolArgs, **self.protocolKwArgs)
            self._protocolInstance.factory = self
            self._protocolInstance.makeConnection(self)

        def closed(self):
            self._protocolInstance.connectionLost(error.ConnectionDone())

        def dataReceived(self, data):
            self._protocolInstance.dataReceived(data)

    class TestConnection(connection.SSHConnection):
        def __init__(self, protocolFactory, protocolArgs, protocolKwArgs, width, height, *a, **kw):
            connection.SSHConnection.__init__(self, *a, **kw)

            self.protocolFactory = protocolFactory
            self.protocolArgs = protocolArgs
            self.protocolKwArgs = protocolKwArgs

            self.width = width
            self.height = height

        def serviceStarted(self):
            self.__channel = SessionChannel(self.protocolFactory, self.protocolArgs, self.protocolKwArgs, self.width, self.height)
            self.openChannel(self.__channel)

        def write(self, bytes):
            return self.__channel.write(bytes)

    class TestAuth(userauth.SSHUserAuthClient):
        def __init__(self, username, password, *a, **kw):
            userauth.SSHUserAuthClient.__init__(self, username, *a, **kw)
            self.password = password

        def getPassword(self):
            return defer.succeed(self.password)

    class TestTransport(transport.SSHClientTransport):
        def __init__(self, protocolFactory, protocolArgs, protocolKwArgs, username, password, width, height, *a, **kw):
            # transport.SSHClientTransport.__init__(self, *a, **kw)
            self.protocolFactory = protocolFactory
            self.protocolArgs = protocolArgs
            self.protocolKwArgs = protocolKwArgs
            self.username = username
            self.password = password
            self.width = width
            self.height = height

        def verifyHostKey(self, hostKey, fingerprint):
            return defer.succeed(True)

        def connectionSecure(self):
            self.__connection = TestConnection(self.protocolFactory, self.protocolArgs, self.protocolKwArgs, self.width, self.height)
            self.requestService(
                TestAuth(self.username, self.password, self.__connection))

        def write(self, bytes):
            return self.__connection.write(bytes)

    class TestSessionTransport(TerminalSessionTransport):
        def protocolFactory(self):
            return self.avatar.conn.transport.factory.serverProtocol()

    class TestSession(TerminalSession):
        transportFactory = TestSessionTransport

    class TestUser(TerminalUser):
        pass

    components.registerAdapter(TestSession, TestUser, session.ISession)


class LoopbackRelay(loopback.LoopbackRelay):
    clearCall = None

    def logPrefix(self):
        return "LoopbackRelay(%r)" % (self.target.__class__.__name__,)

    def write(self, bytes):
        loopback.LoopbackRelay.write(self, bytes)
        if self.clearCall is not None:
            self.clearCall.cancel()

        from twisted.internet import reactor
        self.clearCall = reactor.callLater(0, self._clearBuffer)

    def _clearBuffer(self):
        self.clearCall = None
        loopback.LoopbackRelay.clearBuffer(self)


class NotifyingExpectableBuffer(helper.ExpectableBuffer):
    def __init__(self):
        self.onConnection = defer.Deferred()
        self.onDisconnection = defer.Deferred()

    def connectionMade(self):
        helper.ExpectableBuffer.connectionMade(self)
        self.onConnection.callback(self)

    def connectionLost(self, reason):
        self.onDisconnection.errback(reason)


class _BaseMixin:
    WIDTH = 80
    HEIGHT = 24

    def _assertBuffer(self, lines):
        receivedLines = str(self.recvlineClient).splitlines()
        expectedLines = lines + ([''] * (self.HEIGHT - len(lines) - 1))
        self.assertEquals(len(receivedLines), len(expectedLines))
        for i in range(len(receivedLines)):
            self.assertEquals(
                receivedLines[i], expectedLines[i],
                str(receivedLines[max(0, i-1):i+1]) +
                " != " +
                str(expectedLines[max(0, i-1):i+1]))

    def _trivialTest(self, input, output):
        done = self.recvlineClient.expect("done")

        self._testwrite(input)

        def finished(ign):
            self._assertBuffer(output)

        return done.addCallback(finished)


class _SSHMixin(_BaseMixin):
    def setUp(self):
        if not ssh:
            raise unittest.SkipTest("Crypto requirements missing, can't run historic recvline tests over ssh")

        u, p = 'testuser', 'testpass'
        rlm = TerminalRealm()
        rlm.userFactory = TestUser
        rlm.chainedProtocolFactory = lambda: insultsServer

        ptl = portal.Portal(
            rlm,
            [checkers.InMemoryUsernamePasswordDatabaseDontUse(**{u: p})])
        sshFactory = ConchFactory(ptl)
        sshFactory.serverProtocol = self.serverProtocol
        sshFactory.startFactory()

        recvlineServer = self.serverProtocol()
        insultsServer = insults.ServerProtocol(lambda: recvlineServer)
        sshServer = sshFactory.buildProtocol(None)
        clientTransport = LoopbackRelay(sshServer)

        recvlineClient = NotifyingExpectableBuffer()
        insultsClient = insults.ClientProtocol(lambda: recvlineClient)
        sshClient = TestTransport(lambda: insultsClient, (), {}, u, p, self.WIDTH, self.HEIGHT)
        serverTransport = LoopbackRelay(sshClient)

        sshClient.makeConnection(clientTransport)
        sshServer.makeConnection(serverTransport)

        self.recvlineClient = recvlineClient
        self.sshClient = sshClient
        self.sshServer = sshServer
        self.clientTransport = clientTransport
        self.serverTransport = serverTransport

        return recvlineClient.onConnection

    def _testwrite(self, bytes):
        self.sshClient.write(bytes)

from twisted.conch.test import test_telnet

class TestInsultsClientProtocol(insults.ClientProtocol,
                                test_telnet.TestProtocol):
    pass


class TestInsultsServerProtocol(insults.ServerProtocol,
                                test_telnet.TestProtocol):
    pass

class _TelnetMixin(_BaseMixin):
    def setUp(self):
        recvlineServer = self.serverProtocol()
        insultsServer = TestInsultsServerProtocol(lambda: recvlineServer)
        telnetServer = telnet.TelnetTransport(lambda: insultsServer)
        clientTransport = LoopbackRelay(telnetServer)

        recvlineClient = NotifyingExpectableBuffer()
        insultsClient = TestInsultsClientProtocol(lambda: recvlineClient)
        telnetClient = telnet.TelnetTransport(lambda: insultsClient)
        serverTransport = LoopbackRelay(telnetClient)

        telnetClient.makeConnection(clientTransport)
        telnetServer.makeConnection(serverTransport)

        serverTransport.clearBuffer()
        clientTransport.clearBuffer()

        self.recvlineClient = recvlineClient
        self.telnetClient = telnetClient
        self.clientTransport = clientTransport
        self.serverTransport = serverTransport

        return recvlineClient.onConnection

    def _testwrite(self, bytes):
        self.telnetClient.write(bytes)

try:
    from twisted.conch import stdio
except ImportError:
    stdio = None

class _StdioMixin(_BaseMixin):
    def setUp(self):
        # A memory-only terminal emulator, into which the server will
        # write things and make other state changes.  What ends up
        # here is basically what a user would have seen on their
        # screen.
        testTerminal = NotifyingExpectableBuffer()

        # An insults client protocol which will translate bytes
        # received from the child process into keystroke commands for
        # an ITerminalProtocol.
        insultsClient = insults.ClientProtocol(lambda: testTerminal)

        # A process protocol which will translate stdout and stderr
        # received from the child process to dataReceived calls and
        # error reporting on an insults client protocol.
        processClient = stdio.TerminalProcessProtocol(insultsClient)

        # Run twisted/conch/stdio.py with the name of a class
        # implementing ITerminalProtocol.  This class will be used to
        # handle bytes we send to the child process.
        exe = sys.executable
        module = stdio.__file__
        if module.endswith('.pyc') or module.endswith('.pyo'):
            module = module[:-1]
        args = [exe, module, reflect.qual(self.serverProtocol)]
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)

        from twisted.internet import reactor
        clientTransport = reactor.spawnProcess(processClient, exe, args,
                                               env=env, usePTY=True)

        self.recvlineClient = self.testTerminal = testTerminal
        self.processClient = processClient
        self.clientTransport = clientTransport

        # Wait for the process protocol and test terminal to become
        # connected before proceeding.  The former should always
        # happen first, but it doesn't hurt to be safe.
        return defer.gatherResults(filter(None, [
            processClient.onConnection,
            testTerminal.expect(">>> ")]))

    def tearDown(self):
        # Kill the child process.  We're done with it.
        try:
            self.clientTransport.signalProcess("KILL")
        except (error.ProcessExitedAlready, OSError):
            pass
        def trap(failure):
            failure.trap(error.ProcessTerminated)
            self.assertEquals(failure.value.exitCode, None)
            self.assertEquals(failure.value.status, 9)
        return self.testTerminal.onDisconnection.addErrback(trap)

    def _testwrite(self, bytes):
        self.clientTransport.write(bytes)

class RecvlineLoopbackMixin:
    serverProtocol = EchoServer

    def testSimple(self):
        return self._trivialTest(
            "first line\ndone",
            [">>> first line",
             "first line",
             ">>> done"])

    def testLeftArrow(self):
        return self._trivialTest(
            insert + 'first line' + left * 4 + "xxxx\ndone",
            [">>> first xxxx",
             "first xxxx",
             ">>> done"])

    def testRightArrow(self):
        return self._trivialTest(
            insert + 'right line' + left * 4 + right * 2 + "xx\ndone",
            [">>> right lixx",
             "right lixx",
            ">>> done"])

    def testBackspace(self):
        return self._trivialTest(
            "second line" + backspace * 4 + "xxxx\ndone",
            [">>> second xxxx",
             "second xxxx",
             ">>> done"])

    def testDelete(self):
        return self._trivialTest(
            "delete xxxx" + left * 4 + delete * 4 + "line\ndone",
            [">>> delete line",
             "delete line",
             ">>> done"])

    def testInsert(self):
        return self._trivialTest(
            "third ine" + left * 3 + "l\ndone",
            [">>> third line",
             "third line",
             ">>> done"])

    def testTypeover(self):
        return self._trivialTest(
            "fourth xine" + left * 4 + insert + "l\ndone",
            [">>> fourth line",
             "fourth line",
             ">>> done"])

    def testHome(self):
        return self._trivialTest(
            insert + "blah line" + home + "home\ndone",
            [">>> home line",
             "home line",
             ">>> done"])

    def testEnd(self):
        return self._trivialTest(
            "end " + left * 4 + end + "line\ndone",
            [">>> end line",
             "end line",
             ">>> done"])

class RecvlineLoopbackTelnet(_TelnetMixin, unittest.TestCase, RecvlineLoopbackMixin):
    pass

class RecvlineLoopbackSSH(_SSHMixin, unittest.TestCase, RecvlineLoopbackMixin):
    pass

class RecvlineLoopbackStdio(_StdioMixin, unittest.TestCase, RecvlineLoopbackMixin):
    if stdio is None:
        skip = "Terminal requirements missing, can't run recvline tests over stdio"


class HistoricRecvlineLoopbackMixin:
    serverProtocol = EchoServer

    def testUpArrow(self):
        return self._trivialTest(
            "first line\n" + up + "\ndone",
            [">>> first line",
             "first line",
             ">>> first line",
             "first line",
             ">>> done"])

    def testDownArrow(self):
        return self._trivialTest(
            "first line\nsecond line\n" + up * 2 + down + "\ndone",
            [">>> first line",
             "first line",
             ">>> second line",
             "second line",
             ">>> second line",
             "second line",
             ">>> done"])

class HistoricRecvlineLoopbackTelnet(_TelnetMixin, unittest.TestCase, HistoricRecvlineLoopbackMixin):
    pass

class HistoricRecvlineLoopbackSSH(_SSHMixin, unittest.TestCase, HistoricRecvlineLoopbackMixin):
    pass

class HistoricRecvlineLoopbackStdio(_StdioMixin, unittest.TestCase, HistoricRecvlineLoopbackMixin):
    if stdio is None:
        skip = "Terminal requirements missing, can't run historic recvline tests over stdio"
