
import pmock
from StringIO import StringIO

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

from insults import ServerProtocol, ClientProtocol
from insults import CS_UK, CS_US, CS_DRAWING, CS_ALTERNATE, CS_ALTERNATE_SPECIAL
from insults import G0, G1, G2, G3

class ByteGroupingsMixin:
    protocolFactory = None

    def setUp(self):
        self.transport = StringTransport()
        self.proto = pmock.Mock()
        self.parser = self.protocolFactory(lambda: self.proto)
        self.proto.expects(pmock.once()).makeConnection(pmock.eq(self.parser))
        self.parser.makeConnection(self.transport)

    def testSingleBytes(self):
        protocol, bytes = self._setupProtocol()
        for b in bytes:
            self.parser.dataReceived(b)
        protocol.verify()

    tmpl = "def testByte%s(self):\n\th, b = self._setupProtocol()\n\twhile b:\n\t\tself.parser.dataReceived(b[:%d])\n\t\tb = b[%d:]\n\th.verify()"
    for word, n in [('Pairs', 2), ('Triples', 3), ('Quads', 4), ('Quints', 5), ('Sexes', 6)]:
        exec tmpl % (word, n, n)

    del tmpl, word, n

class ServerByteGroupings(ByteGroupingsMixin, unittest.TestCase):
    protocolFactory = ServerProtocol

    def _setupProtocol(self):
        # All the arrow keys once
        bytes = '\x1b[A\x1b[B\x1b[C\x1b[D'
        protocol = self.proto
        protocol.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.UP_ARROW)).id("up")
        protocol.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.DOWN_ARROW)).id("down").after("up")
        protocol.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.RIGHT_ARROW)).id("right").after("down")
        protocol.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.LEFT_ARROW)).after("right")
        return protocol, bytes

class ServerControlCharacters(unittest.TestCase):
    """Test for parsing and dispatching control characters (arrow keys, etc).
    """
    def setUp(self):
        self.transport = StringTransport()
        self.proto = pmock.Mock()
        self.parser = ServerProtocol(lambda: self.proto)
        self.proto.expects(pmock.once()).makeConnection(pmock.eq(self.parser))
        self.parser.makeConnection(self.transport)

    def _simpleKeystrokeTest(self, symbolic, bytes):
        self.proto.expects(pmock.once()).keystrokeReceived(pmock.eq(symbolic))
        self.parser.dataReceived(bytes)
        self.proto.verify()

    tmpl = "def test%sArrow(self): self._simpleKeystrokeTest(self.parser.%s_ARROW, '\x1b[%s')"
    for testName, byte in [('Up', 'A'), ('Down', 'B'), ('Right', 'C'), ('Left', 'D')]:
        exec tmpl % (testName, testName.upper(), byte)

    tmpl = "def testF%d(self): self._simpleKeystrokeTest(self.parser.F%d, '\x1b[%s')"
    for testName, bytes in [(1, 'OP'), (2, 'OQ'), (3, 'OR'), (4, 'OS'),
                            (5, '15~'), (6, '17~'), (7, '18~'), (8, '19~'),
                            (9, '20~'), (10, '21~'), (11, '23~'), (12, '24~')]:
        exec tmpl % (testName, testName, bytes)

    del testName, byte, bytes

class ClientByteGroups(ByteGroupingsMixin, unittest.TestCase):
    protocolFactory = ClientProtocol

    def _setupProtocol(self):
        # Move the cursor down two, right four, up one, left two, up one, left two
        d2 = "\x1b[2B"
        r4 = "\x1b[4C"
        u1 = "\x1b[A"
        l2 = "\x1b[2D"
        bytes = d2 + r4 + u1 + l2 + u1 + l2
        p = self.proto
        p.expects(pmock.once()).cursorDown(pmock.eq(2)).id("d2")
        p.expects(pmock.once()).cursorForward(pmock.eq(4)).id("r4").after("d2")
        p.expects(pmock.once()).cursorUp(pmock.eq(1)).id("u1").after("r4")
        p.expects(pmock.once()).cursorBackward(pmock.eq(2)).id("l2").after("u1")
        p.expects(pmock.once()).cursorUp(pmock.eq(1)).id("u1-2").after("l2")
        p.expects(pmock.once()).cursorBackward(pmock.eq(2)).after("u1-2")
        return p, bytes

