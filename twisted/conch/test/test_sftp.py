# -*- test-case-name: twisted.conch.test.test_sftp -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE file for details.

from twisted.trial import unittest, util
try:
    from twisted.conch import unix
    from twisted.conch.scripts import cftp
except ImportError:
    unix = None

try:
    import Crypto
except ImportError:
    Crypto = None

from twisted.cred import portal
from twisted.conch import avatar
from twisted.conch.ssh import filetransfer, session
from twisted.protocols import loopback
from twisted.internet import defer, reactor, protocol, interfaces
from twisted.internet.utils import getProcessOutputAndValue
from twisted.python import components, log, failure
from twisted.test import test_process

import test_conch
import sys, os, os.path, time, tempfile

class FileTransferTestAvatar(avatar.ConchUser): 

    def __init__(self):
        avatar.ConchUser.__init__(self)
        self.channelLookup['session'] = session.SSHSession
        self.subsystemLookup['sftp'] = filetransfer.FileTransferServer
            
    def _runAsUser(self, f, *args, **kw):
        try:
            f = iter(f)
        except TypeError:
            f = [(f, args, kw)]
        for i in f:
            func = i[0]
            args = len(i)>1 and i[1] or ()
            kw = len(i)>2 and i[2] or {}
            r = func(*args, **kw)
        return r

    def getHomeDir(self):
        return os.path.join(os.getcwd(), 'sftp_test')

class SFTPTestProcess(protocol.ProcessProtocol):

    def __init__(self):
        self.clearBuffer()
        self.connected = 0

    def connectionMade(self):
        self.connected = 1
        
    def clearBuffer(self):
        self.buffer = ''

    def outReceived(self, data):
        log.msg('got %s' % data)
        self.buffer += data

    def errReceived(self, data):
        log.msg('err: %s' % data)

    def connectionLost(self, reason):
        self.connected = 0
    def getBuffer(self):
        return self.buffer

class ConchSessionForTestAvatar:

    def __init__(self, avatar):
        self.avatar = avatar
if unix:
    class FileTransferForTestAvatar(unix.SFTPServerForUnixConchUser):

        def gotVersion(self, version, otherExt):
            return {'conchTest' : 'ext data'}

        def extendedRequest(self, extName, extData):
            if extName == 'testExtendedRequest':
                return 'bar'
            raise NotImplementedError

    components.registerAdapter(FileTransferForTestAvatar, FileTransferTestAvatar, filetransfer.ISFTPServer)

class FileTransferTestRealm:

    def requestAvatar(sefl, avatarID, mind, *interfaces):
        a = FileTransferTestAvatar()
        return interfaces[0], a, lambda: None

class SFTPTestBase(unittest.TestCase):

    def setUp(self):
        os.mkdir('sftp_test')
        os.mkdir('sftp_test/testDirectory')

        f=file('sftp_test/testfile1','w')
        f.write('a'*10+'b'*10)
        f.write(file('/dev/urandom').read(1024*64)) # random data
        os.chmod('sftp_test/testfile1', 0644)
        file('sftp_test/testRemoveFile', 'w').write('a')
        file('sftp_test/testRenameFile', 'w').write('a')
        file('sftp_test/.testHiddenFile', 'w').write('a')


    def tearDown(self):
        for f in ['testfile1', 'testRemoveFile', 'testRenameFile', 
                  'testRenamedFile', 'testLink', 'testfile2', 
                  '.testHiddenFile']:
            try:
                os.remove('sftp_test/' + f)
            except OSError:
                pass
        for d in ['sftp_test/testDirectory', 'sftp_test/testMakeDirectory', 
                'sftp_test']:
            try:
                os.rmdir(d)
            except:
                pass
       
