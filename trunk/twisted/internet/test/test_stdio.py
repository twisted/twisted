# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.stdio}.
"""

from twisted.python.runtime import platform
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.protocol import Protocol
if not platform.isWindows():
    from twisted.internet._posixstdio import StandardIO



class StdioFilesTests(ReactorBuilder):
    """
    L{StandardIO} supports reading and writing to filesystem files.
    """

    def setUp(self):
        path = self.mktemp()
        file(path, "w").close()
        self.extraFile = file(path, "r+")


    def test_addReader(self):
        """
        Adding a filesystem file reader to a reactor will make sure it is
        polled.
        """
        reactor = self.buildReactor()

        class DataProtocol(Protocol):
            data = ""
            def dataReceived(self, data):
                self.data += data
                # It'd be better to stop reactor on connectionLost, but that
                # fails on FreeBSD, probably due to
                # http://bugs.python.org/issue9591:
                if self.data == "hello!":
                    reactor.stop()

        path = self.mktemp()
        f = file(path, "w")
        f.write("hello!")
        f.close()
        f = file(path, "r")

        # Read bytes from a file, deliver them to a protocol instance:
        protocol = DataProtocol()
        StandardIO(protocol, stdin=f.fileno(),
                   stdout=self.extraFile.fileno(),
                   reactor=reactor)

        self.runReactor(reactor)
        self.assertEqual(protocol.data, "hello!")


    def test_addWriter(self):
        """
        Adding a filesystem file writer to a reactor will make sure it is
        polled.
        """
        reactor = self.buildReactor()

        class DisconnectProtocol(Protocol):
            def connectionLost(self, reason):
                reactor.stop()

        path = self.mktemp()
        f = file(path, "w")

        # Write bytes to a transport, hopefully have them written to a file:
        protocol = DisconnectProtocol()
        StandardIO(protocol, stdout=f.fileno(),
                   stdin=self.extraFile.fileno(), reactor=reactor)
        protocol.transport.write("hello")
        protocol.transport.write(", world")
        protocol.transport.loseConnection()

        self.runReactor(reactor)
        f.close()
        f = file(path, "r")
        self.assertEqual(f.read(), "hello, world")
        f.close()


    def test_removeReader(self):
        """
        Removing a filesystem file reader from a reactor will make sure it is
        no longer polled.
        """
        reactor = self.buildReactor()
        self.addCleanup(self.unbuildReactor, reactor)

        path = self.mktemp()
        file(path, "w").close()
        # Cleanup might fail if file is GCed too soon:
        self.f = f = file(path, "r")

        # Have the reader added:
        stdio = StandardIO(Protocol(), stdin=f.fileno(),
                           stdout=self.extraFile.fileno(),
                           reactor=reactor)
        self.assertIn(stdio._reader, reactor.getReaders())
        stdio._reader.stopReading()
        self.assertNotIn(stdio._reader, reactor.getReaders())


    def test_removeWriter(self):
        """
        Removing a filesystem file writer from a reactor will make sure it is
        no longer polled.
        """
        reactor = self.buildReactor()
        self.addCleanup(self.unbuildReactor, reactor)

        # Cleanup might fail if file is GCed too soon:
        self.f = f = file(self.mktemp(), "w")

        # Have the reader added:
        protocol = Protocol()
        stdio = StandardIO(protocol, stdout=f.fileno(),
                           stdin=self.extraFile.fileno(),
                           reactor=reactor)
        protocol.transport.write("hello")
        self.assertIn(stdio._writer, reactor.getWriters())
        stdio._writer.stopWriting()
        self.assertNotIn(stdio._writer, reactor.getWriters())


    def test_removeAll(self):
        """
        Calling C{removeAll} on a reactor includes descriptors that are
        filesystem files.
        """
        reactor = self.buildReactor()
        self.addCleanup(self.unbuildReactor, reactor)

        path = self.mktemp()
        file(path, "w").close()
        # Cleanup might fail if file is GCed too soon:
        self.f = f = file(path, "r")

        # Have the reader added:
        stdio = StandardIO(Protocol(), stdin=f.fileno(),
                           stdout=self.extraFile.fileno(), reactor=reactor)
        # And then removed:
        removed = reactor.removeAll()
        self.assertIn(stdio._reader, removed)
        self.assertNotIn(stdio._reader, reactor.getReaders())


    def test_getReaders(self):
        """
        C{reactor.getReaders} includes descriptors that are filesystem files.
        """
        reactor = self.buildReactor()
        self.addCleanup(self.unbuildReactor, reactor)

        path = self.mktemp()
        file(path, "w").close()
        # Cleanup might fail if file is GCed too soon:
        self.f = f = file(path, "r")

        # Have the reader added:
        stdio = StandardIO(Protocol(), stdin=f.fileno(),
                           stdout=self.extraFile.fileno(), reactor=reactor)
        self.assertIn(stdio._reader, reactor.getReaders())


    def test_getWriters(self):
        """
        C{reactor.getWriters} includes descriptors that are filesystem files.
        """
        reactor = self.buildReactor()
        self.addCleanup(self.unbuildReactor, reactor)

        # Cleanup might fail if file is GCed too soon:
        self.f = f = file(self.mktemp(), "w")

        # Have the reader added:
        stdio = StandardIO(Protocol(), stdout=f.fileno(),
                           stdin=self.extraFile.fileno(), reactor=reactor)
        self.assertNotIn(stdio._writer, reactor.getWriters())
        stdio._writer.startWriting()
        self.assertIn(stdio._writer, reactor.getWriters())

    if platform.isWindows():
        skip = ("StandardIO does not accept stdout as an argument to Windows.  "
                "Testing redirection to a file is therefore harder.")


globals().update(StdioFilesTests.makeTestCaseClasses())
