
import insults, recvline

from twisted.python import log
from twisted.internet import defer
from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

class Arrows(unittest.TestCase):
    def setUp(self):
        self.underlyingTransport = StringTransport()
        self.pt = insults.ServerProtocol()
        self.p = recvline.HistoricRecvLine()
        self.pt.protocolFactory = lambda: self.p
        self.pt.makeConnection(self.underlyingTransport)
        # self.p.makeConnection(self.pt)

    def testPrintableCharacters(self):
        self.p.keystrokeReceived('x')
        self.p.keystrokeReceived('y')
        self.p.keystrokeReceived('z')

        self.assertEquals(self.p.currentLineBuffer(), ('xyz', ''))

    def testHorizontalArrows(self):
        kR = self.p.keystrokeReceived
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
        kR = self.p.keystrokeReceived

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
        kR = self.p.keystrokeReceived

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
        kR = self.p.keystrokeReceived

        for ch in 'hello, world':
            kR(ch)
        self.assertEquals(self.p.currentLineBuffer(), ('hello, world', ''))

        kR(self.pt.HOME)
        self.assertEquals(self.p.currentLineBuffer(), ('', 'hello, world'))

    def testEnd(self):
        kR = self.p.keystrokeReceived

        for ch in 'hello, world':
            kR(ch)
        self.assertEquals(self.p.currentLineBuffer(), ('hello, world', ''))

        kR(self.pt.HOME)
        kR(self.pt.END)
        self.assertEquals(self.p.currentLineBuffer(), ('hello, world', ''))

    def testBackspace(self):
        kR = self.p.keystrokeReceived

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
        kR = self.p.keystrokeReceived

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
        kR = self.p.keystrokeReceived

        for ch in 'xyz':
            kR(ch)

        kR(self.pt.INSERT)

        kR(self.pt.LEFT_ARROW)
        kR('A')
        self.assertEquals(self.p.currentLineBuffer(), ('xyA', 'z'))

        kR(self.pt.LEFT_ARROW)
        kR('B')
        self.assertEquals(self.p.currentLineBuffer(), ('xyB', 'Az'))

    def testTypeover(self):
        kR = self.p.keystrokeReceived

        for ch in 'xyz':
            kR(ch)

        kR(self.pt.LEFT_ARROW)
        kR('A')
        self.assertEquals(self.p.currentLineBuffer(), ('xyA', ''))

        kR(self.pt.LEFT_ARROW)
        kR('B')
        self.assertEquals(self.p.currentLineBuffer(), ('xyB', ''))


import telnet, helper
from twisted.protocols import loopback

class EchoServer(recvline.HistoricRecvLine):
    def lineReceived(self, line):
        self.transport.write(line + '\n' + self.ps[self.pn])

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
from twisted.conch.ssh import transport, userauth, channel, connection, session

class TestAuth(userauth.SSHUserAuthClient):
    def __init__(self, username, password, *a, **kw):
        userauth.SSHUserAuthClient.__init__(self, username, *a, **kw)
        self.password = password

    def getPassword(self):
        return defer.succeed(self.password)

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
        self._protocolInstance.makeConnection(self)

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

from ssh import TerminalUser, TerminalSession, TerminalSessionTransport, ConchFactory
from demolib import TerminalForwardingProtocol
from twisted.python import components

class TestSessionTransport(TerminalSessionTransport):
    def protocolFactory(self):
        return TerminalForwardingProtocol(self.avatar.conn.transport.factory.serverProtocol)

class TestSession(TerminalSession):
    transportFactory = TestSessionTransport

components.registerAdapter(TestSession, TerminalUser, session.ISession)

class _BaseMixin:
    WIDTH = 80
    HEIGHT = 24

    def _test(self, s, lines):
        self._testwrite(s)
        self._emptyBuffers()
        self.assertEquals(
            str(self.recvlineClient),
            '\n'.join(lines) +
            '\n' * (self.HEIGHT - len(lines)))