class TestOurServerOurClient(SFTPTestBase):

    def setUp(self):
        self.avatar = FileTransferTestAvatar()
        self.server = filetransfer.FileTransferServer(avatar=self.avatar)
        clientTransport = loopback.LoopbackRelay(self.server)

        self.client = filetransfer.FileTransferClient()
        self._serverVersion = None
        self._extData = None
        def _(serverVersion, extData):
            self._serverVersion = serverVersion
            self._extData = extData
        self.client.gotServerVersion = _
        serverTransport = loopback.LoopbackRelay(self.client) 
        self.client.makeConnection(clientTransport)
        self.server.makeConnection(serverTransport)

        self.clientTransport = clientTransport
        self.serverTransport = serverTransport

        self._emptyBuffers()

        SFTPTestBase.setUp(self)

    def _emptyBuffers(self):
        while self.serverTransport.buffer or self.clientTransport.buffer:
            self.serverTransport.clearBuffer()
            self.clientTransport.clearBuffer()

    def _waitWithBuffer(self, d, timeout=10):
        reactor.callLater(0.1, self._emptyBuffers)
        return util.wait(d, timeout)

    def testServerVersion(self):
        self.failUnlessEqual(self._serverVersion, 3)
        self.failUnlessEqual(self._extData, {'conchTest' : 'ext data'})

    def testOpenFile(self):
        d = self.client.openFile("testfile1", filetransfer.FXF_READ | \
                filetransfer.FXF_WRITE, {})
        openFile = self._waitWithBuffer(d)
        self.failUnlessEqual(filetransfer.ISFTPFile(openFile), openFile)
        bytes = self._waitWithBuffer(openFile.readChunk(0, 20))
        self.failUnlessEqual(bytes, 'a'*10 + 'b'*10)
        self._waitWithBuffer(openFile.writeChunk(20, 'c'*10))
        bytes = self._waitWithBuffer(openFile.readChunk(0, 30))
        self.failUnlessEqual(bytes, 'a'*10 + 'b'*10 + 'c'*10)
        attrs = self._waitWithBuffer(openFile.getAttrs())
        self._waitWithBuffer(openFile.close())
        d = openFile.getAttrs()
        self.failUnlessRaises(filetransfer.SFTPError, self._waitWithBuffer, d)
        log.flushErrors()
        attrs2 = self._waitWithBuffer(self.client.getAttrs('testfile1'))
        self.failUnlessEqual(attrs, attrs2)
        # XXX test setAttrs

    def testRemoveFile(self):
        d = self.client.getAttrs("testRemoveFile")
        result = self._waitWithBuffer(d)
        d = self.client.removeFile("testRemoveFile")
        result = self._waitWithBuffer(d)
        d = self.client.removeFile("testRemoveFile")
        self.failUnlessRaises(filetransfer.SFTPError, self._waitWithBuffer, d)

    def testRenameFile(self):
        d = self.client.getAttrs("testRenameFile")
        attrs = self._waitWithBuffer(d)
        d = self.client.renameFile("testRenameFile", "testRenamedFile")
        result = self._waitWithBuffer(d)
        d = self.client.getAttrs("testRenamedFile")
        self.failUnlessEqual(self._waitWithBuffer(d), attrs)

    def testDirectory(self):
        d = self.client.getAttrs("testMakeDirectory")
        self.failUnlessRaises(filetransfer.SFTPError, self._waitWithBuffer, d)
        d = self.client.makeDirectory("testMakeDirectory", {})
        result = self._waitWithBuffer(d)
        d = self.client.getAttrs("testMakeDirectory")
        attrs = self._waitWithBuffer(d)
        # XXX not until version 4/5
        # self.failUnlessEqual(filetransfer.FILEXFER_TYPE_DIRECTORY&attrs['type'], 
        #                     filetransfer.FILEXFER_TYPE_DIRECTORY)

        d = self.client.removeDirectory("testMakeDirectory")
        result = self._waitWithBuffer(d)
        d = self.client.getAttrs("testMakeDirectory")
        self.failUnlessRaises(filetransfer.SFTPError, self._waitWithBuffer, d)

    def testOpenDirectory(self):
        d = self.client.openDirectory('')
        openDir = self._waitWithBuffer(d)
        files = []
        for f in openDir:
            if isinstance(f, defer.Deferred):
                try:
                    f = self._waitWithBuffer(f)
                except EOFError:
                    break
            files.append(f[0])
        files.sort()
        self.failUnlessEqual(files, ['.testHiddenFile', 'testDirectory', 
                'testRemoveFile', 'testRenameFile', 'testfile1']) 
        d = openDir.close()
        result = self._waitWithBuffer(d)

    def testLink(self):
        d = self.client.getAttrs('testLink')
        self.failUnlessRaises(filetransfer.SFTPError, self._waitWithBuffer, d)
        self._waitWithBuffer(self.client.makeLink('testLink', 'testfile1'))
        attrs = self._waitWithBuffer(self.client.getAttrs('testLink',1))
        attrs2 = self._waitWithBuffer(self.client.getAttrs('testfile1'))
        self.failUnlessEqual(attrs, attrs2)
        link = self._waitWithBuffer(self.client.readLink('testLink'))
        self.failUnlessEqual(link, os.path.join(os.getcwd(), 'sftp_test', 'testfile1'))
        realPath = self._waitWithBuffer(self.client.realPath('testLink'))
        self.failUnlessEqual(realPath, os.path.join(os.getcwd(), 'sftp_test', 'testfile1'))

    def testExtendedRequest(self):
        d = self.client.extendedRequest('testExtendedRequest', 'foo')
        self.failUnlessEqual(self._waitWithBuffer(d), 'bar')
        d = self.client.extendedRequest('testBadRequest', '')
        self.failUnlessRaises(NotImplementedError, self._waitWithBuffer, d)

