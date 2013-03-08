# -*- test-case-name: twisted.conch.test.test_insults -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

from twisted.conch.insults.insults import ServerProtocol, ClientProtocol
from twisted.conch.insults.insults import CS_UK, CS_US, CS_DRAWING, CS_ALTERNATE, CS_ALTERNATE_SPECIAL
from twisted.conch.insults.insults import G0, G1
from twisted.conch.insults.insults import modes

def _getattr(mock, name):
    return super(Mock, mock).__getattribute__(name)

def occurrences(mock):
    return _getattr(mock, 'occurrences')

def methods(mock):
    return _getattr(mock, 'methods')

def _append(mock, obj):
    occurrences(mock).append(obj)

default = object()

class Mock(object):
    callReturnValue = default

    def __init__(self, methods=None, callReturnValue=default):
        """
        @param methods: Mapping of names to return values
        @param callReturnValue: object __call__ should return
        """
        self.occurrences = []
        if methods is None:
            methods = {}
        self.methods = methods
        if callReturnValue is not default:
            self.callReturnValue = callReturnValue

    def __call__(self, *a, **kw):
        returnValue = _getattr(self, 'callReturnValue')
        if returnValue is default:
            returnValue = Mock()
        # _getattr(self, 'occurrences').append(('__call__', returnValue, a, kw))
        _append(self, ('__call__', returnValue, a, kw))
        return returnValue

    def __getattribute__(self, name):
        methods = _getattr(self, 'methods')
        if name in methods:
            attrValue = Mock(callReturnValue=methods[name])
        else:
            attrValue = Mock()
        # _getattr(self, 'occurrences').append((name, attrValue))
        _append(self, (name, attrValue))
        return attrValue

class MockMixin:
    def assertCall(self, occurrence, methodName, expectedPositionalArgs=(),
                   expectedKeywordArgs={}):
        attr, mock = occurrence
        self.assertEqual(attr, methodName)
        self.assertEqual(len(occurrences(mock)), 1)
        [(call, result, args, kw)] = occurrences(mock)
        self.assertEqual(call, "__call__")
        self.assertEqual(args, expectedPositionalArgs)
        self.assertEqual(kw, expectedKeywordArgs)
        return result


_byteGroupingTestTemplate = """\
def testByte%(groupName)s(self):
    transport = StringTransport()
    proto = Mock()
    parser = self.protocolFactory(lambda: proto)
    parser.factory = self
    parser.makeConnection(transport)

    bytes = self.TEST_BYTES
    while bytes:
        chunk = bytes[:%(bytesPer)d]
        bytes = bytes[%(bytesPer)d:]
        parser.dataReceived(chunk)

    self.verifyResults(transport, proto, parser)
"""
class ByteGroupingsMixin(MockMixin):
    protocolFactory = None

    for word, n in [('Pairs', 2), ('Triples', 3), ('Quads', 4), ('Quints', 5), ('Sexes', 6)]:
        exec _byteGroupingTestTemplate % {'groupName': word, 'bytesPer': n}
    del word, n

    def verifyResults(self, transport, proto, parser):
        result = self.assertCall(occurrences(proto).pop(0), "makeConnection", (parser,))
        self.assertEqual(occurrences(result), [])

del _byteGroupingTestTemplate

class ServerArrowKeys(ByteGroupingsMixin, unittest.TestCase):
    protocolFactory = ServerProtocol

    # All the arrow keys once
    TEST_BYTES = '\x1b[A\x1b[B\x1b[C\x1b[D'

    def verifyResults(self, transport, proto, parser):
        ByteGroupingsMixin.verifyResults(self, transport, proto, parser)

        for arrow in (parser.UP_ARROW, parser.DOWN_ARROW,
                      parser.RIGHT_ARROW, parser.LEFT_ARROW):
            result = self.assertCall(occurrences(proto).pop(0), "keystrokeReceived", (arrow, None))
            self.assertEqual(occurrences(result), [])
        self.failIf(occurrences(proto))


