# -*- test-case-name: twisted.conch.test.test_cftp -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE file for details.

import sys, os

try:
    import Crypto.Cipher.DES3
except ImportError:
    Crypto = None

try:
    from twisted.conch import unix
    from twisted.conch.scripts import cftp
    from twisted.conch.client import connect, default, options
    from twisted.conch.test.test_filetransfer import FileTransferForTestAvatar
except ImportError:
    unix = None
    try:
        del sys.modules['twisted.conch.unix'] # remove the bad import
    except KeyError:
        # In Python 2.4, the bad import has already been cleaned up for us.
        pass

from twisted.cred import portal
from twisted.internet import reactor, protocol, interfaces, defer, error
from twisted.internet.utils import getProcessOutputAndValue
from twisted.python import log

from twisted.conch.test import test_ssh, test_conch
from twisted.conch.test.test_filetransfer import SFTPTestBase
from twisted.conch.test.test_filetransfer import FileTransferTestAvatar


class FileTransferTestRealm:
    def __init__(self, testDir):
        self.testDir = testDir

    def requestAvatar(self, avatarID, mind, *interfaces):
        a = FileTransferTestAvatar(self.testDir)
        return interfaces[0], a, lambda: None


class SFTPTestProcess(protocol.ProcessProtocol):
    """
    Protocol for testing cftp. Provides an interface between Python (where all
    the tests are) and the cftp client process (which does the work that is
    being tested).
    """

    def __init__(self, onOutReceived):
        """
        @param onOutReceived: A L{Deferred} to be fired as soon as data is
        received from stdout.
        """
        self.clearBuffer()
        self.onOutReceived = onOutReceived
        self.onProcessEnd = None
        self._expectingCommand = None
        self._processEnded = False

    def clearBuffer(self):
        """
        Clear any buffered data received from stdout. Should be private.
        """
        self.buffer = ''
        self._linesReceived = []
        self._lineBuffer = ''

    def outReceived(self, data):
        """
        Called by Twisted when the cftp client prints data to stdout.
        """
        log.msg('got %s' % data)
        lines = (self._lineBuffer + data).split('\n')
        self._lineBuffer = lines.pop(-1)
        self._linesReceived.extend(lines)
        # XXX - not strictly correct.
        # We really want onOutReceived to fire after the first 'cftp>' prompt
        # has been received. (See use in TestOurServerCmdLineClient.setUp)
        if self.onOutReceived is not None:
            d, self.onOutReceived = self.onOutReceived, None
            d.callback(data)
        self.buffer += data
        self._checkForCommand()

    def _checkForCommand(self):
        prompt = 'cftp> '
        if self._expectingCommand and self._lineBuffer == prompt:
            buf = '\n'.join(self._linesReceived)
            if buf.startswith(prompt):
                buf = buf[len(prompt):]
            self.clearBuffer()
            d, self._expectingCommand = self._expectingCommand, None
            d.callback(buf)

    def errReceived(self, data):
        """
        Called by Twisted when the cftp client prints data to stderr.
        """
        log.msg('err: %s' % data)

    def getBuffer(self):
        """
        Return the contents of the buffer of data received from stdout.
        """
        return self.buffer

    def runCommand(self, command):
        """
        Issue the given command via the cftp client. Return a C{Deferred} that
        fires when the server returns a result. Note that the C{Deferred} will
        callback even if the server returns some kind of error.

        @param command: A string containing an sftp command.

        @return: A C{Deferred} that fires when the sftp server returns a
        result. The payload is the server's response string.
        """
        self._expectingCommand = defer.Deferred()
        self.clearBuffer()
        self.transport.write(command + '\n')
        return self._expectingCommand

    def runScript(self, commands):
        """
        Run each command in sequence and return a Deferred that fires when all
        commands are completed.

        @param commands: A list of strings containing sftp commands.

        @return: A C{Deferred} that fires when all commands are completed. The
        payload is a list of response strings from the server, in the same
        order as the commands.
        """
        sem = defer.DeferredSemaphore(1)
        dl = [sem.run(self.runCommand, command) for command in commands]
        return defer.gatherResults(dl)

    def killProcess(self):
        """
        Kill the process if it is still running.

        If the process is still running, sends a KILL signal to the transport
        and returns a C{Deferred} which fires when L{processEnded} is called.

        @return: a C{Deferred}.
        """
        if self._processEnded:
            return defer.succeed(None)
        self.onProcessEnd = defer.Deferred()
        self.transport.signalProcess('KILL')
        return self.onProcessEnd

    def processEnded(self, reason):
        """
        Called by Twisted when the cftp client process ends.
        """
        self._processEnded = True
        if self.onProcessEnd:
            d, self.onProcessEnd = self.onProcessEnd, None
            d.callback(None)


