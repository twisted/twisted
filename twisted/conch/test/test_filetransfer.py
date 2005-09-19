# -*- test-case-name: twisted.conch.test.test_filetransfer -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE file for details.

from twisted.trial import unittest, util
try:
    from twisted.conch import unix
except ImportError:
    unix = None
    import sys
    del sys.modules['twisted.conch.unix'] # remove the bad import

from twisted.conch import avatar
from twisted.conch.ssh import filetransfer, session
from twisted.internet import defer, reactor, protocol, interfaces
from twisted.protocols import loopback
from twisted.python import components, log, failure

import os

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

class ConchSessionForTestAvatar:

    def __init__(self, avatar):
        self.avatar = avatar

if unix:
    if not hasattr(unix, 'SFTPServerForUnixConchUser'):
        # unix should either be a fully working module, or None.  I'm not sure
        # how this happens, but on win32 it does.  Try to cope.  --spiv.
        import warnings
        warnings.warn(("twisted.conch.unix imported %r, "
                       "but doesn't define SFTPServerForUnixConchUser'")
                      % (unix,))
        unix = None
    else:
        class FileTransferForTestAvatar(unix.SFTPServerForUnixConchUser):

            def gotVersion(self, version, otherExt):
                return {'conchTest' : 'ext data'}

            def extendedRequest(self, extName, extData):
                if extName == 'testExtendedRequest':
                    return 'bar'
                raise NotImplementedError

        components.registerAdapter(FileTransferForTestAvatar,
                                   FileTransferTestAvatar,
                                   filetransfer.ISFTPServer)

class SFTPTestBase(unittest.TestCase):

    def setUp(self):
        try:
            os.mkdir('sftp_test')
        except OSError, e:
            if e.args[0] == 17:
                pass
        try:
            os.mkdir('sftp_test/testDirectory')
        except OSError, e:
            if e.args[0] == 17:
                pass

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

    if not unix:
        skip = "can't run on non-posix computers"

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
        # Ok, how about this for a start?  It caught a bug :)  -- spiv.
        attrs['atime'] = 0
        # XXX: Remove 'uid' and 'gid', because python 2.2 doesn't have
        #      os.lchown, so we just skip that bit (dodgy!)
        #        -- spiv, 2005-02-27
        del attrs['uid'], attrs['gid']
        self._waitWithBuffer(self.client.setAttrs('testfile1', attrs))
        attrs3 = self._waitWithBuffer(self.client.getAttrs('testfile1'))
        del attrs3['uid'], attrs3['gid']
        self.failUnlessEqual(attrs, attrs3)

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
