
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
        self.handler = self.parser.handler = pmock.Mock()

    def _simpleKeystrokeTest(self, symbolic, bytes):
        self.handler.expects(pmock.once()).keystrokeReceived(pmock.eq(symbolic))
        self.parser.dataReceived(bytes)
        self.handler.verify()

    tmpl = "def test%sArrow(self): self._simpleKeystrokeTest(self.parser.%s_ARROW, '\x1b[%s')"
    for testName, byte in [('Up', 'A'), ('Down', 'B'), ('Right', 'C'), ('Left', 'D')]:
        exec tmpl % (testName, testName.upper(), byte)

    tmpl = "def testF%d(self): self._simpleKeystrokeTest(self.parser.F%d, '\x1bO%s')"
    for funcNum in range(1, 13):
        exec tmpl % (funcNum, funcNum, chr(ord('O') + funcNum))

    del tmpl, testName, funcNum, byte