class CFTPClientTestBase(SFTPTestBase):
    def setUp(self):
        f = open('dsa_test.pub','w')
        f.write(test_ssh.publicDSA_openssh)
        f.close()
        f = open('dsa_test','w')
        f.write(test_ssh.privateDSA_openssh)
        f.close()
        os.chmod('dsa_test', 33152)
        f = open('kh_test','w')
        f.write('127.0.0.1 ' + test_ssh.publicRSA_openssh)
        f.close()
        return SFTPTestBase.setUp(self)

    def startServer(self):
        realm = FileTransferTestRealm(self.testDir)
        p = portal.Portal(realm)
        p.registerChecker(test_ssh.ConchTestPublicKeyChecker())
        fac = test_ssh.ConchTestServerFactory()
        fac.portal = p
        self.server = reactor.listenTCP(0, fac, interface="127.0.0.1")

    def stopServer(self):
        if not hasattr(self.server.factory, 'proto'):
            return self._cbStopServer(None)
        self.server.factory.proto.expectedLoseConnection = 1
        d = defer.maybeDeferred(
            self.server.factory.proto.transport.loseConnection)
        d.addCallback(self._cbStopServer)
        return d

    def _cbStopServer(self, ignored):
        return defer.maybeDeferred(self.server.stopListening)

    def tearDown(self):
        for f in ['dsa_test.pub', 'dsa_test', 'kh_test']:
            try:
                os.remove(f)
            except:
                pass
        return SFTPTestBase.tearDown(self)



