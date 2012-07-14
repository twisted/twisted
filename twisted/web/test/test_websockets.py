from twisted.trial import unittest

from twisted.web.websockets import (make_accept, mask, CLOSE, NORMAL, PING,
                                    PONG, make_hybi07_frame,
                                    parse_hybi07_frames)

class TestKeys(unittest.TestCase):

    def test_make_accept_rfc(self):
        """
        Test ``make_accept()`` using the keys listed in the RFC for HyBi-07
        through HyBi-10.
        """

        key = "dGhlIHNhbXBsZSBub25jZQ=="

        self.assertEqual(make_accept(key), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")


    def test_make_accept_wikipedia(self):
        """
        Test ``make_accept()`` using the keys listed on Wikipedia.
        """

        key = "x3JJHMbDL1EzLkh9GBhXDw=="

        self.assertEqual(make_accept(key), "HSmrc0sMlYUkAGmm5OPpG2HaGWk=")



class TestHyBi07Helpers(unittest.TestCase):
    """
    HyBi-07 is best understood as a large family of helper functions which
    work together, somewhat dysfunctionally, to produce a mediocre
    Thanksgiving every other year.
    """

    def test_mask_noop(self):
        key = "\x00\x00\x00\x00"
        self.assertEqual(mask("Test", key), "Test")


    def test_mask_noop_long(self):
        key = "\x00\x00\x00\x00"
        self.assertEqual(mask("LongTest", key), "LongTest")


    def test_mask_noop_odd(self):
        """
        Masking works even when the data to be masked isn't a multiple of four
        in length.
        """

        key = "\x00\x00\x00\x00"
        self.assertEqual(mask("LongestTest", key), "LongestTest")


    def test_mask_hello(self):
        """
        From RFC 6455, 5.7.
        """

        key = "\x37\xfa\x21\x3d"
        self.assertEqual(mask("Hello", key), "\x7f\x9f\x4d\x51\x58")


    def test_parse_hybi07_unmasked_text(self):
        """
        From HyBi-10, 4.7.
        """

        frame = "\x81\x05Hello"
        frames, buf = parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (NORMAL, "Hello"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_masked_text(self):
        """
        From HyBi-10, 4.7.
        """

        frame = "\x81\x857\xfa!=\x7f\x9fMQX"
        frames, buf = parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (NORMAL, "Hello"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_unmasked_text_fragments(self):
        """
        We don't care about fragments. We are totally unfazed.

        From HyBi-10, 4.7.
        """

        frame = "\x01\x03Hel\x80\x02lo"
        frames, buf = parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0], (NORMAL, "Hel"))
        self.assertEqual(frames[1], (NORMAL, "lo"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_ping(self):
        """
        From HyBi-10, 4.7.
        """

        frame = "\x89\x05Hello"
        frames, buf = parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (PING, "Hello"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_pong(self):
        """
        From HyBi-10, 4.7.
        """

        frame = "\x8a\x05Hello"
        frames, buf = parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (PONG, "Hello"))
        self.assertEqual(buf, "")


    def test_parse_hybi07_close_empty(self):
        """
        A HyBi-07 close packet may have no body. In that case, it should use
        the generic error code 1000, and have no reason.
        """

        frame = "\x88\x00"
        frames, buf = parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (CLOSE, (1000, "No reason given")))
        self.assertEqual(buf, "")


    def test_parse_hybi07_close_reason(self):
        """
        A HyBi-07 close packet must have its first two bytes be a numeric
        error code, and may optionally include trailing text explaining why
        the connection was closed.
        """

        frame = "\x88\x0b\x03\xe8No reason"
        frames, buf = parse_hybi07_frames(frame)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0], (CLOSE, (1000, "No reason")))
        self.assertEqual(buf, "")


    def test_parse_hybi07_partial_no_length(self):
        frame = "\x81"
        frames, buf = parse_hybi07_frames(frame)
        self.assertFalse(frames)
        self.assertEqual(buf, "\x81")


    def test_parse_hybi07_partial_truncated_length_int(self):
        frame = "\x81\xfe"
        frames, buf = parse_hybi07_frames(frame)
        self.assertFalse(frames)
        self.assertEqual(buf, "\x81\xfe")


    def test_parse_hybi07_partial_truncated_length_double(self):
        frame = "\x81\xff"
        frames, buf = parse_hybi07_frames(frame)
        self.assertFalse(frames)
        self.assertEqual(buf, "\x81\xff")


    def test_parse_hybi07_partial_no_data(self):
        frame = "\x81\x05"
        frames, buf = parse_hybi07_frames(frame)
        self.assertFalse(frames)
        self.assertEqual(buf, "\x81\x05")


    def test_parse_hybi07_partial_truncated_data(self):
        frame = "\x81\x05Hel"
        frames, buf = parse_hybi07_frames(frame)
        self.assertFalse(frames)
        self.assertEqual(buf, "\x81\x05Hel")


    def test_make_hybi07_hello(self):
        frame = "\x81\x05Hello"
        buf = make_hybi07_frame("Hello")
        self.assertEqual(frame, buf)
