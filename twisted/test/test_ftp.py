# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""FTP tests.

Maintainer: U{Andrew Bennetts<mailto:spiv@twistedmatrix.com>}
"""

from __future__ import nested_scopes

import os.path
from StringIO import StringIO
import shutil

from twisted.trial import unittest
from twisted.protocols import basic
from twisted.internet import reactor, protocol, defer, error
from twisted.cred import portal, checkers, credentials
from twisted.python import failure

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
        self.d.callback(self)


class FTPServerTestCase(unittest.TestCase):
    """Simple tests for an FTP server with the default settings."""

    def setUp(self):
        # Create a directory
        self.directory = self.mktemp()
        os.mkdir(self.directory)

        # Start the server
        p = portal.Portal(ftp.FTPRealm(self.directory))
        p.registerChecker(checkers.AllowAnonymousAccess(), 
                          credentials.IAnonymous)
        self.factory = ftp.FTPFactory(portal=p)
        self.port = reactor.listenTCP(0, self.factory, interface="127.0.0.1")

        # Hook the server's buildProtocol to make the protocol instance
        # accessible to tests.
        buildProtocol = self.factory.buildProtocol
        d1 = defer.Deferred()
        def _rememberProtocolInstance(addr):
            protocol = buildProtocol(addr)
            self.serverProtocol = protocol.wrappedProtocol
            d1.callback(None)
            return protocol
        self.factory.buildProtocol = _rememberProtocolInstance

        # Connect a client to it
        portNum = self.port.getHost().port
        clientCreator = protocol.ClientCreator(reactor, ftp.FTPClientBasic)
        d2 = clientCreator.connectTCP("127.0.0.1", portNum)
        def gotClient(client):
            self.client = client
        d2.addCallback(gotClient)
        return defer.gatherResults([d1, d2])

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

    def assertCommandResponse(self, command, expectedResponseLines,
                              chainDeferred=None):
        """Asserts that a sending an FTP command receives the expected
        response.
        
        Returns a Deferred.  Optionally accepts a deferred to chain its actions
        to.
        """
        if chainDeferred is None: 
            chainDeferred = defer.succeed(None)
        
        def queueCommand(ignored):
            d = self.client.queueStringCommand(command)
            def gotResponse(responseLines):
                self.assertEquals(expectedResponseLines, responseLines)
            return d.addCallback(gotResponse)
        return chainDeferred.addCallback(queueCommand)

    def assertCommandFailed(self, command, expectedResponse=None,
                            chainDeferred=None):
        if chainDeferred is None: 
            chainDeferred = defer.succeed(None)

        def queueCommand(ignored):
            return self.client.queueStringCommand(command)
        chainDeferred.addCallback(queueCommand)
        self.assertFailure(chainDeferred, ftp.CommandFailed)
        def failed(exception):
            if expectedResponse is not None:
                self.failUnlessEqual(
                    expectedResponse, exception.args[0])
        return chainDeferred.addCallback(failed)

    def _anonymousLogin(self):
        d = self.assertCommandResponse(
            'USER anonymous',
            ['331 Guest login ok, type your email address as password.'])
        return self.assertCommandResponse(
            'PASS test@twistedmatrix.com',
            ['230 Anonymous login ok, access restrictions apply.'],
            chainDeferred=d)
        

class BasicFTPServerTestCase(FTPServerTestCase):
    def testNotLoggedInReply(self):
        """When not logged in, all commands other than USER and PASS should
        get NOT_LOGGED_IN errors.
        """
        commandList = ['CDUP', 'CWD', 'LIST', 'MODE', 'PASV',
                       'PWD', 'RETR', 'STRU', 'SYST', 'TYPE']

        # Issue commands, check responses
        def checkResponse(exception):
            failureResponseLines = exception.args[0]
            self.failUnless(failureResponseLines[-1].startswith("530"),
                            "Response didn't start with 530: %r"
                            % (failureResponseLines[-1],))
        deferreds = []
        for command in commandList:
            deferred = self.client.queueStringCommand(command)
            self.assertFailure(deferred, ftp.CommandFailed)
            deferred.addCallback(checkResponse)
            deferreds.append(deferred)
        return defer.DeferredList(deferreds, fireOnOneErrback=True)

    def testPASSBeforeUSER(self):
        """Issuing PASS before USER should give an error."""
        return self.assertCommandFailed(
            'PASS foo',
            ["503 Incorrect sequence of commands: "
             "USER required before PASS"])

    def testNoParamsForUSER(self):
        """Issuing USER without a username is a syntax error."""
        return self.assertCommandFailed(
            'USER',
            ['500 Syntax error: USER requires an argument.'])

    def testNoParamsForPASS(self):
        """Issuing PASS without a password is a syntax error."""
        d = self.client.queueStringCommand('USER foo')
        return self.assertCommandFailed(
            'PASS',
            ['500 Syntax error: PASS requires an argument.'],
            chainDeferred=d)

    def testAnonymousLogin(self):
        return self._anonymousLogin()

    def testQuit(self):
        """Issuing QUIT should return a 221 message."""
        d = self._anonymousLogin()
        return self.assertCommandResponse(
            'QUIT',
            ['221 Goodbye.'],
            chainDeferred=d)

    def testAnonymousLoginDenied(self):
        # Reconfigure the server to disallow anonymous access, and to have an
        # IUsernamePassword checker that always rejects.
        self.factory.allowAnonymous = False
        denyAlwaysChecker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        self.factory.portal.registerChecker(denyAlwaysChecker,
                                            credentials.IUsernamePassword)

        # Same response code as allowAnonymous=True, but different text.
        d = self.assertCommandResponse(
            'USER anonymous',
            ['331 Password required for anonymous.'])

        # It will be denied.  No-one can login.
        d = self.assertCommandFailed(
            'PASS test@twistedmatrix.com',
            ['530 Sorry, Authentication failed.'],
            chainDeferred=d)

        # It's not just saying that.  You aren't logged in.
        d = self.assertCommandFailed(
            'PWD',
            ['530 Please login with USER and PASS.'],
            chainDeferred=d)
        return d

    def testUnknownCommand(self):
        d = self._anonymousLogin()
        return self.assertCommandFailed(
            'GIBBERISH', 
            ["502 Command 'GIBBERISH' not implemented"],
            chainDeferred=d)

    def testRETRBeforePORT(self):
        d = self._anonymousLogin()
        return self.assertCommandFailed(
            'RETR foo', 
            ["503 Incorrect sequence of commands: "
             "PORT or PASV required before RETR"],
            chainDeferred=d)

    def testSTORBeforePORT(self):
        d = self._anonymousLogin()
        return self.assertCommandFailed(
            'STOR foo',
            ["503 Incorrect sequence of commands: "
             "PORT or PASV required before STOR"],
            chainDeferred=d)

    def testBadCommandArgs(self):
        d = self._anonymousLogin()
        self.assertCommandFailed(
            'MODE z',
            ["504 Not implemented for parameter 'z'."],
            chainDeferred=d)
        self.assertCommandFailed(
            'STRU I',
            ["504 Not implemented for parameter 'I'."],
            chainDeferred=d)
        return d

    def testDecodeHostPort(self):
        self.assertEquals(ftp.decodeHostPort('25,234,129,22,100,23'),
                ('25.234.129.22', 25623))
        nums = range(6)
        for i in range(6):
            badValue = list(nums)
            badValue[i] = 256
            s = ','.join(map(str, badValue))
            self.assertRaises(ValueError, ftp.decodeHostPort, s)

    def testPASV(self):
        # Login
        yield defer.waitForDeferred(self._anonymousLogin())

        # Issue a PASV command, and extract the host and port from the response
        pasvCmd = defer.waitForDeferred(self.client.queueStringCommand('PASV'))
        yield pasvCmd
        responseLines = pasvCmd.getResult()
        host, port = ftp.decodeHostPort(responseLines[-1][4:])

        # Make sure the server is listening on the port it claims to be
        self.assertEqual(port, self.serverProtocol.dtpPort.getHost().port)

        # Semi-reasonable way to force cleanup
        self.serverProtocol.connectionLost(error.ConnectionDone())
    testPASV = defer.deferredGenerator(testPASV)

    def testSYST(self):
        d = self._anonymousLogin()
        self.assertCommandResponse('SYST', ["215 UNIX Type: L8"],
                                   chainDeferred=d)
        return d

class FTPServerPasvDataConnectionTestCase(FTPServerTestCase):
    def _makeDataConnection(self, ignored=None):
        # Establish a passive data connection (i.e. client connecting to
        # server).
        d = self.client.queueStringCommand('PASV')
        def gotPASV(responseLines):
            host, port = ftp.decodeHostPort(responseLines[-1][4:])
            cc = protocol.ClientCreator(reactor, _BufferingProtocol)
            return cc.connectTCP('127.0.0.1', port)
        return d.addCallback(gotPASV)

    def _download(self, command, chainDeferred=None):
        if chainDeferred is None:
            chainDeferred = defer.succeed(None)

        chainDeferred.addCallback(self._makeDataConnection)
        def queueCommand(downloader):
            # wait for the command to return, and the download connection to be
            # closed.
            d1 = self.client.queueStringCommand(command)
            d2 = downloader.d
            return defer.gatherResults([d1, d2])
        chainDeferred.addCallback(queueCommand)

        def downloadDone((ignored, downloader)):
            return downloader.buffer
        return chainDeferred.addCallback(downloadDone)

    def testEmptyLIST(self):
        # Login
        d = self._anonymousLogin()

        # No files, so the file listing should be empty
        self._download('LIST', chainDeferred=d)
        def checkEmpty(result):
            self.assertEqual('', result)
        return d.addCallback(checkEmpty)

    def testTwoDirLIST(self):
        # Make some directories
        os.mkdir(os.path.join(self.directory, 'foo'))
        os.mkdir(os.path.join(self.directory, 'bar'))

        # Login
        d = self._anonymousLogin()

        # We expect 2 lines because there are two files.
        self._download('LIST', chainDeferred=d)
        def checkDownload(download):
            self.assertEqual(2, len(download[:-2].split('\r\n')))
        d.addCallback(checkDownload)

        # Download a names-only listing.
        self._download('NLST ', chainDeferred=d)
        def checkDownload(download):
            filenames = download[:-2].split('\r\n')
            filenames.sort()
            self.assertEqual(['bar', 'foo'], filenames)
        d.addCallback(checkDownload)

        # Download a listing of the 'foo' subdirectory.  'foo' has no files, so
        # the file listing should be empty.
        self._download('LIST foo', chainDeferred=d)
        def checkDownload(download):
            self.assertEqual('', download)
        d.addCallback(checkDownload)

        # Change the current working directory to 'foo'.
        def chdir(ignored):
            return self.client.queueStringCommand('CWD foo')
        d.addCallback(chdir)

        # Download a listing from within 'foo', and again it should be empty,
        # because LIST uses the working directory by default.
        self._download('LIST', chainDeferred=d)
        def checkDownload(download):
            self.assertEqual('', download)
        return d.addCallback(checkDownload)

    def testManyLargeDownloads(self):
        # Login
        d = self._anonymousLogin()

        # Download a range of different size files
        for size in range(100000, 110000, 500):
            fObj = file(os.path.join(self.directory, '%d.txt' % (size,)), 'wb')
            fObj.write('x' * size)
            fObj.close()

            self._download('RETR %d.txt' % (size,), chainDeferred=d)
            def checkDownload(download, size=size):
                self.assertEqual('x' * size, download)
            d.addCallback(checkDownload)
        return d


class FTPServerPortDataConnectionTestCase(FTPServerPasvDataConnectionTestCase):
    def setUp(self):
        self.dataPorts = []
        return FTPServerPasvDataConnectionTestCase.setUp(self)

    def _makeDataConnection(self, ignored=None):
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
        self.client.queueStringCommand(cmd)
        return deferred

    def tearDown(self):
        l = [defer.maybeDeferred(port.stopListening) for port in self.dataPorts]
        d = defer.maybeDeferred(
            FTPServerPasvDataConnectionTestCase.tearDown, self)
        l.append(d)
        return defer.DeferredList(l, fireOnOneErrback=True) 

    def testPORTCannotConnect(self):
        # Login
        d = self._anonymousLogin()

        # Listen on a port, and immediately stop listening as a way to find a
        # port number that is definitely closed.
        def loggedIn(ignored):
            port = reactor.listenTCP(0, protocol.Factory(),
                                     interface='127.0.0.1')
            portNum = port.getHost().port
            d = port.stopListening()
            d.addCallback(lambda _: portNum)
            return d
        d.addCallback(loggedIn)

        # Tell the server to connect to that port with a PORT command, and
        # verify that it fails with the right error.
        def gotPortNum(portNum):
            return self.assertCommandFailed(
                'PORT ' + ftp.encodeHostPort('127.0.0.1', portNum),
                ["425 Can't open data connection."])
        return d.addCallback(gotPortNum)

        
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
        exampleLine = (
            '-rw-r--r--   1 root     other        531 Jan 29 2003 README\n')
        class PrintLine(protocol.Protocol):
            def connectionMade(self):
                self.transport.write(exampleLine)
                self.transport.loseConnection()
        loopback.loopback(PrintLine(), fileList)
        file = fileList.files[0]
        self.failUnless(file['size'] == 531, 'misparsed fileitem')
        self.failUnless(file['date'] == 'Jan 29 2003', 'misparsed fileitem')
        self.failUnless(file['filename'] == 'README', 'misparsed fileitem')


class FTPClientTests(unittest.TestCase):
    def tearDown(self):
        # Clean up self.port, if any.
        port = getattr(self, 'port', None)
        if port is not None:
            return port.stopListening()
            
    def testFailedRETR(self):
        f = protocol.Factory()
        f.noisy = 0
        self.port = reactor.listenTCP(0, f, interface="127.0.0.1")
        portNum = self.port.getHost().port
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
        d = cc.connectTCP('127.0.0.1', portNum)
        def gotClient(client):
            p = protocol.Protocol()
            return client.retrieveFile('/file/that/doesnt/exist', p)
        d.addCallback(gotClient)
        return self.assertFailure(d, ftp.CommandFailed)

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
