
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

    def _setupHandler(self):
        # All the arrow keys once
        bytes = '\x1b[A\x1b[B\x1b[C\x1b[D'
        handler = self.parser.handler = pmock.Mock()
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.UP_ARROW)).id("up")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.DOWN_ARROW)).id("down").after("up")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.RIGHT_ARROW)).id("right").after("down")
        handler.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.LEFT_ARROW)).after("right")
        return handler, bytes

    def testSingleBytes(self):
        handler, bytes = self._setupHandler()
        for b in bytes:
            self.parser.dataReceived(b)
        handler.verify()

    tmpl = "def testByte%s(self):\n\th, b = self._setupHandler()\n\twhile b:\n\t\tself.parser.dataReceived(b[:%d])\n\t\tb = b[%d:]\n\th.verify()"
    for word, n in [('Pairs', 2), ('Triples', 3), ('Quads', 4), ('Quints', 5), ('Sexes', 6)]:
        exec tmpl % (word, n, n)

    del tmpl, word, n