class _SSHMixin(_BaseMixin):
    def setUp(self):
        u, p = 'testuser', 'testpass'
        sshFactory = ConchFactory([checkers.InMemoryUsernamePasswordDatabaseDontUse(**{u: p})])
        sshFactory.serverProtocol = self.serverProtocol
        sshFactory.startFactory()

        recvlineServer = self.serverProtocol()
        insultsServer = insults.ServerProtocol(lambda: recvlineServer)
        sshServer = sshFactory.buildProtocol(None)
        clientTransport = loopback.LoopbackRelay(sshServer)

        recvlineClient = helper.TerminalBuffer()
        insultsClient = insults.ClientProtocol(lambda: recvlineClient)
        sshClient = TestTransport(lambda: insultsClient, (), {}, u, p, self.WIDTH, self.HEIGHT)
        serverTransport = loopback.LoopbackRelay(sshClient)

        sshClient.makeConnection(clientTransport)
        sshServer.makeConnection(serverTransport)

        self.recvlineClient = recvlineClient
        self.sshClient = sshClient
        self.sshServer = sshServer
        self.clientTransport = clientTransport
        self.serverTransport = serverTransport

        self._emptyBuffers()

    def _testwrite(self, bytes):
        self.sshClient.write(bytes)

    def _emptyBuffers(self):
        while self.serverTransport.buffer or self.clientTransport.buffer:
            log.callWithContext({'system': 'serverTransport'}, self.serverTransport.clearBuffer)
            log.callWithContext({'system': 'clientTransport'}, self.clientTransport.clearBuffer)

class _TelnetMixin(_BaseMixin):
    def setUp(self):
        recvlineServer = self.serverProtocol()
        insultsServer = insults.ServerProtocol(lambda: recvlineServer)
        telnetServer = telnet.TelnetTransport(lambda: insultsServer)
        clientTransport = loopback.LoopbackRelay(telnetServer)

        recvlineClient = helper.TerminalBuffer()
        insultsClient = insults.ClientProtocol(lambda: recvlineClient)
        telnetClient = telnet.TelnetTransport(lambda: insultsClient)
        serverTransport = loopback.LoopbackRelay(telnetClient)

        telnetClient.makeConnection(clientTransport)
        telnetServer.makeConnection(serverTransport)

        serverTransport.clearBuffer()
        clientTransport.clearBuffer()

        self.recvlineClient = recvlineClient
        self.telnetClient = telnetClient
        self.clientTransport = clientTransport
        self.serverTransport = serverTransport

    def _testwrite(self, bytes):
        self.telnetClient.write(bytes)

    def _emptyBuffers(self):
        self.clientTransport.clearBuffer()
        self.serverTransport.clearBuffer()

class RecvlineLoopbackMixin:
    serverProtocol = EchoServer

    def testSimple(self):
        self._test(
            "first line",
            [">>> first line"])

    def testLeftArrow(self):
        self._test(
            'first line' + left * 4 + "xxxx\n",
            [">>> first xxxx",
             "first xxxx",
             ">>>"])

    def testRightArrow(self):
        self._test(
            'right line' + left * 4 + right * 2 + "xx\n",
            [">>> right lixx",
             "right lixx",
            ">>>"])

    def testBackspace(self):
        self._test(
            "second line" + backspace * 4 + "xxxx\n",
            [">>> second xxxx",
             "second xxxx",
             ">>>"])

    def testDelete(self):
        self._test(
            "delete xxxx" + left * 4 + delete * 4 + "line\n",
            [">>> delete line",
             "delete line",
             ">>>"])

    def testInsert(self):
        self._test(
            "third ine" + left * 3 + insert + "l\n",
            [">>> third line",
             "third line",
             ">>>"])

    def testTypeover(self):
        self._test(
            "fourth xine" + left * 4 + insert * 2 + "l\n",
            [">>> fourth line",
             "fourth line",
             ">>>"])

    def testHome(self):
        self._test(
            "blah line" + home + "home\n",
            [">>> home line",
             "home line",
             ">>>"])

    def testEnd(self):
        self._test(
            "end " + left * 4 + end + "line\n",
            [">>> end line",
             "end line",
             ">>>"])

class RecvlineLoopbackTelnet(_TelnetMixin, unittest.TestCase, RecvlineLoopbackMixin):
    pass

class RecvlineLoopbackSSH(_SSHMixin, unittest.TestCase, RecvlineLoopbackMixin):
    pass

class HistoricRecvlineLoopbackMixin:
    serverProtocol = EchoServer

    def testUpArrow(self):
        self._test(
            "first line\n" + up,
            [">>> first line",
             "first line",
             ">>> first line"])

    def testDownArrow(self):
        self._test(
            "first line\nsecond line\n" + up * 2 + down,
            [">>> first line",
             "first line",
             ">>> second line",
             "second line",
             ">>> second line"])

class HistoricRecvlineLoopbackTelnet(_TelnetMixin, unittest.TestCase, HistoricRecvlineLoopbackMixin):
    pass

class HistoricRecvlineLoopbackSSH(_SSHMixin, unittest.TestCase, HistoricRecvlineLoopbackMixin):
    pass