class TestOurServerCmdLineClient(CFTPClientTestBase):

    def setUp(self):
        CFTPClientTestBase.setUp(self)

        self.startServer()
        cmds = ('-p %i -l testuser '
               '--known-hosts kh_test '
               '--user-authentications publickey '
               '--host-key-algorithms ssh-rsa '
               '-K direct '
               '-i dsa_test '
               '-a --nocache '
               '-v '
               '127.0.0.1')
        port = self.server.getHost().port
        cmds = test_conch._makeArgs((cmds % port).split(), mod='cftp')
        log.msg('running %s %s' % (sys.executable, cmds))
        d = defer.Deferred()
        self.processProtocol = SFTPTestProcess(d)
        d.addCallback(lambda _: self.processProtocol.clearBuffer())
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        reactor.spawnProcess(self.processProtocol, sys.executable, cmds,
                             env=env)
        return d

    def tearDown(self):
        d = self.stopServer()
        d.addCallback(lambda _: self.processProtocol.killProcess())
        return d

    def _killProcess(self, ignored):
        try:
            self.processProtocol.transport.signalProcess('KILL')
        except error.ProcessExitedAlready:
            pass

    def runCommand(self, command):
        """
        Run the given command with the cftp client. Return a C{Deferred} that
        fires when the command is complete. Payload is the server's output for
        that command.
        """
        return self.processProtocol.runCommand(command)

    def runScript(self, *commands):
        """
        Run the given commands with the cftp client. Returns a C{Deferred}
        that fires when the commands are all complete. The C{Deferred}'s
        payload is a list of output for each command.
        """
        return self.processProtocol.runScript(commands)

    def testCdPwd(self):
        """
        Test that 'pwd' reports the current remote directory, that 'lpwd'
        reports the current local directory, and that changing to a
        subdirectory then changing to its parent leaves you in the original
        remote directory.
        """
        # XXX - not actually a unit test, see docstring.
        homeDir = os.path.join(os.getcwd(), self.testDir)
        d = self.runScript('pwd', 'lpwd', 'cd testDirectory', 'cd ..', 'pwd')
        d.addCallback(lambda xs: xs[:3] + xs[4:])
        d.addCallback(self.assertEqual,
                      [homeDir, os.getcwd(), '', homeDir])
        return d

    def testChAttrs(self):
        """
        Check that 'ls -l' output includes the access permissions and that
        this output changes appropriately with 'chmod'.
        """
        def _check(results):
            self.flushLoggedErrors()
            self.assertTrue(results[0].startswith('-rw-r--r--'))
            self.assertEqual(results[1], '')
            self.assertTrue(results[2].startswith('----------'), results[2])
            self.assertEqual(results[3], '')

        d = self.runScript('ls -l testfile1', 'chmod 0 testfile1',
                           'ls -l testfile1', 'chmod 644 testfile1')
        return d.addCallback(_check)
        # XXX test chgrp/own


    def testList(self):
        """
        Check 'ls' works as expected. Checks for wildcards, hidden files,
        listing directories and listing empty directories.
        """
        def _check(results):
            self.assertEqual(results[0], ['testDirectory', 'testRemoveFile',
                                          'testRenameFile', 'testfile1'])
            self.assertEqual(results[1], ['testDirectory', 'testRemoveFile',
                                          'testRenameFile', 'testfile1'])
            self.assertEqual(results[2], ['testRemoveFile', 'testRenameFile'])
            self.assertEqual(results[3], ['.testHiddenFile', 'testRemoveFile',
                                          'testRenameFile'])
            self.assertEqual(results[4], [''])
        d = self.runScript('ls', 'ls ../' + os.path.basename(self.testDir),
                           'ls *File', 'ls -a *File', 'ls -l testDirectory')
        d.addCallback(lambda xs: [x.split('\n') for x in xs])
        return d.addCallback(_check)

    def testHelp(self):
        """
        Check that running the '?' command returns help.
        """
        d = self.runCommand('?')
        d.addCallback(self.assertEqual,
                      cftp.StdioClient(None).cmd_HELP('').strip())
        return d

    def assertFilesEqual(self, name1, name2, msg=None):
        """
        Assert that the files at C{name1} and C{name2} contain exactly the
        same data.
        """
        f1 = file(name1).read()
        f2 = file(name2).read()
        self.failUnlessEqual(f1, f2, msg)


    def testGet(self):
        """
        Test that 'get' saves the remote file to the correct local location,
        that the output of 'get' is correct and that 'rm' actually removes
        the file.
        """
        # XXX - not actually a unit test
        expectedOutput = ("Transferred %s/%s/testfile1 to %s/test file2"
                          % (os.getcwd(), self.testDir, self.testDir))
        def _checkGet(result):
            self.assertTrue(result.endswith(expectedOutput))
            self.assertFilesEqual(self.testDir + '/testfile1',
                                  self.testDir + '/test file2',
                                  "get failed")
            return self.runCommand('rm "test file2"')

        d = self.runCommand('get testfile1 "%s/test file2"' % (self.testDir,))
        d.addCallback(_checkGet)
        d.addCallback(lambda _: self.failIf(
            os.path.exists(self.testDir + '/test file2')))
        return d


    def testWildcardGet(self):
        """
        Test that 'get' works correctly when given wildcard parameters.
        """
        def _check(ignored):
            self.assertFilesEqual(self.testDir + '/testRemoveFile',
                                  'testRemoveFile',
                                  'testRemoveFile get failed')
            self.assertFilesEqual(self.testDir + '/testRenameFile',
                                  'testRenameFile',
                                  'testRenameFile get failed')

        d = self.runCommand('get testR*')
        return d.addCallback(_check)


    def testPut(self):
        """
        Check that 'put' uploads files correctly and that they can be
        successfully removed. Also check the output of the put command.
        """
        # XXX - not actually a unit test
        expectedOutput = ('Transferred %s/testfile1 to %s/%s/test"file2'
                          % (self.testDir, os.getcwd(), self.testDir))
        def _checkPut(result):
            self.assertFilesEqual(self.testDir + '/testfile1',
                                  self.testDir + '/test"file2')
            self.failUnless(result.endswith(expectedOutput))
            return self.runCommand('rm "test\\"file2"')

        d = self.runCommand('put %s/testfile1 "test\\"file2"'
                            % (self.testDir,))
        d.addCallback(_checkPut)
        d.addCallback(lambda _: self.failIf(
            os.path.exists(self.testDir + '/test"file2')))
        return d


    def testWildcardPut(self):
        """
        What happens if you issue a 'put' command and include a wildcard (i.e.
        '*') in parameter? Check that all files matching the wildcard are
        uploaded to the correct directory.
        """
        def check(results):
            self.assertEqual(results[0], '')
            self.assertEqual(results[2], '')
            self.assertFilesEqual(self.testDir + '/testRemoveFile',
                                  self.testDir + '/../testRemoveFile',
                                  'testRemoveFile get failed')
            self.assertFilesEqual(self.testDir + '/testRenameFile',
                                  self.testDir + '/../testRenameFile',
                                  'testRenameFile get failed')

        d = self.runScript('cd ..',
                           'put %s/testR*' % (self.testDir,),
                           'cd %s' % os.path.basename(self.testDir))
        d.addCallback(check)
        return d


    def testLink(self):
        """
        Test that 'ln' creates a file which appears as a link in the output of
        'ls'. Check that removing the new file succeeds without output.
        """
        def _check(results):
            self.flushLoggedErrors()
            self.assertEqual(results[0], '')
            self.assertTrue(results[1].startswith('l'), 'link failed')
            return self.runCommand('rm testLink')

        d = self.runScript('ln testLink testfile1', 'ls -l testLink')
        d.addCallback(_check)
        d.addCallback(self.assertEqual, '')
        return d


    def testRemoteDirectory(self):
        """
        Test that we can create and remove directories with the cftp client.
        """
        def _check(results):
            self.assertEqual(results[0], '')
            self.assertTrue(results[1].startswith('d'))
            return self.runCommand('rmdir testMakeDirectory')

        d = self.runScript('mkdir testMakeDirectory',
                           'ls -l testMakeDirector?')
        d.addCallback(_check)
        d.addCallback(self.assertEqual, '')
        return d


    def test_existingRemoteDirectory(self):
        """
        Test that a C{mkdir} on an existing directory fails with the
        appropriate error, and doesn't log an useless error server side.
        """
        def _check(results):
            self.assertEquals(results[0], '')
            self.assertEquals(results[1],
                              'remote error 11: mkdir failed')

        d = self.runScript('mkdir testMakeDirectory',
                           'mkdir testMakeDirectory')
        d.addCallback(_check)
        return d


    def testLocalDirectory(self):
        """
        Test that we can create a directory locally and remove it with the
        cftp client. This test works because the 'remote' server is running
        out of a local directory.
        """
        d = self.runCommand('lmkdir %s/testLocalDirectory' % (self.testDir,))
        d.addCallback(self.assertEqual, '')
        d.addCallback(lambda _: self.runCommand('rmdir testLocalDirectory'))
        d.addCallback(self.assertEqual, '')
        return d


    def testRename(self):
        """
        Test that we can rename a file.
        """
        def _check(results):
            self.assertEqual(results[0], '')
            self.assertEqual(results[1], 'testfile2')
            return self.runCommand('rename testfile2 testfile1')

        d = self.runScript('rename testfile1 testfile2', 'ls testfile?')
        d.addCallback(_check)
        d.addCallback(self.assertEqual, '')
        return d


    def testCommand(self):
        d = self.runCommand('!echo hello')
        return d.addCallback(self.assertEqual, 'hello')


