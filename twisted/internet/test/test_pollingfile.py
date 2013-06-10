# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet._pollingfile}.
"""
import os

from twisted.python.runtime import platform
from twisted.trial.unittest import TestCase
from twisted.protocols import basic
from twisted.internet.test.reactormixins import ReactorBuilder



if platform.isWindows():
    import win32pipe
    import win32security

    from twisted.internet import _pollingfile

    from twisted.internet._pollingfile import _PollingTimer
    _skipNotWindows = None
else:
    _skipNotWindows = "Test will run only on Windows."
    _PollingTimer = object



class PipeRunner(_PollingTimer):
    """
    Builds, initializes and runs a pair of read/write pipes.
    """
    def __init__(self, pipeSize, doneReadCB, doneWriteCB, receivedCB, reactor):
        _PollingTimer.__init__(self, reactor)
        sAttrs = win32security.SECURITY_ATTRIBUTES()
        sAttrs.bInheritHandle = 1
        hRead, hWrite = win32pipe.CreatePipe(sAttrs, pipeSize)
        self.reader = _pollingfile._PollableReadPipe(hRead, receivedCB, doneReadCB)
        self.writer = _pollingfile._PollableWritePipe(hWrite, doneWriteCB)
        self._addPollableResource(self.reader)
        self._addPollableResource(self.writer)



class TestPollablePipes(ReactorBuilder):
    """
    Tests for L{_pollingfile._PollableWritePipe} and
    L{_pollingfile._PollableReadPipe}.
    """
    def test_pipeBufferSize(self):
        """
        This test times-out with the existing _pollingfile implementation.

        See Ticket #5365: _pollingfile assumes that (win32 API) WriteFile()
        will allow a partial write, but WriteFile() writes either all or
        nothing. Which means if you try to write too much at once in a pipe's
        buffer, the _PollableWritePipe sits there doing nothing.
        """
        self.timeout = 15.0             # shorten test timeout
        pipeSize     = 512              # set a small pipe buffer size
        testMessage  = '%02048d' % 0    # send a long messages

        class TestProtocol(basic.LineReceiver):
            def lineReceived(self, line):
                self.testResponse = line
                transport.writer.close()

        reactor = self.buildReactor()
        r, w = lambda: reactor.stop(), lambda: None
        protocol = TestProtocol()
        transport = PipeRunner(pipeSize, r, w, protocol.dataReceived, reactor)
        transport.writer.write(testMessage+'\r\n')
        self.runReactor(reactor)
        self.assertEqual(testMessage, protocol.testResponse)


globals().update(TestPollablePipes.makeTestCaseClasses())


class TestPollableWritePipe(TestCase):
    """
    Tests for L{_pollingfile._PollableWritePipe}.
    """

    def test_writeUnicode(self):
        """
        L{_pollingfile._PollableWritePipe.write} raises a C{TypeError} if an
        attempt is made to append unicode data to the output buffer.
        """
        p = _pollingfile._PollableWritePipe(1, lambda: None)
        self.assertRaises(TypeError, p.write, u"test")


    def test_writeSequenceUnicode(self):
        """
        L{_pollingfile._PollableWritePipe.writeSequence} raises a C{TypeError}
        if unicode data is part of the data sequence to be appended to the
        output buffer.
        """
        p = _pollingfile._PollableWritePipe(1, lambda: None)
        self.assertRaises(TypeError, p.writeSequence, [u"test"])
        self.assertRaises(TypeError, p.writeSequence, (u"test", ))



if _skipNotWindows:
    TestPollablePipes.skip = skipMessage
    TestPollableWritePipe.skip = skipMessage
