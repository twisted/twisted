# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""FTP tests.

Maintainer: U{Andrew Bennetts<mailto:spiv@twistedmatrix.com>}
"""

from __future__ import nested_scopes

import sys, types, os.path, re
from StringIO import StringIO
import shutil

from zope.interface import implements

from twisted import internet
from twisted.trial import unittest
from twisted.trial.util import wait
from twisted.protocols import basic
from twisted.internet import reactor, protocol, defer, interfaces, error
from twisted.cred import portal, checkers, credentials
from twisted.python import log, components, failure
from twisted.internet.address import IPv4Address

from twisted.protocols import ftp, loopback

class NonClosingStringIO(StringIO):
    def close(self):
        pass

StringIOWithoutClosing = NonClosingStringIO




class Dummy(basic.LineReceiver):
    logname = None
    def __init__(self):
        self.lines = []
        self.rawData = []
    def connectionMade(self):
        self.f = self.factory   # to save typing in pdb :-)
    def lineReceived(self,line):
        self.lines.append(line)
    def rawDataReceived(self, data):
        self.rawData.append(data)
    def lineLengthExceeded(self, line):
        pass


class _BufferingProtocol(protocol.Protocol):
    def connectionMade(self):
        self.buffer = ''
        self.d = defer.Deferred()
    def dataReceived(self, data):
        self.buffer += data
    def connectionLost(self, reason):
        self.d.callback(None)


class FTPServerTestCase(unittest.TestCase):
    """Simple tests for an FTP server with the default settings."""

    def setUp(self):
        # Create a directory
        self.directory = self.mktemp()
        os.mkdir(self.directory)

        # Start the server
        p = portal.Portal(ftp.FTPRealm(self.directory))
        p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)
        self.factory = ftp.FTPFactory(portal=p)
        self.port = reactor.listenTCP(0, self.factory, interface="127.0.0.1")

        # Hook the server's buildProtocol to make the protocol instance
        # accessible to tests.
        buildProtocol = self.factory.buildProtocol
        def _rememberProtocolInstance(addr):
            protocol = buildProtocol(addr)
            self.serverProtocol = protocol.wrappedProtocol
            return protocol
        self.factory.buildProtocol = _rememberProtocolInstance

        # Connect a client to it
        portNum = self.port.getHost().port
        clientCreator = protocol.ClientCreator(reactor, ftp.FTPClientBasic)
        self.client = wait(clientCreator.connectTCP("127.0.0.1", portNum))

    def tearDown(self):
        # Clean up sockets
        self.client.transport.loseConnection()
        d = defer.maybeDeferred(self.port.stopListening)
        d.addCallback(self.ebTearDown)
        return d

    def ebTearDown(self, ignore):
        del self.serverProtocol
        # Clean up temporary directory
        shutil.rmtree(self.directory)

    def _waitForCommandFailure(self, deferred):
        try:
            responseLines = wait(deferred)
        except ftp.CommandFailed, e:
            return e.args[0]
        else:
            self.fail('ftp.CommandFailed not raised for command, got %r'
                      % (responseLines,))

    def _anonymousLogin(self):
        responseLines = wait(self.client.queueStringCommand('USER anonymous'))
        self.assertEquals(
            ['331 Guest login ok, type your email address as password.'],
            responseLines
        )

        responseLines = wait(self.client.queueStringCommand(
            'PASS test@twistedmatrix.com')
        )
        self.assertEquals(
            ['230 Anonymous login ok, access restrictions apply.'],
            responseLines
        )


class BasicFTPServerTestCase(FTPServerTestCase):
    def testNotLoggedInReply(self):
        """When not logged in, all commands other than USER and PASS should
        get NOT_LOGGED_IN errors.
        """
        commandList = ['CDUP', 'CWD', 'LIST', 'MODE', 'PASV',
                       'PWD', 'RETR', 'STRU', 'SYST', 'TYPE']

        # Issue commands, check responses
        for command in commandList:
            deferred = self.client.queueStringCommand(command)
            failureResponseLines = self._waitForCommandFailure(deferred)
            self.failUnless(failureResponseLines[-1].startswith("530"),
                            "Response didn't start with 530: %r"
                            % (failureResponseLines[-1],))

    def testPASSBeforeUSER(self):
        """Issuing PASS before USER should give an error."""
        d = self.client.queueStringCommand('PASS foo')
        self.failUnlessEqual(
            ["503 Incorrect sequence of commands: "
             "USER required before PASS"],
            self._waitForCommandFailure(d))

    def testNoParamsForUSER(self):
        """Issuing USER without a username is a syntax error."""
        d = self.client.queueStringCommand('USER')
        self.failUnlessEqual(
            ['500 Syntax error: USER requires an argument.'],
            self._waitForCommandFailure(d))

    def testNoParamsForPASS(self):
        """Issuing PASS without a password is a syntax error."""
        wait(self.client.queueStringCommand('USER foo'))
        d = self.client.queueStringCommand('PASS')
        self.failUnlessEqual(
            ['500 Syntax error: PASS requires an argument.'],
            self._waitForCommandFailure(d))

    def testAnonymousLogin(self):
        self._anonymousLogin()

    def testQuit(self):
        """Issuing QUIT should return a 221 message."""
        self._anonymousLogin()
        return self.client.queueStringCommand('QUIT').addCallback(self.assertEquals, ['221 Goodbye.'])

    def testAnonymousLoginDenied(self):
        # Reconfigure the server to disallow anonymous access, and to have an
        # IUsernamePassword checker that always rejects.
        self.factory.allowAnonymous = False
        denyAlwaysChecker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        self.factory.portal.registerChecker(denyAlwaysChecker,
                                            credentials.IUsernamePassword)

        # Same response code as allowAnonymous=True, but different text.
        responseLines = wait(self.client.queueStringCommand('USER anonymous'))
        self.assertEquals(
            ['331 Password required for anonymous.'], responseLines
        )

        # It will be denied.  No-one can login.
        d = self.client.queueStringCommand('PASS test@twistedmatrix.com')
        self.failUnlessEqual(
            ['530 Sorry, Authentication failed.'],
            self._waitForCommandFailure(d))

        # It's not just saying that.  You aren't logged in.
        d = self.client.queueStringCommand('PWD')
        self.failUnlessEqual(
            ['530 Please login with USER and PASS.'],
            self._waitForCommandFailure(d))

    def testUnknownCommand(self):
        self._anonymousLogin()

        d = self.client.queueStringCommand('GIBBERISH')
        self.failUnlessEqual(
            ["502 Command 'GIBBERISH' not implemented"],
            self._waitForCommandFailure(d))


    def testRETRBeforePORT(self):
        self._anonymousLogin()
        d = self.client.queueStringCommand('RETR foo')
        self.failUnlessEqual(
            ["503 Incorrect sequence of commands: "
             "PORT or PASV required before RETR"],
            self._waitForCommandFailure(d))

    def testSTORBeforePORT(self):
        self._anonymousLogin()
        d = self.client.queueStringCommand('STOR foo')
        self.failUnlessEqual(
            ["503 Incorrect sequence of commands: "
             "PORT or PASV required before STOR"],
            self._waitForCommandFailure(d))

    def testBadCommandArgs(self):
        self._anonymousLogin()
        d = self.client.queueStringCommand('MODE z')
        self.failUnlessEqual(
            ["504 Not implemented for parameter 'z'."],
            self._waitForCommandFailure(d))

        d = self.client.queueStringCommand('STRU I')
        self.failUnlessEqual(
            ["504 Not implemented for parameter 'I'."],
            self._waitForCommandFailure(d))

    def testDecodeHostPort(self):
        self.assertEquals(ftp.decodeHostPort('25,234,129,22,100,23'),
                ('25.234.129.22', 25623))

    def testPASV(self):
        # Login
        self._anonymousLogin()

        # Issue a PASV command, and extract the host and port from the response
        responseLines = wait(self.client.queueStringCommand('PASV'))
        host, port = ftp.decodeHostPort(responseLines[-1][4:])

        # Make sure the server is listening on the port it claims to be
        self.assertEqual(port, self.serverProtocol.dtpPort.getHost().port)

        # Semi-reasonable way to force cleanup
        self.serverProtocol.connectionLost(error.ConnectionDone())


    def testSYST(self):
        self._anonymousLogin()
        responseLines = wait(self.client.queueStringCommand('SYST'))
        self.assertEqual(["215 UNIX Type: L8"], responseLines)

class FTPServerPasvDataConnectionTestCase(FTPServerTestCase):
    def _makeDataConnection(self):
        # Establish a passive data connection (i.e. client connecting to
        # server).
        responseLines = wait(self.client.queueStringCommand('PASV'))
        host, port = ftp.decodeHostPort(responseLines[-1][4:])
        downloader = wait(
            protocol.ClientCreator(reactor,
                                   _BufferingProtocol).connectTCP('127.0.0.1',
                                                                  port)
        )
        return downloader

    def testLIST(self):
        # Login
        self._anonymousLogin()

        # Download a listing
        downloader = self._makeDataConnection()
        d = self.client.queueStringCommand('LIST')
        wait(defer.gatherResults([d, downloader.d]))

        # No files, so the file listing should be empty
        self.assertEqual('', downloader.buffer)

        # Make some directories
        os.mkdir(os.path.join(self.directory, 'foo'))
        os.mkdir(os.path.join(self.directory, 'bar'))

        # Download a listing again
        downloader = self._makeDataConnection()
        d = self.client.queueStringCommand('LIST')
        wait(defer.gatherResults([d, downloader.d]))

        # Now we expect 2 lines because there are two files.
        self.assertEqual(2, len(downloader.buffer[:-2].split('\r\n')))

        # Download a names-only listing
        downloader = self._makeDataConnection()
        d = self.client.queueStringCommand('NLST ')
        wait(defer.gatherResults([d, downloader.d]))
        filenames = downloader.buffer[:-2].split('\r\n')
        filenames.sort()
        self.assertEqual(['bar', 'foo'], filenames)

        # Download a listing of the 'foo' subdirectory
        downloader = self._makeDataConnection()
        d = self.client.queueStringCommand('LIST foo')
        wait(defer.gatherResults([d, downloader.d]))

        # 'foo' has no files, so the file listing should be empty
        self.assertEqual('', downloader.buffer)

        # Change the current working directory to 'foo'
        wait(self.client.queueStringCommand('CWD foo'))

        # Download a listing from within 'foo', and again it should be empty
        downloader = self._makeDataConnection()
        d = self.client.queueStringCommand('LIST')
        wait(defer.gatherResults([d, downloader.d]))
        self.assertEqual('', downloader.buffer)

    def testManyLargeDownloads(self):
        # Login
        self._anonymousLogin()


        # Download a range of different size files
        for size in range(100000, 110000, 500):
            fObj = file(os.path.join(self.directory, '%d.txt' % (size,)), 'wb')
            fObj.write('x' * size)
            fObj.close()

            downloader = self._makeDataConnection()
            d = self.client.queueStringCommand('RETR %d.txt' % (size,))
            wait(defer.gatherResults([d, downloader.d]))
            self.assertEqual('x' * size, downloader.buffer)


class FTPServerPortDataConnectionTestCase(FTPServerPasvDataConnectionTestCase):
    def setUp(self):
        FTPServerPasvDataConnectionTestCase.setUp(self)
        self.dataPorts = []

    def _makeDataConnection(self):
        # Establish an active data connection (i.e. server connecting to
        # client).
        deferred = defer.Deferred()
        class DataFactory(protocol.ServerFactory):
            protocol = _BufferingProtocol
            def buildProtocol(self, addr):
                p = protocol.ServerFactory.buildProtocol(self, addr)
                reactor.callLater(0, deferred.callback, p)
                return p
        dataPort = reactor.listenTCP(0, DataFactory(), interface='127.0.0.1')
        self.dataPorts.append(dataPort)
        cmd = 'PORT ' + ftp.encodeHostPort('127.0.0.1', dataPort.getHost().port)
        responseLines = wait(self.client.queueStringCommand(cmd))
        downloader = wait(deferred)
        return downloader

    def tearDown(self):
        l = [defer.maybeDeferred(port.stopListening) for port in self.dataPorts]
        wait(defer.DeferredList(l, fireOnOneErrback=True))
        return FTPServerPasvDataConnectionTestCase.tearDown(self)

    def testPORTCannotConnect(self):
        # Login
        self._anonymousLogin()

        # Listen on a port, and immediately stop listening as a way to find a
        # port number that is definitely closed.
        port = reactor.listenTCP(0, protocol.Factory(), interface='127.0.0.1')
        portNum = port.getHost().port
        d = port.stopListening()
        if d is not None:
            wait(d)

        # Tell the server to connect to that port with a PORT command, and
        # verify that it fails with the right error.
        cmd = 'PORT ' + ftp.encodeHostPort('127.0.0.1', portNum)
        d = self.client.queueStringCommand(cmd)
        self.failUnlessEqual(
            ["425 Can't open data connection."],
            self._waitForCommandFailure(d)
        )


# -- Client Tests -----------------------------------------------------------

class PrintLines(protocol.Protocol):
    """Helper class used by FTPFileListingTests."""

    def __init__(self, lines):
        self._lines = lines

    def connectionMade(self):
        for line in self._lines:
            self.transport.write(line + "\r\n")
        self.transport.loseConnection()


class MyFTPFileListProtocol(ftp.FTPFileListProtocol):
    def __init__(self):
        self.other = []
        ftp.FTPFileListProtocol.__init__(self)

    def unknownLine(self, line):
        self.other.append(line)


class FTPFileListingTests(unittest.TestCase):
    def getFilesForLines(self, lines):
        fileList = MyFTPFileListProtocol()
        loopback.loopback(PrintLines(lines), fileList)
        return fileList.files, fileList.other

    def testOneLine(self):
        # This example line taken from the docstring for FTPFileListProtocol
        line = '-rw-r--r--   1 root     other        531 Jan 29 03:26 README'
        (file,), other = self.getFilesForLines([line])
        self.failIf(other, 'unexpect unparsable lines: %s' % repr(other))
        self.failUnless(file['filetype'] == '-', 'misparsed fileitem')
        self.failUnless(file['perms'] == 'rw-r--r--', 'misparsed perms')
        self.failUnless(file['owner'] == 'root', 'misparsed fileitem')
        self.failUnless(file['group'] == 'other', 'misparsed fileitem')
        self.failUnless(file['size'] == 531, 'misparsed fileitem')
        self.failUnless(file['date'] == 'Jan 29 03:26', 'misparsed fileitem')
        self.failUnless(file['filename'] == 'README', 'misparsed fileitem')
        self.failUnless(file['nlinks'] == 1, 'misparsed nlinks')
        self.failIf(file['linktarget'], 'misparsed linktarget')

    def testVariantLines(self):
        line1 = 'drw-r--r--   2 root     other        531 Jan  9  2003 A'
        line2 = 'lrw-r--r--   1 root     other          1 Jan 29 03:26 B -> A'
        line3 = 'woohoo! '
        (file1, file2), (other,) = self.getFilesForLines([line1, line2, line3])
        self.failUnless(other == 'woohoo! \r', 'incorrect other line')
        # file 1
        self.failUnless(file1['filetype'] == 'd', 'misparsed fileitem')
        self.failUnless(file1['perms'] == 'rw-r--r--', 'misparsed perms')
        self.failUnless(file1['owner'] == 'root', 'misparsed owner')
        self.failUnless(file1['group'] == 'other', 'misparsed group')
        self.failUnless(file1['size'] == 531, 'misparsed size')
        self.failUnless(file1['date'] == 'Jan  9  2003', 'misparsed date')
        self.failUnless(file1['filename'] == 'A', 'misparsed filename')
        self.failUnless(file1['nlinks'] == 2, 'misparsed nlinks')
        self.failIf(file1['linktarget'], 'misparsed linktarget')
        # file 2
        self.failUnless(file2['filetype'] == 'l', 'misparsed fileitem')
        self.failUnless(file2['perms'] == 'rw-r--r--', 'misparsed perms')
        self.failUnless(file2['owner'] == 'root', 'misparsed owner')
        self.failUnless(file2['group'] == 'other', 'misparsed group')
        self.failUnless(file2['size'] == 1, 'misparsed size')
        self.failUnless(file2['date'] == 'Jan 29 03:26', 'misparsed date')
        self.failUnless(file2['filename'] == 'B', 'misparsed filename')
        self.failUnless(file2['nlinks'] == 1, 'misparsed nlinks')
        self.failUnless(file2['linktarget'] == 'A', 'misparsed linktarget')

    def testUnknownLine(self):
        files, others = self.getFilesForLines(['ABC', 'not a file'])
        self.failIf(files, 'unexpected file entries')
        self.failUnless(others == ['ABC\r', 'not a file\r'],
                        'incorrect unparsable lines: %s' % repr(others))

    def testYear(self):
        # This example derived from bug description in issue 514.
        fileList = ftp.FTPFileListProtocol()
        class PrintLine(protocol.Protocol):
            def connectionMade(self):
                self.transport.write('-rw-r--r--   1 root     other        531 Jan 29 2003 README\n')
                self.transport.loseConnection()
        loopback.loopback(PrintLine(), fileList)
        file = fileList.files[0]
        self.failUnless(file['size'] == 531, 'misparsed fileitem')
        self.failUnless(file['date'] == 'Jan 29 2003', 'misparsed fileitem')
        self.failUnless(file['filename'] == 'README', 'misparsed fileitem')


class FTPClientTests(unittest.TestCase):
    def testFailedRETR(self):
        try:
            f = protocol.Factory()
            f.noisy = 0
            port = reactor.listenTCP(0, f, interface="127.0.0.1")
            portNum = port.getHost().port
            # This test data derived from a bug report by ranty on #twisted
            responses = ['220 ready, dude (vsFTPd 1.0.0: beat me, break me)',
                         # USER anonymous
                         '331 Please specify the password.',
                         # PASS twisted@twistedmatrix.com
                         '230 Login successful. Have fun.',
                         # TYPE I
                         '200 Binary it is, then.',
                         # PASV
                         '227 Entering Passive Mode (127,0,0,1,%d,%d)' %
                         (portNum >> 8, portNum & 0xff),
                         # RETR /file/that/doesnt/exist
                         '550 Failed to open file.']
            f.buildProtocol = lambda addr: PrintLines(responses)

            client = ftp.FTPClient(passive=1)
            cc = protocol.ClientCreator(reactor, ftp.FTPClient, passive=1)
            client = wait(cc.connectTCP('127.0.0.1', portNum))
            p = protocol.Protocol()
            d = client.retrieveFile('/file/that/doesnt/exist', p)

            # This callback should not be called, because we're expecting a
            # failure.
            d.addCallback(lambda r, self=self:
                            self.fail('Callback incorrectly called: %r' % r))
            def p(failure):
                # Make sure we got the failure we were expecting.
                failure.trap(ftp.CommandFailed)
            d.addErrback(p)

            wait(d)
            log.flushErrors(ftp.FTPError)
        finally:
            d = port.stopListening()
            if d is not None:
                wait(d)

    def testErrbacksUponDisconnect(self):
        ftpClient = ftp.FTPClient()
        d = ftpClient.list('some path', Dummy())
        m = []
        def _eb(failure):
            m.append(failure)
            return None
        d.addErrback(_eb)
        from twisted.internet.main import CONNECTION_LOST
        ftpClient.connectionLost(failure.Failure(CONNECTION_LOST))
        self.failUnless(m, m)


class DummyTransport:
    def write(self, bytes):
        pass

class BufferingTransport:
    buffer = ''
    def write(self, bytes):
        self.buffer += bytes


class FTPClientBasicTests(unittest.TestCase):

    def testGreeting(self):
        # The first response is captured as a greeting.
        ftpClient = ftp.FTPClientBasic()
        ftpClient.lineReceived('220 Imaginary FTP.')
        self.failUnlessEqual(['220 Imaginary FTP.'], ftpClient.greeting)

    def testResponseWithNoMessage(self):
        # Responses with no message are still valid, i.e. three digits followed
        # by a space is complete response.
        ftpClient = ftp.FTPClientBasic()
        ftpClient.lineReceived('220 ')
        self.failUnlessEqual(['220 '], ftpClient.greeting)

    def testMultilineResponse(self):
        ftpClient = ftp.FTPClientBasic()
        ftpClient.transport = DummyTransport()
        ftpClient.lineReceived('220 Imaginary FTP.')

        # Queue (and send) a dummy command, and set up a callback to capture the
        # result
        deferred = ftpClient.queueStringCommand('BLAH')
        result = []
        deferred.addCallback(result.append)
        deferred.addErrback(self.fail)

        # Send the first line of a multiline response.
        ftpClient.lineReceived('210-First line.')
        self.failUnlessEqual([], result)

        # Send a second line, again prefixed with "nnn-".
        ftpClient.lineReceived('123-Second line.')
        self.failUnlessEqual([], result)

        # Send a plain line of text, no prefix.
        ftpClient.lineReceived('Just some text.')
        self.failUnlessEqual([], result)

        # Now send a short (less than 4 chars) line.
        ftpClient.lineReceived('Hi')
        self.failUnlessEqual([], result)

        # Now send an empty line.
        ftpClient.lineReceived('')
        self.failUnlessEqual([], result)

        # And a line with 3 digits in it, and nothing else.
        ftpClient.lineReceived('321')
        self.failUnlessEqual([], result)

        # Now finish it.
        ftpClient.lineReceived('210 Done.')
        self.failUnlessEqual(
            ['210-First line.',
             '123-Second line.',
             'Just some text.',
             'Hi',
             '',
             '321',
             '210 Done.'], result[0])

    def testNoPasswordGiven(self):
        """Passing None as the password avoids sending the PASS command."""
        # Create a client, and give it a greeting.
        ftpClient = ftp.FTPClientBasic()
        ftpClient.transport = BufferingTransport()
        ftpClient.lineReceived('220 Welcome to Imaginary FTP.')

        # Queue a login with no password
        ftpClient.queueLogin('bob', None)
        self.failUnlessEqual('USER bob\r\n', ftpClient.transport.buffer)

        # Clear the test buffer, acknowledge the USER command.
        ftpClient.transport.buffer = ''
        ftpClient.lineReceived('200 Hello bob.')

        # The client shouldn't have sent anything more (i.e. it shouldn't have
        # sent a PASS command).
        self.failUnlessEqual('', ftpClient.transport.buffer)

    def testNoPasswordNeeded(self):
        """Receiving a 230 response to USER prevents PASS from being sent."""
        # Create a client, and give it a greeting.
        ftpClient = ftp.FTPClientBasic()
        ftpClient.transport = BufferingTransport()
        ftpClient.lineReceived('220 Welcome to Imaginary FTP.')

        # Queue a login with no password
        ftpClient.queueLogin('bob', 'secret')
        self.failUnlessEqual('USER bob\r\n', ftpClient.transport.buffer)

        # Clear the test buffer, acknowledge the USER command with a 230
        # response code.
        ftpClient.transport.buffer = ''
        ftpClient.lineReceived('230 Hello bob.  No password needed.')

        # The client shouldn't have sent anything more (i.e. it shouldn't have
        # sent a PASS command).
        self.failUnlessEqual('', ftpClient.transport.buffer)


class PathHandling(unittest.TestCase):
    def testNormalizer(self):
        for inp, outp in [('a', ['a']),
                          ('/a', ['a']),
                          ('/', []),
                          ('a/b/c', ['a', 'b', 'c']),
                          ('/a/b/c', ['a', 'b', 'c']),
                          ('/a/', ['a']),
                          ('a/', ['a'])]:
            self.assertEquals(ftp.toSegments([], inp), outp)

        for inp, outp in [('b', ['a', 'b']),
                          ('b/', ['a', 'b']),
                          ('/b', ['b']),
                          ('/b/', ['b']),
                          ('b/c', ['a', 'b', 'c']),
                          ('b/c/', ['a', 'b', 'c']),
                          ('/b/c', ['b', 'c']),
                          ('/b/c/', ['b', 'c'])]:
            self.assertEquals(ftp.toSegments(['a'], inp), outp)

        for inp, outp in [('//', []),
                          ('//a', ['a']),
                          ('a//', ['a']),
                          ('a//b', ['a', 'b'])]:
            self.assertEquals(ftp.toSegments([], inp), outp)

        for inp, outp in [('//', []),
                          ('//b', ['b']),
                          ('b//c', ['a', 'b', 'c'])]:
            self.assertEquals(ftp.toSegments(['a'], inp), outp)

        for inp, outp in [('..', []),
                          ('../', []),
                          ('a/..', ['x']),
                          ('/a/..', []),
                          ('/a/b/..', ['a']),
                          ('/a/b/../', ['a']),
                          ('/a/b/../c', ['a', 'c']),
                          ('/a/b/../c/', ['a', 'c']),
                          ('/a/b/../../c', ['c']),
                          ('/a/b/../../c/', ['c']),
                          ('/a/b/../../c/..', []),
                          ('/a/b/../../c/../', [])]:
            self.assertEquals(ftp.toSegments(['x'], inp), outp)

        for inp in ['..', '../', 'a/../..', 'a/../../',
                    '/..', '/../', '/a/../..', '/a/../../',
                    '/a/b/../../..']:
            self.assertRaises(ftp.InvalidPath, ftp.toSegments, [], inp)

        for inp in ['../..', '../../', '../a/../..']:
            self.assertRaises(ftp.InvalidPath, ftp.toSegments, ['x'], inp)