class TestOurServerCmdLineClient(test_process.SignalMixin, SFTPTestBase):

    def setUpClass(self):
        test_process.SignalMixin.setUpClass(self)

        open('dsa_test.pub','w').write(test_conch.publicDSA_openssh)
        open('dsa_test','w').write(test_conch.privateDSA_openssh)
        os.chmod('dsa_test', 33152)
        open('kh_test','w').write('localhost '+test_conch.publicRSA_openssh)
        
        cmd = ('%s %s -p %i -l testuser ' 
               '--known-hosts kh_test '
               '--user-authentications publickey '
               '--host-key-algorithms ssh-rsa '
               '-K direct '
               '-i dsa_test '
               '-a --nocache '
               '-v '
               'localhost')
        test_conch.theTest = self
        realm = FileTransferTestRealm()
        p = portal.Portal(realm)
        p.registerChecker(test_conch.ConchTestPublicKeyChecker())
        fac = test_conch.SSHTestFactory()
        fac.portal = p
        self.fac = fac
        self.server = reactor.listenTCP(0, fac, interface="127.0.0.1")
        port = self.server.getHost().port
        import twisted
        exe = sys.executable
        twisted_path = os.path.dirname(twisted.__file__)
        cftp_path = os.path.abspath("%s/../bin/conch/cftp" % twisted_path)
        cmds = (cmd % (exe, cftp_path, port))
        log.msg('running %s %s' % (exe, cmds))
        self.processProtocol = SFTPTestProcess()
        reactor.spawnProcess(self.processProtocol, exe, cmds.split(),
                             env=None)
        timeout = time.time() + 10
        while (not self.processProtocol.buffer) and (time.time() < timeout):
            reactor.iterate(0.1)
        if time.time() > timeout:
            self.skip = "couldn't start process"
        else:
            self.processProtocol.clearBuffer()
            fac.proto.expectedLoseConnection = 1

    def tearDownClass(self):
        test_process.SignalMixin.tearDownClass(self)
        self.server.stopListening()
        for f in ['dsa_test.pub', 'dsa_test', 'kh_test']:
            try:
                os.remove(f)
            except:
                pass
        try:
            os.kill(self.processProtocol.transport.pid, 9)
        except:
            pass
        reactor.iterate(0.1)
        reactor.iterate(0.1)
        reactor.iterate(0.1)

    def _getCmdResult(self, cmd):
        self.processProtocol.clearBuffer()
        self.processProtocol.transport.write(cmd+'\n')
        timeout = time.time() + 10
        while (self.processProtocol.buffer.find('cftp> ') == -1) and (time.time() < timeout):
            reactor.iterate(0.1)
        self.failIf(time.time() > timeout, "timeout")
        if self.processProtocol.buffer.startswith('cftp> '):
            self.processProtocol.buffer = self.processProtocol.buffer[6:]
        return self.processProtocol.buffer[:-6].strip()

    def testCdPwd(self):
        homeDir = os.path.join(os.getcwd(), 'sftp_test')
        pwdRes = self._getCmdResult('pwd')
        lpwdRes = self._getCmdResult('lpwd')
        cdRes = self._getCmdResult('cd testDirectory')
        self._getCmdResult('cd ..')
        pwd2Res = self._getCmdResult('pwd')
        self.failUnlessEqual(pwdRes, homeDir)
        self.failUnlessEqual(lpwdRes, os.getcwd())
        self.failUnlessEqual(cdRes, '')
        self.failUnlessEqual(pwd2Res, pwdRes)

    def testChAttrs(self):
       lsRes = self._getCmdResult('ls -l testfile1')
       self.failUnless(lsRes.startswith('-rw-r--r--'), lsRes)
       self.failIf(self._getCmdResult('chmod 0 testfile1'))
       lsRes = self._getCmdResult('ls -l testfile1')
       self.failUnless(lsRes.startswith('----------'), lsRes)
       self.failIf(self._getCmdResult('chmod 644 testfile1'))
       log.flushErrors()
       # XXX test chgrp/own

    def testList(self):
        lsRes = self._getCmdResult('ls').split('\n')
        self.failUnlessEqual(lsRes, ['testDirectory', 'testRemoveFile', \
                'testRenameFile', 'testfile1'])
        lsRes = self._getCmdResult('ls *File').split('\n')
        self.failUnlessEqual(lsRes, ['.testHiddenFile', 'testRemoveFile', 'testRenameFile'])
        lsRes = self._getCmdResult('ls -l testDirectory')
        self.failIf(lsRes)
        # XXX test lls in a way that doesn't depend on local semantics

    def testHelp(self):
        helpRes = self._getCmdResult('?')
        self.failUnlessEqual(helpRes, cftp.StdioClient(None).cmd_HELP('').strip())

    def testGet(self):
        getRes = self._getCmdResult('get testfile1 sftp_test/testfile2')
        f1 = file('sftp_test/testfile1').read()
        f2 = file('sftp_test/testfile2').read()
        self.failUnlessEqual(f1, f2, "get failed")
        log.msg(repr(getRes))
        self.failUnlessEqual(getRes, "transferred %s/sftp_test/testfile1 to sftp_test/testfile2" % os.getcwd())
        self.failIf(self._getCmdResult('rm testfile2'))
        self.failIf(os.path.exists('sftp_test/testfile2'))

    def testPut(self):
        putRes = self._getCmdResult('put sftp_test/testfile1 testfile2')
        f1 = file('sftp_test/testfile1').read()
        f2 = file('sftp_test/testfile2').read()
        self.failUnlessEqual(f1, f2, "get failed")
        self.failUnlessEqual(putRes, "transferred sftp_test/testfile1 to %s/sftp_test/testfile2" % os.getcwd())
        self.failIf(self._getCmdResult('rm testfile2'))
        self.failIf(os.path.exists('sftp_test/testfile2'))
        
    def testLink(self):
        linkRes = self._getCmdResult('ln testLink testfile1')
        self.failIf(linkRes)
        lslRes = self._getCmdResult('ls -l testLink')
        log.flushErrors()
        self.failUnless(lslRes.startswith('l'), 'link failed')
        self.failIf(self._getCmdResult('rm testLink'))

    def testDirectory(self):
        self.failIf(self._getCmdResult('mkdir testMakeDirectory'))
        lslRes = self._getCmdResult('ls -l testMakeDirector?')
        self.failUnless(lslRes.startswith('d'), lslRes)
        self.failIf(self._getCmdResult('rmdir testMakeDirectory'))
        self.failIf(self._getCmdResult('lmkdir sftp_test/testLocalDirectory'))
        self.failIf(self._getCmdResult('rmdir testLocalDirectory'))
    
    def testRename(self):
        self.failIf(self._getCmdResult('rename testfile1 testfile2'))
        lsRes = self._getCmdResult('ls testfile?').split('\n')
        self.failUnlessEqual(lsRes, ['testfile2'])
        self.failIf(self._getCmdResult('rename testfile2 testfile1'))

    def testCommand(self):
        cmdRes = self._getCmdResult('!echo hello')
        self.failUnlessEqual(cmdRes, 'hello')

