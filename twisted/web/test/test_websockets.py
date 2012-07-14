from twisted.trial import unittest

from twisted.web.websockets import (_CONTROLS, _make_accept, _mask,
                                    _make_hybi07_frame, _parse_hybi07_frames)

"""
The WebSockets Protocol, according to RFC 6455
(http://tools.ietf.org/html/rfc6455). When "RFC" is mentioned, it refers to
this RFC. Some tests reference HyBi-10
(http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-10) or
HyBi-07 (http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-07),
which are drafts of RFC 6455.
"""

class TestKeys(unittest.TestCase):

    def test_make_accept_rfc(self):
        """
        L{_make_accept} makes responses according to the RFC.
        """

        key = "dGhlIHNhbXBsZSBub25jZQ=="

        self.assertEqual(_make_accept(key), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")


    def test_make_accept_wikipedia(self):
        """
        L{_make_accept} makes responses according to Wikipedia.
        """

        key = "x3JJHMbDL1EzLkh9GBhXDw=="

        self.assertEqual(_make_accept(key), "HSmrc0sMlYUkAGmm5OPpG2HaGWk=")



class TestHyBi07Helpers(unittest.TestCase):
    """
    HyBi-07 is best understood as a large family of helper functions which
    work together, somewhat dysfunctionally, to produce a mediocre
    Thanksgiving every other year.
    """

    def test_mask_noop(self):
        """
        Blank keys perform a no-op mask.
        """

        key = "\x00\x00\x00\x00"
        self.assertEqual(_mask("Test", key), "Test")


    def test_mask_noop_long(self):
        """
        Blank keys perform a no-op mask regardless of the length of the input.
        """

        key = "\x00\x00\x00\x00"
        self.assertEqual(_mask("LongTest", key), "LongTest")


    def test_mask_noop_odd(self):
        """
        Masking works even when the data to be masked isn't a multiple of four
        in length.
        """

        key = "\x00\x00\x00\x00"
        self.assertEqual(_mask("LongestTest", key), "LongestTest")


    def test_mask_hello(self):
        """
        A sample mask for "Hello" according to RFC 6455, 5.7.
        """

        key = "\x37\xfa\x21\x3d"
        self.assertEqual(_mask("Hello", key), "\x7f\x9f\x4d\x51\x58")


    def test_parse_hybi07_unmasked_text(self):
        """
        A sample unmasked frame of "Hello" from HyBi-10, 4.7.
        """

        frame = "\x81\x05Hello"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.NORMAL, "Hello"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_masked_text(self):
        """
        A sample masked frame of "Hello" from HyBi-10, 4.7.
        """

        frame = "\x81\x857\xfa!=\x7f\x9fMQX"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.NORMAL, "Hello"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_unmasked_text_fragments(self):
        """
        Fragmented masked packets are handled.

        From HyBi-10, 4.7.
        """

        frame = "\x01\x03Hel\x80\x02lo"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0], (_CONTROLS.NORMAL, "Hel"))
        self.assertEqual(frames[1], (_CONTROLS.NORMAL, "lo"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_ping(self):
        """
        Ping packets are decoded.

        From HyBi-10, 4.7.
        """

        frame = "\x89\x05Hello"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.PING, "Hello"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_pong(self):
        """
        Pong packets are decoded.

        From HyBi-10, 4.7.
        """

        frame = "\x8a\x05Hello"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.PONG, "Hello"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_close_empty(self):
        """
        A HyBi-07 close packet may have no body. In that case, it decodes with
        the generic error code 1000, and has no particular justification or
        error message.
        """

        frame = "\x88\x00"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.CLOSE, (1000, "No reason given")))
        self.assertEqual(buf, "")


    def test_parse_hybi07_close_reason(self):
        """
        A HyBi-07 close packet must have its first two bytes be a numeric
        error code, and may optionally include trailing text explaining why
        the connection was closed.
        """

        frame = "\x88\x0b\x03\xe8No reason"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (_CONTROLS.CLOSE, (1000, "No reason")))
        self.assertEqual(buf, "")


    def test_parse_hybi07_partial_no_length(self):
        """
        Partial frames are stored for later decoding.
        """

        frame = "\x81"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81")


    def test_parse_hybi07_partial_truncated_length_int(self):
        """
        Partial frames are stored for later decoding, even if they are cut on
        length boundaries.
        """

        frame = "\x81\xfe"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\xfe")


    def test_parse_hybi07_partial_truncated_length_double(self):
        """
        Partial frames are stored for later decoding, even if they are marked
        as being extra-long.
        """

        frame = "\x81\xff"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\xff")


    def test_parse_hybi07_partial_no_data(self):
        """
        Partial frames with full headers but no data are stored for later
        decoding.
        """

        frame = "\x81\x05"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\x05")


    def test_parse_hybi07_partial_truncated_data(self):
        """
        Partial frames with full headers and partial data are stored for later
        decoding.
        """

        frame = "\x81\x05Hel"
        frames, buf = _parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 0)
        self.assertEqual(buf, "\x81\x05Hel")


    def test_make_hybi07_hello(self):
        """
        L{_make_hybi07_frame} makes valid HyBi-07 packets.
        """

        frame = "\x81\x05Hello"
        buf = _make_hybi07_frame("Hello")
        self.assertEqual(frame, buf)