class PrintableCharacters(ByteGroupingsMixin, unittest.TestCase):
    protocolFactory = ServerProtocol

    # Some letters and digits, first on their own, then capitalized,
    # then modified with alt

    TEST_BYTES = 'abc123ABC!@#\x1ba\x1bb\x1bc\x1b1\x1b2\x1b3'

    def verifyResults(self, transport, proto, parser):
        ByteGroupingsMixin.verifyResults(self, transport, proto, parser)

        for char in 'abc123ABC!@#':
            result = self.assertCall(occurrences(proto).pop(0), "keystrokeReceived", (char, None))
            self.assertEqual(occurrences(result), [])

        for char in 'abc123':
            result = self.assertCall(occurrences(proto).pop(0), "keystrokeReceived", (char, parser.ALT))
            self.assertEqual(occurrences(result), [])

        occs = occurrences(proto)
        self.failIf(occs, "%r should have been []" % (occs,))

class ServerFunctionKeys(ByteGroupingsMixin, unittest.TestCase):
    """Test for parsing and dispatching function keys (F1 - F12)
    """
    protocolFactory = ServerProtocol

    byteList = []
    for bytes in ('OP', 'OQ', 'OR', 'OS', # F1 - F4
                  '15~', '17~', '18~', '19~', # F5 - F8
                  '20~', '21~', '23~', '24~'): # F9 - F12
        byteList.append('\x1b[' + bytes)
    TEST_BYTES = ''.join(byteList)
    del byteList, bytes

    def verifyResults(self, transport, proto, parser):
        ByteGroupingsMixin.verifyResults(self, transport, proto, parser)
        for funcNum in range(1, 13):
            funcArg = getattr(parser, 'F%d' % (funcNum,))
            result = self.assertCall(occurrences(proto).pop(0), "keystrokeReceived", (funcArg, None))
            self.assertEqual(occurrences(result), [])
        self.failIf(occurrences(proto))

class ClientCursorMovement(ByteGroupingsMixin, unittest.TestCase):
    protocolFactory = ClientProtocol

    d2 = "\x1b[2B"
    r4 = "\x1b[4C"
    u1 = "\x1b[A"
    l2 = "\x1b[2D"
    # Move the cursor down two, right four, up one, left two, up one, left two
    TEST_BYTES = d2 + r4 + u1 + l2 + u1 + l2
    del d2, r4, u1, l2

    def verifyResults(self, transport, proto, parser):
        ByteGroupingsMixin.verifyResults(self, transport, proto, parser)

        for (method, count) in [('Down', 2), ('Forward', 4), ('Up', 1),
                                ('Backward', 2), ('Up', 1), ('Backward', 2)]:
            result = self.assertCall(occurrences(proto).pop(0), "cursor" + method, (count,))
            self.assertEqual(occurrences(result), [])
        self.failIf(occurrences(proto))