class ClientControlSequences(unittest.TestCase):
    def setUp(self):
        self.transport = StringTransport()
        self.proto = pmock.Mock()
        self.parser = ClientProtocol(lambda: self.proto)
        self.proto.expects(pmock.once()).makeConnection(pmock.eq(self.parser))
        self.parser.makeConnection(self.transport)

    def tearDown(self):
        self.proto.verify()

    def testSimpleCardinals(self):
        self.proto.expects(pmock.once()).cursorDown(pmock.eq(1)).id("a")
        self.proto.expects(pmock.once()).cursorDown(pmock.eq(2)).id("b").after("a")
        self.proto.expects(pmock.once()).cursorDown(pmock.eq(20)).id("c").after("b")
        self.proto.expects(pmock.once()).cursorDown(pmock.eq(200)).id("d").after("c")

        self.proto.expects(pmock.once()).cursorUp(pmock.eq(1)).id("e").after("d")
        self.proto.expects(pmock.once()).cursorUp(pmock.eq(2)).id("f").after("e")
        self.proto.expects(pmock.once()).cursorUp(pmock.eq(20)).id("g").after("f")
        self.proto.expects(pmock.once()).cursorUp(pmock.eq(200)).id("h").after("g")

        self.proto.expects(pmock.once()).cursorForward(pmock.eq(1)).id("i").after("h")
        self.proto.expects(pmock.once()).cursorForward(pmock.eq(2)).id("j").after("i")
        self.proto.expects(pmock.once()).cursorForward(pmock.eq(20)).id("k").after("j")
        self.proto.expects(pmock.once()).cursorForward(pmock.eq(200)).id("l").after("k")

        self.proto.expects(pmock.once()).cursorBackward(pmock.eq(1)).id("m").after("l")
        self.proto.expects(pmock.once()).cursorBackward(pmock.eq(2)).id("n").after("m")
        self.proto.expects(pmock.once()).cursorBackward(pmock.eq(20)).id("o").after("n")
        self.proto.expects(pmock.once()).cursorBackward(pmock.eq(200)).id("p").after("o")

        self.parser.dataReceived(
            ''.join([''.join(['\x1b[' + str(n) + ch for n in ('', 2, 20, 200)]) for ch in 'BACD']))

    def testScrollRegion(self):
        self.proto.expects(pmock.once()).setScrollRegion(pmock.eq(5), pmock.eq(22)).id("a")
        self.proto.expects(pmock.once()).setScrollRegion(pmock.eq(None), pmock.eq(None)).after("a")

        self.parser.dataReceived('\x1b[5;22r\x1b[r')

    def testHeightAndWidth(self):
        self.proto.expects(pmock.once()).doubleHeightLine(pmock.eq(True)).id("a")
        self.proto.expects(pmock.once()).doubleHeightLine(pmock.eq(False)).id("b").after("a")
        self.proto.expects(pmock.once()).singleWidthLine().id("c").after("b")
        self.proto.expects(pmock.once()).doubleWidthLine().after("c")

        self.parser.dataReceived("\x1b#3\x1b#4\x1b#5\x1b#6")

    def testCharacterSet(self):
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_UK), pmock.eq(G0)).id("a")
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_US), pmock.eq(G0)).id("b").after("a")
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_DRAWING), pmock.eq(G0)).id("c").after("b")
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_ALTERNATE), pmock.eq(G0)).id("d").after("c")
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_ALTERNATE_SPECIAL), pmock.eq(G0)).id("e").after("d")

        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_UK), pmock.eq(G1)).id("f")
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_US), pmock.eq(G1)).id("g").after("f")
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_DRAWING), pmock.eq(G1)).id("h").after("g")
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_ALTERNATE), pmock.eq(G1)).id("i").after("h")
        self.proto.expects(pmock.once()).selectCharacterSet(pmock.eq(CS_ALTERNATE_SPECIAL), pmock.eq(G1)).id("j").after("i")

        self.parser.dataReceived(
            ''.join([''.join(['\x1b' + g + n for n in 'AB012']) for g in '()']))

    def testShifting(self):
        self.proto.expects(pmock.once()).shiftIn().id("a")
        self.proto.expects(pmock.once()).shiftOut().after("a")

        self.parser.dataReceived("\x15\x14")

    def testSingleShifts(self):
        self.proto.expects(pmock.once()).singleShift2().id("a")
        self.proto.expects(pmock.once()).singleShift3().after("a")

        self.parser.dataReceived("\x1bN\x1bO")

    def testKeypadMode(self):
        self.proto.expects(pmock.once()).applicationKeypadMode().id("a")
        self.proto.expects(pmock.once()).numericKeypadMode().after("a")

        self.parser.dataReceived("\x1b=\x1b>")

    def testCursor(self):
        self.proto.expects(pmock.once()).saveCursor().id("a")
        self.proto.expects(pmock.once()).restoreCursor().after("a")

        self.parser.dataReceived("\x1b7\x1b8")

    def testReset(self):
        self.proto.expects(pmock.once()).reset()

        self.parser.dataReceived("\x1bc")

    def testIndex(self):
        self.proto.expects(pmock.once()).index().id("a")
        self.proto.expects(pmock.once()).reverseIndex().id("b").after("a")
        self.proto.expects(pmock.once()).nextLine().after("b")

        self.parser.dataReceived("\x1bD\x1bM\x1bE")
