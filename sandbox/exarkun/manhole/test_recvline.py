
import insults, recvline

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

        kR(self.pt.INSERT)

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

class Loopback(unittest.TestCase):
    def setUp(self):
        WIDTH = 80
        HEIGHT = 24

        recvlineServer = EchoServer()
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

        # Hack cough grunk stfu
        self.objs = locals()
        self.__dict__.update(locals())

    def testLineEditing(self):
        exec ''
        locals().update(self.objs)
        telnetClient.write("first line")

        clientTransport.clearBuffer()
        serverTransport.clearBuffer()

        self.assertEquals(
            str(recvlineClient),
            ">>> first line" + (recvlineClient.fill * (WIDTH - 14)) + "\n" +
            "\n".join([recvlineClient.fill * WIDTH for i in xrange(HEIGHT - 1)]))

        # An insults API for this would be nice.
        telnetClient.write("\x1b[D\x1b[D\x1b[D\x1b[Dxxxx\n")

        clientTransport.clearBuffer()
        serverTransport.clearBuffer()

        self.assertEquals(
            str(recvlineClient),
            ">>> first xxxx" + (recvlineClient.fill * (WIDTH - 14)) + "\n" +
            "first xxxx" + (recvlineClient.fill * (WIDTH - 10)) + "\n" +
            ">>> " + (recvlineClient.fill * (WIDTH - 4)) + "\n" +
            "\n".join([recvlineClient.fill * WIDTH for i in xrange(HEIGHT - 3)]))
