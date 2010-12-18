# Copyright (c) 2001-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the FIFO-specific L{FileDescriptor} implementations: L{FIFOReader}
and L{FIFOWriter}
"""

import errno
import os

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ProcessProtocol, Protocol
from twisted.internet.fifo import readFromFIFO, writeToFIFO
from twisted.python.filepath import FilePath
from twisted.test.proto_helpers import AccumulatingProtocol
from twisted.trial import unittest


haveFIFOSupport = getattr(os, 'mkfifo', None) is not None



class CatProtocol(ProcessProtocol):
    """
    L{ProcessProtocol} implementation, used to signal back whenever data is
    received on the "other end" of the FIFO.

    @ivar connectionMadeDeferred: the callback will be fired when the
        connection to the child process has been made
    @type connectionMadeDeferred: L{Deferred}
    """
    def __init__(self):
        self.receivedDeferred = None
        self.processEndedDeferred = None
        self.connectionMadeDeferred = Deferred()


    def connectionMade(self):
        """
        Connection to the child process was made
        """
        ProcessProtocol.connectionMade(self)
        self.connectionMadeDeferred.callback(self)


    def outReceived(self, data):
        """
        Data was received from stdout of the child process.
        Fire L{receivedDeferred}'s callback, if L{waitForData} was previously
        called.
        """
        if self.receivedDeferred is not None:
            d, self.receivedDeferred = self.receivedDeferred, None
            d.callback(data)


    def waitForData(self):
        """
        Wait for data to be received by the process.

        @return: L{Deferred} - the callback will be fired with the data,
            that's going to be received.
        @rtype: L{Deferred}
        """
        self.receivedDeferred = Deferred()
        return self.receivedDeferred


    def processEnded(self, reason):
        """
        Child process has terminated.
        Fire L{processEndedDeferred}'s callback, if L{waitForProcessEnd} was
        previously called.
        """
        if self.processEndedDeferred is not None:
            self.processEndedDeferred.callback(None)


    def waitForProcessEnd(self):
        """
        Wait for the child process to end.

        @return: L{Deferred} - the callback will be fired, when the child
            process has stopped. Its argument should be ignored.
        @rtype: L{Deferred}
        """
        self.processEndedDeferred = Deferred()
        return self.processEndedDeferred



class NotifyingAccumulator(AccumulatingProtocol):
    """
    L{AccumulatingProtocol} that may notify us, that some data was received
    through a callback on a L{Deferred}.
    """
    receivedDeferred = None


    def dataReceived(self, data):
        """
        Some data was received.
        Fire L{receivedDeferred}'s callback, if L{waitForData} was previously
        called.
        """
        AccumulatingProtocol.dataReceived(self, data)
        if self.receivedDeferred is not None:
            d, self.receivedDeferred = self.receivedDeferred, None
            d.callback(data)


    def waitForData(self):
        """
        Wait for some data to be received.

        @return: L{Deferred} - the callback will be fired with the data, that's
            going to be received.
        @rtype: L{Deferred}
        """
        self.receivedDeferred = Deferred()
        return self.receivedDeferred



class FIFOReaderTestCase(unittest.TestCase):
    """
    Test reading from the FIFO.
    """
    if not haveFIFOSupport:
        skip = "Don't have FIFO support on this platform"


    def setUp(self):
        tempdirPath = self.mktemp()
        self.tempdir = FilePath(tempdirPath)
        self.tempdir.makedirs()
        self.fifoPath = self.tempdir.child('test.pipe')
        os.mkfifo(self.fifoPath.path)
        catText = r"""
import sys
f = open(sys.argv[1], 'w')
while True:
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    f.write(line)
    f.flush()
