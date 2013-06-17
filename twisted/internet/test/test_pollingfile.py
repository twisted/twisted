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
    def setUp(self):
        self._oldBufferSize = _pollingfile.FULL_BUFFER_SIZE


    def tearDown(self):
        _pollingfile.FULL_BUFFER_SIZE = self._oldBufferSize


    def test_pushProducerUsingWriteSequence(self):
        """
        Test write pipe as a consumer with a push producer using
        writeSequence().

        Calling writeSequence() should behave the same as calling write()
        with each item, including flow control and disconnect handling.

        Note: test depends on Ticket #2835 resolution.

        See Ticket #6493: writeSequence() doesn't pause the producer when
        outgoing buffer is full.
        """
        pipeSize = 4096  # avoid Ticket #5365 issues
        _pollingfile.FULL_BUFFER_SIZE = 1024
        testMessage = '0' * 1024

        class TestProtocol(basic.LineReceiver):
            def lineReceived(self, line):
                self.testResponse = line
                transport.writer.close()

        class TestProducer(object):
            pauseCount = 0
            def resumeProducing(self):
                transport.writer.writeSequence((testMessage+"\r\n",))

            def pauseProducing(self):
                self.pauseCount += 1

            def stopProducing(self):
                pass

        reactor = self.buildReactor()
        r, w = lambda: reactor.stop(), lambda: None
        protocol, producer = TestProtocol(), TestProducer()
        transport = PipeRunner(pipeSize, r, w, protocol.dataReceived, reactor)
        transport.writer.registerProducer(producer, True)
        producer.resumeProducing()
        self.runReactor(reactor)
        self.assertEqual(testMessage, protocol.testResponse)
        self.assertEqual(1, producer.pauseCount)


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
    TestPollableWritePipeUnicode.skip = skipMessage

