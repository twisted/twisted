
import pmock
from StringIO import StringIO

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

from insults import ServerProtocol

class ByteGroupings(unittest.TestCase):
    def setUp(self):
        self.transport = StringTransport()
        self.proto = pmock.Mock()
        self.parser = ServerProtocol(lambda: self.proto)
        self.proto.expects(pmock.once()).makeConnection(pmock.eq(self.parser))
        self.parser.makeConnection(self.transport)

    def _setupProtocol(self):
        # All the arrow keys once
        bytes = '\x1b[A\x1b[B\x1b[C\x1b[D'
        protocol = self.proto
        protocol.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.UP_ARROW)).id("up")
        protocol.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.DOWN_ARROW)).id("down").after("up")
        protocol.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.RIGHT_ARROW)).id("right").after("down")
        protocol.expects(pmock.once()).keystrokeReceived(pmock.eq(self.parser.LEFT_ARROW)).after("right")
        return protocol, bytes

    def testSingleBytes(self):
        protocol, bytes = self._setupProtocol()
        for b in bytes:
            self.parser.dataReceived(b)
        protocol.verify()

    tmpl = "def testByte%s(self):\n\th, b = self._setupProtocol()\n\twhile b:\n\t\tself.parser.dataReceived(b[:%d])\n\t\tb = b[%d:]\n\th.verify()"
    for word, n in [('Pairs', 2), ('Triples', 3), ('Quads', 4), ('Quints', 5), ('Sexes', 6)]:
        exec tmpl % (word, n, n)

    del tmpl, word, n


class ControlCharacters(unittest.TestCase):
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

