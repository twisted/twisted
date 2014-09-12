# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet._pollingfile}.
"""

from twisted.python.runtime import platform
from twisted.trial.unittest import TestCase

if platform.isWindows():
    from twisted.internet import _pollingfile
else:
    _pollingfile = None


class TestPollableWritePipe(TestCase):
    """
    Tests for L{_pollingfile._PollableWritePipe}.
    """

    def test_checkWorkUnicode(self):
        """
        When one tries to pass unicode to L{_pollingfile._PollableWritePipe}, a
        C{TypeError} is raised instead of passing the data to C{WriteFile}
        call which is going to mangle it.
        """
        p = _pollingfile._PollableWritePipe(1, lambda: None)
        p.write("test")
        p.checkWork()
        self.assertRaises(TypeError, p.write, u"test")

    def test_writeSequenceUnicode(self):
        """
        L{_pollingfile._PollableWritePipe.writeSequence} raises a C{TypeError}
        if unicode data is part of the data sequence to be appended to the
        output buffer.
        """
        p = _pollingfile._PollableWritePipe(1, lambda: None)
        
        self.assertRaises(TypeError, p.writeSequence, [u"test"])
        
        self.assertRaises(TypeError, p.writeSequence, (u"test",))


if _pollingfile is None:
    TestPollableWritePipe.skip = "Test will run only on Windows."
