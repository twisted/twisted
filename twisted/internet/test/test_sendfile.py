# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for sendfile integration in the reactor.
"""

import socket

from twisted.trial.unittest import TestCase, SkipTest
from twisted.internet._sendfile import SendfileInfo
from twisted.internet import error, _sendfile
from twisted.internet.interfaces import IReactorFDSet
from twisted.python import log
from twisted.python.filepath import FilePath
from twisted.python.deprecate import _fullyQualifiedName as fullyQualifiedName

if _sendfile.sendfile is None:
    sendfileSkip = "sendfile not available"
else:
    sendfileSkip = None



class SendfileIntegrationMixin(object):
    """
    Tests for
    L{writeFile<twisted.internet.interfaces.IWriteFileTransport.writeFile>}.
    """

    def createFile(self):
        """
        Create a file to send during tests.

        @return: A file opened ready to be sent.
        """
        path = FilePath(self.mktemp())
        path.setContent(b'x' * 1000000)
        f = path.open()
        self.addCleanup(f.close)
        return f


    def test_writeFileServer(self):
        """
        C{IWriteFileTransport.writeFile} sends the whole content of a file over
        the wire.
        """
        clients = []

        def connected(protocols):
            client, server = protocols[:2]
            clients.append(client)
            fileObject = self.createFile()
            doneDeferred = server.transport.writeFile(fileObject)
            return doneDeferred.addBoth(finished, server)

        def finished(passthrough, server):
            server.transport.loseConnection()
            return passthrough

        reactor = self.buildReactor()
        d = self.getConnectedClientAndServer(
            reactor, "127.0.0.1", socket.AF_INET)
        d.addCallback(connected)
        d.addErrback(log.err)
        self.runReactor(reactor)

        self.assertEqual(1000000, len(clients[0].data))


    def test_writeFileClient(self):
        """
        C{IWriteFileTransport.writeFile} works from client transport side as
        well.
        """
        servers = []

        def connected(protocols):
            client, server = protocols[:2]
            servers.append(server)
            fileObject = self.createFile()
            doneDeferred = client.transport.writeFile(fileObject)
            return doneDeferred.addBoth(finished, client)

        def finished(passthrough, client):
            client.transport.loseConnection()
            return passthrough

        reactor = self.buildReactor()
        d = self.getConnectedClientAndServer(
            reactor, "127.0.0.1", socket.AF_INET)
        d.addCallback(connected)
        d.addErrback(log.err)
        self.runReactor(reactor)

        self.assertEqual(1000000, len(servers[0].data))


    def test_writeFilePendingData(self):
        """
        C{IWriteFileTransport.writeFile} doesn't take precedence over previous
        C{ITCPTransport.write} calls, the data staying in the same order.
        """
        clients = []

        def connected(protocols):
            client, server = protocols[:2]
            clients.append(client)
            server.transport.write(b'y' * 10)
            fileObject = self.createFile()
            doneDeferred = server.transport.writeFile(fileObject)
            return doneDeferred.addBoth(finished, server)

        def finished(passthrough, server):
            server.transport.loseConnection()
            return passthrough

        reactor = self.buildReactor()
        d = self.getConnectedClientAndServer(
            reactor, "127.0.0.1", socket.AF_INET)
        d.addCallback(connected)
        d.addErrback(log.err)
        self.runReactor(reactor)

        data = clients[0].data
        self.assertEqual(1000010, len(data))
        self.assertEqual(b'y' * 10, data[:10])
        self.assertEqual(b'x' * 10, data[10:20])


    def test_writeFileStopWriting(self):
        """
        At the end of a successfull C{IWriteFileTransport.writeFile} call, the
        transport is unregistered from the reactor as there is no pending data
        to send.
        """
        reactor = self.buildReactor()
        if not IReactorFDSet.providedBy(reactor):
            raise SkipTest("%s does not provide IReactorFDSet" % (
                fullyQualifiedName(reactor.__class__),))

        clients = []

        def connected(protocols):
            client, server = protocols[:2]
            clients.append(client)
            fileObject = self.createFile()
            doneDeferred = server.transport.writeFile(fileObject)
            return doneDeferred.addCallback(checkServer, server)

        def checkServer(ign, server):
            # Leave room for the reactor to notice the unregister
            reactor.callLater(0, checkWriter, server)

        def checkWriter(server):
            self.assertNotIn(server.transport, reactor.getWriters())
            server.transport.write(b"x")
            server.transport.loseConnection()

        d = self.getConnectedClientAndServer(
            reactor, "127.0.0.1", socket.AF_INET)
        d.addCallback(connected)
        d.addErrback(log.err)
        self.runReactor(reactor)

        self.assertEqual(1000001, len(clients[0].data))


    def test_writeFileError(self):
        """
        When an error happens during the C{IWriteFileTransport.writeFile} call,
        the L{Deferred} returned is fired with that error. We simulate that
        case by patching C{sendfile} after the first call, and make sure that
        we get the error and that transfer is interrupted.
        """
        originalSendfile = _sendfile.sendfile
        calls = []
        clients = []

        def sendError(*args):
            if not calls:
                calls.append(None)
                return originalSendfile(*args)
            raise IOError("That's bad!")

        self.patch(_sendfile, "sendfile", sendError)

        def connected(protocols):
            client, server = protocols[:2]
            clients.append(client)
            fileObject = self.createFile()
            sendFileDeferred = server.transport.writeFile(fileObject)
            return sendFileDeferred.addErrback(serverFinished)

        def serverFinished(error):
            error.trap(IOError)

        reactor = self.buildReactor()
        d = self.getConnectedClientAndServer(
            reactor, "127.0.0.1", socket.AF_INET)
        d.addCallback(connected)
        d.addErrback(log.err)
        self.runReactor(reactor)

        client = clients[0]
        self.assertIsInstance(client.closedReason.value, error.ConnectionDone)
        self.assertTrue(len(client.data) < 1000000, len(client.data))

    if sendfileSkip:
        test_writeFileError.skip = sendfileSkip


    def test_writeFileErrorAtFirstSight(self):
        """
        If the C{sendfile} system calls fails at the start of the transfer with
        an C{IOError}, C{IWriteFileTransport.writeFile} falls back to a
        standard producer.
        """
        clients = []

        def sendError(*args):
            raise IOError("That's bad!")

        self.patch(_sendfile, "sendfile", sendError)

        def connected(protocols):
            client, server = protocols[:2]
            clients.append(client)
            fileObject = self.createFile()
            doneDeferred = server.transport.writeFile(fileObject)
            return doneDeferred.addBoth(finished, server)

        def finished(passthrough, server):
            server.transport.loseConnection()
            return passthrough

        reactor = self.buildReactor()
        d = self.getConnectedClientAndServer(
            reactor, "127.0.0.1", socket.AF_INET)
        d.addCallback(connected)
        d.addErrback(log.err)
        self.runReactor(reactor)

        self.assertEqual(1000000, len(clients[0].data))

    if sendfileSkip:
        test_writeFileErrorAtFirstSight.skip = sendfileSkip



class SendfileInfoTestCase(TestCase):
    """
    Tests for L{SendfileInfo}.
    """

    def test_lengthDetection(self):
        """
        L{SendfileInfo} is able to detect the file length and preserves the
        file position when doing so.
        """
        path = FilePath(self.mktemp())
        path.setContent(b'x' * 42)
        f = path.open()
        f.seek(7)
        self.addCleanup(f.close)
        sfi = SendfileInfo(f)
        self.assertEqual(sfi.count, 42)
        self.assertEqual(f.tell(), 7)
