# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.logger._capture}.
"""

from twisted.logger import Logger, LogLevel
from twisted.trial.unittest import TestCase

from .._capture import LogCapture



class LogCaptureTests(TestCase):
    """
    Tests for L{LogCaptureTests}.
    """

    log = Logger()


    def test_capture(self):
        """
        Events logged within context are captured.
        """
        foo = object()

        with LogCapture() as capture:
            self.log.debug("Capture this, please", foo=foo)
            self.log.info("Capture this too, please", foo=foo)

            events = capture.events

        self.assertTrue(len(events) == 2)
        self.assertEqual(events[0]["log_format"], "Capture this, please")
        self.assertEqual(events[0]["log_level"], LogLevel.debug)
        self.assertEqual(events[0]["foo"], foo)
        self.assertEqual(events[1]["log_format"], "Capture this too, please")
        self.assertEqual(events[1]["log_level"], LogLevel.info)
        self.assertEqual(events[1]["foo"], foo)


    def test_asText(self):
        """
        L{LogCapture.asText} returns the captured logs as text.
        """
        foo = object()

        with LogCapture() as capture:
            self.log.debug("Capture this, please", foo=foo)
            self.log.info("Capture this too, please", foo=foo)

            text = capture.asText()

        lines = text.split("\n")

        self.assertTrue(len(lines) == 3)
        self.assertTrue(
            lines[0].endswith(
                " [twisted.logger.test.test_capture.LogCaptureTests#debug]"
                " Capture this, please"
            )
        )
        self.assertTrue(
            lines[1].endswith(
                " [twisted.logger.test.test_capture.LogCaptureTests#info]"
                " Capture this too, please"
            )
        )
        self.assertEqual(lines[2], "")
