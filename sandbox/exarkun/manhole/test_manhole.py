
import pmock
from StringIO import StringIO

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

from manhole import ServerProtocol

class ControlCharacters(unittest.TestCase):
    """Test for parsing and dispatching control characters (arrow keys, etc).
    """

    def setUp(self):
        self.parser = ServerProtocol()
        self.transport = StringTransport()
        self.parser.makeConnection(self.transport)

    def _simpleKeystrokeTest(self, symbolic, bytes):
        handler = self.parser.handler = pmock.Mock()
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(symbolic))
        self.parser.dataReceived(bytes)
        handler.verify()

    tmpl = "def test%sArrow(self): self._simpleKeystrokeTest(self.parser.%s_ARROW, '\x1b[%s')"
    for testName, byte in [('Up', 'A'), ('Down', 'B'), ('Right', 'C'), ('Left', 'D')]:
        exec tmpl % (testName, testName.upper(), byte)

    tmpl = "def testF%d(self): self._simpleKeystrokeTest(self.parser.F%d, '\x1bO%s')"
    for funcNum in range(1, 13):
        exec tmpl % (funcNum, funcNum, chr(ord('O') + funcNum))

    del tmpl, testName, funcNum, byte

    def _setupHandler(self):
        # All the arrow keys once, followed by 5 function keys
        bytes = '\x1b[A\x1b[B\x1b[C\x1bD\x1bOP\x1bOQ\x1bOR\x1bOS\x1bOT'
        handler = self.parser.handler = pmock.Mock()
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.UP_ARROW)).id("up")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.DOWN_ARROW)).id("down").after("up")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.RIGHT_ARROW)).id("right").after("down")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.LEFT_ARROW)).id("left").after("right")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.F1)).id("f1").after("left")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.F2)).id("f2").after("f1")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.F3)).id("f3").after("f2")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.F4)).id("f4").after("f3")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.F5)).after("f4")
        return handler, bytes

    def testSingleBytes(self):
        handler, bytes = self._setupHandler()
        for b in bytes:
            self.parser.dataReceived(b)
        handler.verify()

    tmpl = "def testByte%s(self):\n\thandler, bytes = self._setupHandler()\n\twhile bytes:\n\t\tself.parser.dataReceived(b[:%d])\n\t\tb = b[%d:]\n\thandler.verify()"
    for word, n in [('Pairs', 2), ('Triples', 3), ('Quads', 4), ('Quints', 5), ('Sexes', 6)]:
        exec tmpl % (word, n, n)