class TestOurServerBatchFile(CFTPClientTestBase):
    def setUp(self):
        CFTPClientTestBase.setUp(self)
        self.startServer()

    def tearDown(self):
        CFTPClientTestBase.tearDown(self)
        return self.stopServer()

    def _getBatchOutput(self, f):
        fn = self.mktemp()
        open(fn, 'w').write(f)
        l = []
        port = self.server.getHost().port
        cmds = ('-p %i -l testuser '
                    '--known-hosts kh_test '
                    '--user-authentications publickey '
                    '--host-key-algorithms ssh-rsa '
                    '-K direct '
                    '-i dsa_test '
                    '-a --nocache '
                    '-v -b %s 127.0.0.1') % (port, fn)
        cmds = test_conch._makeArgs(cmds.split(), mod='cftp')[1:]
        log.msg('running %s %s' % (sys.executable, cmds))
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)

        self.server.factory.expectedLoseConnection = 1

        d = getProcessOutputAndValue(sys.executable, cmds, env=env)

        def _cleanup(res):
            os.remove(fn)
            return res

        d.addCallback(lambda res: res[0])
        d.addBoth(_cleanup)

        return d

    def testBatchFile(self):
        """Test whether batch file function of cftp ('cftp -b batchfile').
        This works by treating the file as a list of commands to be run.
        """
        cmds = """pwd
ls
exit
"""
        def _cbCheckResult(res):
            res = res.split('\n')
            log.msg('RES %s' % str(res))
            self.failUnless(res[1].find(self.testDir) != -1, repr(res))
            self.failUnlessEqual(res[3:-2], ['testDirectory', 'testRemoveFile',
                                             'testRenameFile', 'testfile1'])

        d = self._getBatchOutput(cmds)
        d.addCallback(_cbCheckResult)
        return d

    def testError(self):
        """Test that an error in the batch file stops running the batch.
        """
        cmds = """chown 0 missingFile
pwd
exit
"""
        def _cbCheckResult(res):
            self.failIf(res.find(self.testDir) != -1)

        d = self._getBatchOutput(cmds)
        d.addCallback(_cbCheckResult)
        return d

    def testIgnoredError(self):
        """Test that a minus sign '-' at the front of a line ignores
        any errors.
        """
        cmds = """-chown 0 missingFile
pwd
exit
"""
        def _cbCheckResult(res):
            self.failIf(res.find(self.testDir) == -1)

        d = self._getBatchOutput(cmds)
        d.addCallback(_cbCheckResult)
        return d