"""
        fd = self.tempdir.child('cat.py').open('w')
        fd.write(catText)
        fd.close()


    def test_startReadingNoWriter(self):
        """
        Starting a read with no writer present.
        """
        proto = AccumulatingProtocol()
        readFromFIFO(reactor, self.fifoPath, proto)
        self.assertTrue(
            proto.made, "Opening the FIFO with O_NONBLOCK must always succeed")
        fifo = proto.transport
        self.addCleanup(fifo.loseConnection)


    def test_reading(self):
        """
        Reading from the reading end of the FIFO.
        """
        fifoProto = NotifyingAccumulator()
        fifoProto.closedDeferred = Deferred()

        readFromFIFO(reactor, self.fifoPath, fifoProto)

        catProto = CatProtocol()

        reactor.spawnProcess(
            catProto, 'python',
            ['python', self.tempdir.child('cat.py').path, self.fifoPath.path],
            env=os.environ)

        def onCatProtoConnMade(ign):
            catProto.transport.write("Line1\n")
            return fifoProto.waitForData().addCallback(firstLineReceived)

        def firstLineReceived(ign):
            self.assertEqual(fifoProto.data, "Line1\n")
            fifoProto.transport.startReading() # This should do nothing at all
            catProto.transport.write("Line2\n")
            return fifoProto.waitForData().addCallback(secondLineReceived)

        def secondLineReceived(ign):
            self.assertEqual(fifoProto.data, "Line1\nLine2\n")
            catProto.transport.loseConnection()
            return fifoProto.closedDeferred.addCallback(afterClosed)

        def afterClosed(ign):
            d = Deferred()
            d.addCallback(
                lambda ign: self.assertRaises(OSError, os.close,
                                              fifoProto.transport._fd))
            reactor.callLater(0, d.callback, None)
            return d
        catProto.connectionMadeDeferred.addCallback(onCatProtoConnMade)
        return catProto.connectionMadeDeferred


    def test_writing(self):
        """
        Attempting to write to the FIFO from the reading end results in a
        L{NotImplementedError} being raised, but the connection should not be
        disturbed.
        """
        fifoProto = NotifyingAccumulator()
        fifoProto.closedDeferred = Deferred()

        readFromFIFO(reactor, self.fifoPath, fifoProto)

        catProto = CatProtocol()

        reactor.spawnProcess(
            catProto, 'python',
            ['python', self.tempdir.child('cat.py').path, self.fifoPath.path],
            env=os.environ)

        def onCatProtoConnMade(ign):
            self.addCleanup(catProto.transport.loseConnection)
            self.assertRaises(NotImplementedError,
                              fifoProto.transport.startWriting)
            catProto.transport.write("Line1\n")
            return fifoProto.waitForData().addCallback(firstLineReceived)

        def firstLineReceived(ign):
            self.assertEqual(fifoProto.data, "Line1\n")
            fifoProto.transport.loseConnection()
            return fifoProto.closedDeferred.addCallback(afterClosed)

        def afterClosed(ign):
            d = Deferred()
            d.addCallback(
                lambda ign: self.assertRaises(OSError, os.close,
                                              fifoProto.transport._fd))
            reactor.callLater(0, d.callback, None)
            return d

        catProto.connectionMadeDeferred.addCallback(onCatProtoConnMade)
        return catProto.connectionMadeDeferred


    def test_writingSideQuit(self):
        """
        Writing side is closed in the middle of the exchange.
        """
        fifoProto = NotifyingAccumulator()
        fifoProto.closedDeferred = Deferred()

        readFromFIFO(reactor, self.fifoPath, fifoProto)

        catProto = CatProtocol()

        reactor.spawnProcess(
            catProto, 'python',
            ['python', self.tempdir.child('cat.py').path, self.fifoPath.path],
            env=os.environ)

        def onCatProtoConnMade(ign):
            self.addCleanup(catProto.transport.loseConnection)
            self.assertRaises(NotImplementedError,
                              fifoProto.transport.startWriting)
            catProto.transport.write("Line1\n")
            return fifoProto.waitForData().addCallback(firstLineReceived)

        def firstLineReceived(ign):
            self.assertEqual(fifoProto.data, "Line1\n")
            catProto.transport.signalProcess("KILL")
            return fifoProto.closedDeferred.addCallback(afterClosed)

        def afterClosed(ign):
            d = Deferred()
            d.addCallback(
                lambda ign: self.assertRaises(OSError, os.close,
                                              fifoProto.transport._fd))
            reactor.callLater(0, d.callback, None)
            return d

        catProto.connectionMadeDeferred.addCallback(onCatProtoConnMade)
        return catProto.connectionMadeDeferred



class FIFOWriterTestCase(unittest.TestCase):
    """
    Test writing to the FIFO.
    """
    if not haveFIFOSupport:
        skip = "Don't have FIFO support on this platform"

    def setUp(self):
        tempdirPath = self.mktemp()
        self.tempdir = FilePath(tempdirPath)
        self.tempdir.makedirs()
        self.fifoPath = self.tempdir.child('test.pipe')
        os.mkfifo(self.fifoPath.path)
        catText = r"""
import sys
f = open(sys.argv[1], 'r', 1)
while True:
    line = f.readline()
    if not line:
        sys.exit(0)
    sys.stdout.write(line)
    sys.stdout.flush()
