# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The WebSockets Protocol, according to RFC 6455
(http://tools.ietf.org/html/rfc6455). When "RFC" is mentioned, it refers to
this RFC. Some tests reference HyBi-10
(http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-10) or
HyBi-07 (http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-07),
which are drafts of RFC 6455.
"""

from twisted.trial.unittest import TestCase

from twisted.internet.protocol import Factory, Protocol
from twisted.python import log
from twisted.test.proto_helpers import StringTransportWithDisconnection

from twisted.web.websockets import (
    _CONTROLS, _makeAccept, _mask, _makeFrame, _parseFrames, _WSException,
    _WebSocketsFactory)



class TestFrameHelpers(TestCase):

    def test_makeAcceptRFC(self):
        """
        L{_makeAccept} makes responses according to the RFC.
        """
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        self.assertEqual(_makeAccept(key), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")


    def test_maskNoop(self):
        """
        Blank keys perform a no-op mask.
        """
        key = "\x00\x00\x00\x00"
        self.assertEqual(_mask("Test", key), "Test")


    def test_maskNoopLong(self):
        """
        Blank keys perform a no-op mask regardless of the length of the input.
        """
        key = "\x00\x00\x00\x00"
        self.assertEqual(_mask("LongTest", key), "LongTest")


    def test_maskNoopOdd(self):
        """
        Masking works even when the data to be masked isn't a multiple of four
        in length.
        """
        key = "\x00\x00\x00\x00"
        self.assertEqual(_mask("LongestTest", key), "LongestTest")


    def test_maskHello(self):
        """
        A sample mask for "Hello" according to RFC 6455, 5.7.
        """
        key = "\x37\xfa\x21\x3d"
        self.assertEqual(_mask("Hello", key), "\x7f\x9f\x4d\x51\x58")


    def test_parseUnmaskedText(self):
        """
        A sample unmasked frame of "Hello" from HyBi-10, 4.7.
        """
        frame = "\x81\x05Hello"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.NORMAL, "Hello"))
        self.assertEqual(buf, "")


    def test_parseUnmaskedLargeText(self):
        """
        L{_parseFrames} handles frame with text longer than 125 bytes.
        """
        frame = "\x81\x7e\x00\xc8" + "x" * 200
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.NORMAL, "x" * 200))
        self.assertEqual(buf, "")


    def test_parseUnmaskedHugeText(self):
        """
        L{_parseFrames} handles frame with text longer than 64 kB.
        """
        frame = "\x81\x7f\x00\x00\x00\x00\x00\x01\x86\xa0" + "x" * 100000
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.NORMAL, "x" * 100000))
        self.assertEqual(buf, "")


    def test_parseMaskedText(self):
        """
        A sample masked frame of "Hello" from HyBi-10, 4.7.
        """
        frame = "\x81\x857\xfa!=\x7f\x9fMQX"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.NORMAL, "Hello"))
        self.assertEqual(buf, "")


    def test_parseMaskedPartialText(self):
        """
        L{_parseFrames} stops parsing if a masked frame isn't long enough to
        contain the length of the text.
        """
        frame = "\x81\x827\xfa"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\x827\xfa")


    def test_parseUnmaskedTextFragments(self):
        """
        Fragmented masked packets are handled.

        From HyBi-10, 4.7.
        """
        frame = "\x01\x03Hel\x80\x02lo"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0], (_CONTROLS.NORMAL, "Hel"))
        self.assertEqual(frames[1], (_CONTROLS.NORMAL, "lo"))
        self.assertEqual(buf, "")


    def test_parsePing(self):
        """
        Ping packets are decoded.

        From HyBi-10, 4.7.
        """
        frame = "\x89\x05Hello"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.PING, "Hello"))
        self.assertEqual(buf, "")


    def test_parsePong(self):
        """
        Pong packets are decoded.

        From HyBi-10, 4.7.
        """
        frame = "\x8a\x05Hello"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.PONG, "Hello"))
        self.assertEqual(buf, "")


    def test_parseCloseEmpty(self):
        """
        A HyBi-07 close packet may have no body. In that case, it decodes with
        the generic error code 1000, and has no particular justification or
        error message.
        """
        frame = "\x88\x00"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(
            frames[0], (_CONTROLS.CLOSE, (1000, "No reason given")))
        self.assertEqual(buf, "")


    def test_parseCloseReason(self):
        """
        A HyBi-07 close packet must have its first two bytes be a numeric
        error code, and may optionally include trailing text explaining why
        the connection was closed.
        """
        frame = "\x88\x0b\x03\xe8No reason"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.CLOSE, (1000, "No reason")))
        self.assertEqual(buf, "")


    def test_parsePartialNoLength(self):
        """
        Partial frames are stored for later decoding.
        """
        frame = "\x81"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81")


    def test_parsePartialTruncatedLengthInt(self):
        """
        Partial frames are stored for later decoding, even if they are cut on
        length boundaries.
        """
        frame = "\x81\xfe"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\xfe")


    def test_parsePartialTruncatedLengthDouble(self):
        """
        Partial frames are stored for later decoding, even if they are marked
        as being extra-long.
        """
        frame = "\x81\xff"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\xff")


    def test_parsePartialNoData(self):
        """
        Partial frames with full headers but no data are stored for later
        decoding.
        """
        frame = "\x81\x05"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\x05")


    def test_parsePartialTruncatedData(self):
        """
        Partial frames with full headers and partial data are stored for later
        decoding.
        """
        frame = "\x81\x05Hel"
        frames, buf = _parseFrames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\x05Hel")


    def test_parseReservedFlag(self):
        """
        L{_parseFrames} raises a L[_WSException} error when the header uses a
        reserved flag.
        """
        frame = "\x72\x05"
        error = self.assertRaises(_WSException, _parseFrames, frame)
        self.assertEqual("Reserved flag in frame (114)", str(error))


    def test_parseUnknownOpcode(self):
        """
        L{_parseFrames} raises a L{_WSException} error when the error uses an
        unknown opcode.
        """
        frame = "\x8f\x05"
        error = self.assertRaises(_WSException, _parseFrames, frame)
        self.assertEqual("Unknown opcode 15 in frame", str(error))


    def test_makeHello(self):
        """
        L{_makeFrame} makes valid HyBi-07 packets.
        """
        frame = "\x81\x05Hello"
        buf = _makeFrame("Hello")
        self.assertEqual(frame, buf)


    def test_makeLargeFrame(self):
        """
        L{_makeFrame} prefixes the payload by the length on 2 bytes if the
        payload is more than 125 bytes.
        """
        frame = "\x81\x7e\x00\xc8" + "x" * 200
        buf = _makeFrame("x" * 200)
        self.assertEqual(frame, buf)


    def test_makeHugeFrame(self):
        """
        L{_makeFrame} prefixes the payload by the length on 8 bytes if the
        payload is more than 64 kB.
        """
        frame = "\x81\x7f\x00\x00\x00\x00\x00\x01\x86\xa0" + "x" * 100000
        buf = _makeFrame("x" * 100000)
        self.assertEqual(frame, buf)



class SavingEcho(Protocol):
    """
    A test protocol saving the data received and sending it back.
    """

    def connectionMade(self):
        self.received = []


    def dataReceived(self, data):
        self.received.append(data)
        self.transport.write(data)



class WebsocketsProtocolTest(TestCase):

    def setUp(self):

        class SavingEchoFactory(Factory):

            def buildProtocol(oself, addr):
                return self.echoProtocol

        factory = SavingEchoFactory()
        self.echoProtocol = SavingEcho()
        self.factory = _WebSocketsFactory(factory)
        self.protocol = self.factory.buildProtocol(None)
        self.transport = StringTransportWithDisconnection()
        self.protocol.makeConnection(self.transport)
        self.transport.protocol = self.protocol


    def test_frameReceived(self):
        """
        C{_WebSocketsProtocol.dataReceived} translates bytes into frames, and
        then write it back encoded into frames.
        """
        self.protocol.dataReceived("\x81\x05Hello")
        self.assertEqual("\x81\x05Hello", self.transport.value())
        self.assertEqual(["Hello"], self.echoProtocol.received)


    def test_frameReceivedWithCodec(self):
        """
        A codec can be specified with the C{_WebSocketsProtocol}, in which case
        the data received and sent is encoded with it.
        """
        self.protocol.codec = "base64"
        self.protocol.dataReceived("\x81\x08SGVsbG8=")
        self.assertEqual("\x81\x08SGVsbG8=", self.transport.value())
        self.assertEqual(["Hello"], self.echoProtocol.received)


    def test_ping(self):
        """
        When a C{PING} frame is received, the frame is resent with a C{PONG},
        but the application protocol doesn't receive any data.
        """
        self.protocol.dataReceived("\x89\x05Hello")
        self.assertEqual("\x8a\x05Hello", self.transport.value())
        self.assertEqual([], self.echoProtocol.received)


    def test_close(self):
        """
        When a C{CLOSE} frame is received, the protocol closes the connection
        and logs a message.
        """
        loggedMessages = []

        def logConnectionLostMsg(eventDict):
            loggedMessages.append(log.textFromEventDict(eventDict))

        log.addObserver(logConnectionLostMsg)

        self.protocol.dataReceived("\x88\x00")
        self.assertFalse(self.transport.connected)
        self.assertEqual(["Closing connection: 'No reason given' (1000)"],
                         loggedMessages)


    def test_invalidFrame(self):
        """
        If an invalid frame is received, C{_WebSocketsProtocol} closes the
        connection and logs an error.
        """
        self.protocol.dataReceived("\x72\x05")
        self.assertFalse(self.transport.connected)
        [error] = self.flushLoggedErrors(_WSException)
        self.assertEqual("Reserved flag in frame (114)", str(error.value))