class TestOurServerUnixClient(test_conch._UnixFixHome, CFTPClientTestBase):

    def setUp(self):
        test_conch._UnixFixHome.setUp(self)
        CFTPClientTestBase.setUp(self)
        self.startServer()
        cmd1 = ('-p %i -l testuser '
                '--known-hosts kh_test '
                '--host-key-algorithms ssh-rsa '
                '-a '
                '-K direct '
                '-i dsa_test '
                '127.0.0.1'
                )
        port = self.server.getHost().port
        cmds1 = (cmd1 % port).split()
        o = options.ConchOptions()
        def _(host, *args):
            o['host'] = host
        o.parseArgs = _
        o.parseOptions(cmds1)
        vhk = default.verifyHostKey
        self.conn = conn = test_conch.SSHTestConnectionForUnix(None)
        uao = default.SSHUserAuthClient(o['user'], o, conn)
        return connect.connect(o['host'], int(o['port']), o, vhk, uao)

    def tearDown(self):
        CFTPClientTestBase.tearDown(self)
        d = defer.maybeDeferred(self.conn.transport.loseConnection)
        d.addCallback(lambda x : self.stopServer())
        def clean(ign):
            test_conch._UnixFixHome.tearDown(self)
            return ign
        return defer.gatherResults([d, self.conn.stopDeferred]).addBoth(clean)

    def _getBatchOutput(self, f):
        fn = self.mktemp()
        open(fn, 'w').write(f)
        port = self.server.getHost().port
        cmds = ('-p %i -l testuser '
                    '-K unix '
                    '-a '
                    '-v -b %s 127.0.0.1') % (port, fn)
        cmds = test_conch._makeArgs(cmds.split(), mod='cftp')[1:]
        log.msg('running %s %s' % (sys.executable, cmds))
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)

        self.server.factory.expectedLoseConnection = 1

        d = getProcessOutputAndValue(sys.executable, cmds, env=env)

        def _cleanup(res):
            os.remove(fn)
            return res

        d.addCallback(lambda res: res[0])
        d.addBoth(_cleanup)

        return d

    def testBatchFile(self):
        """Test that the client works even over a UNIX connection.
        """
        cmds = """pwd
exit
"""
        d = self._getBatchOutput(cmds)
        d.addCallback(
            lambda res : self.failIf(res.find(self.testDir) == -1,
                                     "%s not in %r" % (self.testDir, res)))
        return d



class TestOurServerSftpClient(CFTPClientTestBase):
    """
    Test the sftp server against sftp command line client.
    """

    def setUp(self):
        CFTPClientTestBase.setUp(self)
        return self.startServer()


    def tearDown(self):
        return self.stopServer()


    def test_extendedAttributes(self):
        """
        Test the return of extended attributes by the server: the sftp client
        should ignore them, but still be able to parse the response correctly.

        This test is mainly here to check that
        L{filetransfer.FILEXFER_ATTR_EXTENDED} has the correct value.
        """
        fn = self.mktemp()
        open(fn, 'w').write("ls .\nexit")
        port = self.server.getHost().port

        oldGetAttr = FileTransferForTestAvatar._getAttrs
        def _getAttrs(self, s):
            attrs = oldGetAttr(self, s)
            attrs["ext_foo"] = "bar"
            return attrs

        self.patch(FileTransferForTestAvatar, "_getAttrs", _getAttrs)

        self.server.factory.expectedLoseConnection = True
        cmds = ('-o', 'IdentityFile=dsa_test',
                '-o', 'UserKnownHostsFile=kh_test',
                '-o', 'HostKeyAlgorithms=ssh-rsa',
                '-o', 'Port=%i' % (port,), '-b', fn, 'testuser@127.0.0.1')
        d = getProcessOutputAndValue("sftp", cmds)
        def check(result):
            self.assertEquals(result[2], 0)
            for i in ['testDirectory', 'testRemoveFile',
                      'testRenameFile', 'testfile1']:
                self.assertIn(i, result[0])
        return d.addCallback(check)



if not unix or not Crypto or not interfaces.IReactorProcess(reactor, None):
    TestOurServerCmdLineClient.skip = "don't run w/o spawnprocess or PyCrypto"
    TestOurServerBatchFile.skip = "don't run w/o spawnProcess or PyCrypto"
    TestOurServerUnixClient.skip = "don't run w/o spawnProcess or PyCrypto"
    TestOurServerSftpClient.skip = "don't run w/o spawnProcess or PyCrypto"
else:
    from twisted.python.procutils import which
    if not which('sftp'):
        TestOurServerSftpClient.skip = "no sftp command-line client available"