class ClientControlSequences(unittest.TestCase, MockMixin):
    def setUp(self):
        self.transport = StringTransport()
        self.proto = Mock()
        self.parser = ClientProtocol(lambda: self.proto)
        self.parser.factory = self
        self.parser.makeConnection(self.transport)
        result = self.assertCall(occurrences(self.proto).pop(0), "makeConnection", (self.parser,))
        self.failIf(occurrences(result))

    def testSimpleCardinals(self):
        self.parser.dataReceived(
            ''.join([''.join(['\x1b[' + str(n) + ch for n in ('', 2, 20, 200)]) for ch in 'BACD']))
        occs = occurrences(self.proto)

        for meth in ("Down", "Up", "Forward", "Backward"):
            for count in (1, 2, 20, 200):
                result = self.assertCall(occs.pop(0), "cursor" + meth, (count,))
                self.failIf(occurrences(result))
        self.failIf(occs)

    def testScrollRegion(self):
        self.parser.dataReceived('\x1b[5;22r\x1b[r')
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "setScrollRegion", (5, 22))
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "setScrollRegion", (None, None))
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testHeightAndWidth(self):
        self.parser.dataReceived("\x1b#3\x1b#4\x1b#5\x1b#6")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "doubleHeightLine", (True,))
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "doubleHeightLine", (False,))
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "singleWidthLine")
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "doubleWidthLine")
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testCharacterSet(self):
        self.parser.dataReceived(
            ''.join([''.join(['\x1b' + g + n for n in 'AB012']) for g in '()']))
        occs = occurrences(self.proto)

        for which in (G0, G1):
            for charset in (CS_UK, CS_US, CS_DRAWING, CS_ALTERNATE, CS_ALTERNATE_SPECIAL):
                result = self.assertCall(occs.pop(0), "selectCharacterSet", (charset, which))
                self.failIf(occurrences(result))
        self.failIf(occs)

    def testShifting(self):
        self.parser.dataReceived("\x15\x14")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "shiftIn")
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "shiftOut")
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testSingleShifts(self):
        self.parser.dataReceived("\x1bN\x1bO")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "singleShift2")
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "singleShift3")
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testKeypadMode(self):
        self.parser.dataReceived("\x1b=\x1b>")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "applicationKeypadMode")
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "numericKeypadMode")
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testCursor(self):
        self.parser.dataReceived("\x1b7\x1b8")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "saveCursor")
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "restoreCursor")
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testReset(self):
        self.parser.dataReceived("\x1bc")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "reset")
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testIndex(self):
        self.parser.dataReceived("\x1bD\x1bM\x1bE")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "index")
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "reverseIndex")
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "nextLine")
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testModes(self):
        self.parser.dataReceived(
            "\x1b[" + ';'.join(map(str, [modes.KAM, modes.IRM, modes.LNM])) + "h")
        self.parser.dataReceived(
            "\x1b[" + ';'.join(map(str, [modes.KAM, modes.IRM, modes.LNM])) + "l")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "setModes", ([modes.KAM, modes.IRM, modes.LNM],))
        self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "resetModes", ([modes.KAM, modes.IRM, modes.LNM],))
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testErasure(self):
        self.parser.dataReceived(
            "\x1b[K\x1b[1K\x1b[2K\x1b[J\x1b[1J\x1b[2J\x1b[3P")
        occs = occurrences(self.proto)

        for meth in ("eraseToLineEnd", "eraseToLineBeginning", "eraseLine",
                     "eraseToDisplayEnd", "eraseToDisplayBeginning",
                     "eraseDisplay"):
            result = self.assertCall(occs.pop(0), meth)
            self.failIf(occurrences(result))

        result = self.assertCall(occs.pop(0), "deleteCharacter", (3,))
        self.failIf(occurrences(result))
        self.failIf(occs)

    def testLineDeletion(self):
        self.parser.dataReceived("\x1b[M\x1b[3M")
        occs = occurrences(self.proto)

        for arg in (1, 3):
            result = self.assertCall(occs.pop(0), "deleteLine", (arg,))
            self.failIf(occurrences(result))
        self.failIf(occs)

    def testLineInsertion(self):
        self.parser.dataReceived("\x1b[L\x1b[3L")
        occs = occurrences(self.proto)

        for arg in (1, 3):
            result = self.assertCall(occs.pop(0), "insertLine", (arg,))
            self.failIf(occurrences(result))
        self.failIf(occs)

    def testCursorPosition(self):
        methods(self.proto)['reportCursorPosition'] = (6, 7)
        self.parser.dataReceived("\x1b[6n")
        self.assertEqual(self.transport.value(), "\x1b[7;8R")
        occs = occurrences(self.proto)

        result = self.assertCall(occs.pop(0), "reportCursorPosition")
        # This isn't really an interesting assert, since it only tests that
        # our mock setup is working right, but I'll include it anyway.
        self.assertEqual(result, (6, 7))


    def test_applicationDataBytes(self):
        """
        Contiguous non-control bytes are passed to a single call to the
        C{write} method of the terminal to which the L{ClientProtocol} is
        connected.
        """
        occs = occurrences(self.proto)
        self.parser.dataReceived('a')
        self.assertCall(occs.pop(0), "write", ("a",))
        self.parser.dataReceived('bc')
        self.assertCall(occs.pop(0), "write", ("bc",))


    def _applicationDataTest(self, data, calls):
        occs = occurrences(self.proto)
        self.parser.dataReceived(data)
        while calls:
            self.assertCall(occs.pop(0), *calls.pop(0))
        self.assertFalse(occs, "No other calls should happen: %r" % (occs,))


    def test_shiftInAfterApplicationData(self):
        """
        Application data bytes followed by a shift-in command are passed to a
        call to C{write} before the terminal's C{shiftIn} method is called.
        """
        self._applicationDataTest(
            'ab\x15', [
                ("write", ("ab",)),
                ("shiftIn",)])


    def test_shiftOutAfterApplicationData(self):
        """
        Application data bytes followed by a shift-out command are passed to a
        call to C{write} before the terminal's C{shiftOut} method is called.
        """
        self._applicationDataTest(
            'ab\x14', [
                ("write", ("ab",)),
                ("shiftOut",)])


    def test_cursorBackwardAfterApplicationData(self):
        """
        Application data bytes followed by a cursor-backward command are passed
        to a call to C{write} before the terminal's C{cursorBackward} method is
        called.
        """
        self._applicationDataTest(
            'ab\x08', [
                ("write", ("ab",)),
                ("cursorBackward",)])


    def test_escapeAfterApplicationData(self):
        """
        Application data bytes followed by an escape character are passed to a
        call to C{write} before the terminal's handler method for the escape is
        called.
        """
        # Test a short escape
        self._applicationDataTest(
            'ab\x1bD', [
                ("write", ("ab",)),
                ("index",)])

        # And a long escape
        self._applicationDataTest(
            'ab\x1b[4h', [
                ("write", ("ab",)),
                ("setModes", ([4],))])

        # There's some other cases too, but they're all handled by the same
        # codepaths as above.