"""
        fd = self.tempdir.child('cat.py').open('w')
        fd.write(catText)
        fd.close()


    def test_startWritingNoReader(self):
        """
        Starting a write with no reader present results in an L{OSError} with
        errno=ENXIO.
        """
        proto = Protocol()

        try:
            writeToFIFO(reactor, self.fifoPath, proto)
        except OSError, e:
            self.assertEqual(e.errno, errno.ENXIO)
        else:
            self.fail("Attempting to open for writing with O_NONBLOCK when no "
                      "reader is present must always result in ENXIO")


    def test_writing(self):
        """
        Writing to the writing end of the FIFO.
        """
        catProto = CatProtocol()

        reactor.spawnProcess(
            catProto, 'python',
            ['python', self.tempdir.child('cat.py').path, self.fifoPath.path],
            env=os.environ)

        def onCatProtoConnMade(ing):
            d = Deferred()
            d.addCallback(afterCatWait)
            reactor.callLater(0.5, d.callback, None)
            return d

        def afterCatWait(ign):
            self.fifoProto = Protocol()
            writeToFIFO(reactor, self.fifoPath, self.fifoProto)
            self.fifoProto.transport.write("Line1\n")
            return catProto.waitForData().addCallback(firstLineReceived)

        def firstLineReceived(data):
            self.assertEqual(data, "Line1\n")
            self.fifoProto.transport.write("Line2\n")
            return catProto.waitForData().addCallback(secondLineReceived)

        def secondLineReceived(data):
            self.assertEqual(data, "Line2\n")
            self.fifoProto.transport.loseConnection()
            return catProto.waitForProcessEnd().addCallback(afterClosed)

        def afterClosed(ign):
            d = Deferred()
            d.addCallback(
                lambda ign: self.assertRaises(OSError, os.close,
                                              self.fifoProto.transport._fd))
            reactor.callLater(0, d.callback, None)
            return d

        catProto.connectionMadeDeferred.addCallback(onCatProtoConnMade)
        return catProto.connectionMadeDeferred


    def test_reading(self):
        """
        Attempting to read from the FIFO from the writing end results in
        a L{NotImplementedError} being raised, but the connection
        should not be disturbed.
        """
        catProto = CatProtocol()

        reactor.spawnProcess(
            catProto, 'python',
            ['python', self.tempdir.child('cat.py').path, self.fifoPath.path],
            env=os.environ)

        def onCatProtoConnMade(ing):
            d = Deferred()
            d.addCallback(afterCatWait)
            reactor.callLater(0.5, d.callback, None)
            return d

        def afterCatWait(ign):
            self.fifoProto = Protocol()
            writeToFIFO(reactor, self.fifoPath, self.fifoProto)
            self.fifoProto.transport.write("Line1\n")
            return catProto.waitForData().addCallback(firstLineReceived)

        def firstLineReceived(data):
            self.assertEqual(data, "Line1\n")
            self.assertRaises(NotImplementedError,
                              self.fifoProto.transport.startReading)
            self.fifoProto.transport.write("Line2\n")
            return catProto.waitForData().addCallback(secondLineReceived)

        def secondLineReceived(data):
            self.assertEqual(data, "Line2\n")
            self.fifoProto.transport.loseConnection()
            return catProto.waitForProcessEnd().addCallback(afterClosed)

        def afterClosed(ign):
            d = Deferred()
            d.addCallback(
                lambda ign: self.assertRaises(OSError, os.close,
                                              self.fifoProto.transport._fd))
            reactor.callLater(0, d.callback, None)
            return d

        catProto.connectionMadeDeferred.addCallback(onCatProtoConnMade)
        return catProto.connectionMadeDeferred


    def test_readingSideQuit(self):
        """
        Reading side is closed during the exchange.
        """
        self.catProto = CatProtocol()

        reactor.spawnProcess(
            self.catProto, 'python',
            ['python', self.tempdir.child('cat.py').path, self.fifoPath.path],
            env=os.environ)

        def onCatProtoConnMade(ing):
            d = Deferred()
            d.addCallback(afterCatWait)
            reactor.callLater(0.5, d.callback, None)
            return d

        def afterCatWait(ign):
            self.fifoProto = Protocol()
            writeToFIFO(reactor, self.fifoPath, self.fifoProto)
            self.fifoProto.transport.write("Line1\n")
            return self.catProto.waitForData().addCallback(firstLineReceived)

        def firstLineReceived(data):
            self.assertEqual(data, "Line1\n")
            self.catProto.transport.signalProcess("KILL")
            return self.catProto.waitForProcessEnd().addCallback(afterCatQuit)

        def afterCatQuit(ign):
            self.assert_(self.fifoProto.transport.connected,
                        "The transport should stay connected")
            self.catProto = CatProtocol()

            reactor.spawnProcess(
                self.catProto, 'python',
                ['python', self.tempdir.child('cat.py').path,
                 self.fifoPath.path],
                env=os.environ)

            self.catProto.connectionMadeDeferred.addCallback(secondCatStarted)
            return self.catProto.connectionMadeDeferred

        def secondCatStarted(ign):
            d = Deferred()
            d.addCallback(afterSecondCatWait)
            reactor.callLater(0.5, d.callback, None)
            return d

        def afterSecondCatWait(ign):
            self.fifoProto.transport.write("Line2\n")
            return self.catProto.waitForData().addCallback(secondLineReceived)

        def secondLineReceived(data):
            self.assertEqual(data, "Line2\n")
            self.fifoProto.transport.loseConnection()
            return self.catProto.waitForProcessEnd().addCallback(afterClosed)

        def afterClosed(ign):
            d = Deferred()
            d.addCallback(
                lambda ign: self.assertRaises(OSError, os.close,
                                              self.fifoProto.transport._fd))
            reactor.callLater(0, d.callback, None)
            return d

        self.catProto.connectionMadeDeferred.addCallback(onCatProtoConnMade)
        return self.catProto.connectionMadeDeferred