class TestOurServerBatchFile(test_process.SignalMixin, SFTPTestBase):

    def setUp(self):
        SFTPTestBase.setUp(self)
        open('dsa_test.pub','w').write(test_conch.publicDSA_openssh)
        open('dsa_test','w').write(test_conch.privateDSA_openssh)
        os.chmod('dsa_test', 33152)
        open('kh_test','w').write('localhost '+test_conch.publicRSA_openssh)

        test_conch.theTest = self
        realm = FileTransferTestRealm()
        p = portal.Portal(realm)
        p.registerChecker(test_conch.ConchTestPublicKeyChecker())
        fac = test_conch.SSHTestFactory()
        fac.portal = p
        self.fac = fac
        self.server = reactor.listenTCP(0, fac, interface="127.0.0.1")
        port = self.server.getHost().port
        import twisted
        twisted_path = os.path.dirname(twisted.__file__)
        cftp_path = os.path.abspath("%s/../bin/conch/cftp" % twisted_path)
        self.cmd = ('%s -p %i -l testuser '
                    '--known-hosts kh_test '
                    '--user-authentications publickey '
                    '--host-key-algorithms ssh-rsa '
                    '-K direct '
                    '-i dsa_test '
                    '-a --nocache '
                    '-v -b %%s localhost') % (cftp_path, port)
        log.msg('running %s %s' % (sys.executable, self.cmd))

    def tearDown(self):
        self.server.stopListening()
        SFTPTestBase.tearDown(self)

    def _getBatchOutput(self, f):
        fn = tempfile.mktemp()
        open(fn, 'w').write(f)
        l = []
        cmds = (self.cmd % fn).split()
        d = getProcessOutputAndValue(sys.executable, cmds, env=None)
        d.setTimeout(10)
        d.addBoth(l.append)
        while not l:
            reactor.iterate(0.1)
            if hasattr(self.fac, 'proto'):
                self.fac.proto.expectedLoseConnection = 1
        os.remove(fn)
        result = l[0]
        if isinstance(result, failure.Failure):
            raise result.value
        else:
            log.msg(result[1])
            return result[0]

    def testBatchFile(self):
        cmds = """ls
exit
"""
        res = self._getBatchOutput(cmds).split('\n')
        self.failUnlessEqual(res[1:-2], ['testDirectory', 'testRemoveFile', 'testRenameFile', 'testfile1'])

    def testError(self):
        cmds = """chown 0 missingFile
pwd
exit
"""
        res = self._getBatchOutput(cmds)
        self.failIf(res.find('sftp_test') != -1)

    def testIgnoredError(self):
        cmds = """-chown 0 missingFile
pwd
exit
"""
        res = self._getBatchOutput(cmds)
        self.failIf(res.find('sftp_test') == -1)

if not unix or not Crypto:
    TestOurServerOurClient.skip = "don't run on non-posix"
    TestOurServerCmdLineClient.skip = "don't run on non-posix"
    TestOurServerBatchFile.skip = "don't run on non-posix"

if not interfaces.IReactorProcess(reactor, None):
    TestOurServerCmdLineClient.skip = "don't run w/o spawnprocess or PyCrypto"
    TestOurServerBatchFile.skip = "don't run w/o/ spawnProcess or PyCrypto"