class ServerProtocolOutputTests(unittest.TestCase):
    """
    Tests for the bytes L{ServerProtocol} writes to its transport when its
    methods are called.
    """
    def test_nextLine(self):
        """
        L{ServerProtocol.nextLine} writes C{"\r\n"} to its transport.
        """
        # Why doesn't it write ESC E?  Because ESC E is poorly supported.  For
        # example, gnome-terminal (many different versions) fails to scroll if
        # it receives ESC E and the cursor is already on the last row.
        protocol = ServerProtocol()
        transport = StringTransport()
        protocol.makeConnection(transport)
        protocol.nextLine()
        self.assertEqual(transport.value(), "\r\n")



class Deprecations(unittest.TestCase):
    """
    Tests to ensure deprecation of L{insults.colors} and L{insults.client}
    """

    def ensureDeprecated(self, message):
        """
        Ensures that the correct deprecation warning was issued.
        """
        warnings = self.flushWarnings()
        self.assertIdentical(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(warnings[0]['message'], message)
        self.assertEqual(len(warnings), 1)


    def test_colors(self):
        """
        The L{insults.colors} module is deprecated
        """
        from twisted.conch.insults import colors
        self.ensureDeprecated("twisted.conch.insults.colors was deprecated "
                              "in Twisted 10.1.0: Please use "
                              "twisted.conch.insults.helper instead.")


    def test_client(self):
        """
        The L{insults.client} module is deprecated
        """
        from twisted.conch.insults import client
        self.ensureDeprecated("twisted.conch.insults.client was deprecated "
                              "in Twisted 10.1.0: Please use "
                              "twisted.conch.insults.insults instead.")
