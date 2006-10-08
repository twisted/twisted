# -*- test-case-name: twisted.conch.test.test_filetransfer -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE file for details.

import os
import sys

from twisted.trial import unittest
try:
    from twisted.conch import unix
except ImportError:
    unix = None
    try:
        del sys.modules['twisted.conch.unix'] # remove the bad import
    except KeyError:
        # In Python 2.4, the bad import has already been cleaned up for us.
        # Hooray.
        pass

from twisted.conch import avatar
from twisted.conch.ssh import filetransfer, session
from twisted.internet import defer, reactor
from twisted.protocols import loopback
from twisted.python import components, log


class FileTransferTestAvatar(avatar.ConchUser):

    def __init__(self, homeDir):
        avatar.ConchUser.__init__(self)
        self.channelLookup['session'] = session.SSHSession
        self.subsystemLookup['sftp'] = filetransfer.FileTransferServer
        self.homeDir = homeDir

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
        return os.path.join(os.getcwd(), self.homeDir)

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
        self.testDir = self.mktemp()
        # Give the testDir another level so we can safely "cd .." from it in
        # tests.
        self.testDir = os.path.join(self.testDir, 'extra')
        os.makedirs(os.path.join(self.testDir, 'testDirectory'))

        f = file(os.path.join(self.testDir, 'testfile1'),'w')
        f.write('a'*10+'b'*10)
        f.write(file('/dev/urandom').read(1024*64)) # random data
        os.chmod(os.path.join(self.testDir, 'testfile1'), 0644)
        file(os.path.join(self.testDir, 'testRemoveFile'), 'w').write('a')
        file(os.path.join(self.testDir, 'testRenameFile'), 'w').write('a')
        file(os.path.join(self.testDir, '.testHiddenFile'), 'w').write('a')


class TestOurServerOurClient(SFTPTestBase):

    if not unix:
        skip = "can't run on non-posix computers"

    def setUp(self):
        SFTPTestBase.setUp(self)

        self.avatar = FileTransferTestAvatar(self.testDir)
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

    def _emptyBuffers(self):
        while self.serverTransport.buffer or self.clientTransport.buffer:
            self.serverTransport.clearBuffer()
            self.clientTransport.clearBuffer()

    def _delayedEmptyBuffers(self):
        reactor.callLater(0.1, self._emptyBuffers)

    def testServerVersion(self):
        self.failUnlessEqual(self._serverVersion, 3)
        self.failUnlessEqual(self._extData, {'conchTest' : 'ext data'})

    def testOpenFileIO(self):
        d = self.client.openFile("testfile1", filetransfer.FXF_READ |
                                 filetransfer.FXF_WRITE, {})
        self._emptyBuffers()

        def _fileOpened(openFile):
            self.failUnlessEqual(openFile, filetransfer.ISFTPFile(openFile))
            d = _readChunk(openFile)
            d.addCallback(_writeChunk, openFile)
            return d

        def _readChunk(openFile):
            d = openFile.readChunk(0, 20)
            self._emptyBuffers()
            d.addCallback(self.failUnlessEqual, 'a'*10 + 'b'*10)
            return d

        def _writeChunk(_, openFile):
            d = openFile.writeChunk(20, 'c'*10)
            self._emptyBuffers()
            d.addCallback(_readChunk2, openFile)
            return d

        def _readChunk2(_, openFile):
            d = openFile.readChunk(0, 30)
            self._emptyBuffers()
            d.addCallback(self.failUnlessEqual, 'a'*10 + 'b'*10 + 'c'*10)
            return d

        d.addCallback(_fileOpened)
        return d

    def testClosedFileGetAttrs(self):
        d = self.client.openFile("testfile1", filetransfer.FXF_READ |
                                 filetransfer.FXF_WRITE, {})
        self._emptyBuffers()

        def _getAttrs(_, openFile):
            d = openFile.getAttrs()
            self._emptyBuffers()
            return d

        def _err(f):
            log.flushErrors()
            return f

        def _close(openFile):
            d = openFile.close()
            self._emptyBuffers()
            d.addCallback(_getAttrs, openFile)
            d.addErrback(_err)
            return self.assertFailure(d, filetransfer.SFTPError)

        d.addCallback(_close)
        return d

    def testOpenFileAttributes(self):
        d = self.client.openFile("testfile1", filetransfer.FXF_READ |
                                 filetransfer.FXF_WRITE, {})
        self._emptyBuffers()

        def _getAttrs(openFile):
            d = openFile.getAttrs()
            self._emptyBuffers()
            d.addCallback(_getAttrs2)
            return d

        def _getAttrs2(attrs1):
            d = self.client.getAttrs('testfile1')
            self._emptyBuffers()
            d.addCallback(self.failUnlessEqual, attrs1)
            return d

        return d.addCallback(_getAttrs)


    def testOpenFileSetAttrs(self):
        # XXX test setAttrs
        # Ok, how about this for a start?  It caught a bug :)  -- spiv.
        d = self.client.openFile("testfile1", filetransfer.FXF_READ |
                                 filetransfer.FXF_WRITE, {})
        self._emptyBuffers()

        def _getAttrs(openFile):
            d = openFile.getAttrs()
            self._emptyBuffers()
            d.addCallback(_setAttrs)
            return d

        def _setAttrs(attrs):
            attrs['atime'] = 0
            d = self.client.setAttrs('testfile1', attrs)
            self._emptyBuffers()
            d.addCallback(_getAttrs2)
            d.addCallback(self.failUnlessEqual, attrs)
            return d

        def _getAttrs2(_):
            d = self.client.getAttrs('testfile1')
            self._emptyBuffers()
            return d

        d.addCallback(_getAttrs)
        return d

    def testRemoveFile(self):
        d = self.client.getAttrs("testRemoveFile")
        self._emptyBuffers()
        def _removeFile(ignored):
            d = self.client.removeFile("testRemoveFile")
            self._emptyBuffers()
            return d
        d.addCallback(_removeFile)
        d.addCallback(_removeFile)
        return self.assertFailure(d, filetransfer.SFTPError)

    def testRenameFile(self):
        d = self.client.getAttrs("testRenameFile")
        self._emptyBuffers()
        def _rename(attrs):
            d = self.client.renameFile("testRenameFile", "testRenamedFile")
            self._emptyBuffers()
            d.addCallback(_testRenamed, attrs)
            return d
        def _testRenamed(_, attrs):
            d = self.client.getAttrs("testRenamedFile")
            self._emptyBuffers()
            d.addCallback(self.failUnlessEqual, attrs)
        return d.addCallback(_rename)

    def testDirectoryBad(self):
        d = self.client.getAttrs("testMakeDirectory")
        self._emptyBuffers()
        return self.assertFailure(d, filetransfer.SFTPError)

    def testDirectoryCreation(self):
        d = self.client.makeDirectory("testMakeDirectory", {})
        self._emptyBuffers()

        def _getAttrs(_):
            d = self.client.getAttrs("testMakeDirectory")
            self._emptyBuffers()
            return d

        # XXX not until version 4/5
        # self.failUnlessEqual(filetransfer.FILEXFER_TYPE_DIRECTORY&attrs['type'],
        #                     filetransfer.FILEXFER_TYPE_DIRECTORY)

        def _removeDirectory(_):
            d = self.client.removeDirectory("testMakeDirectory")
            self._emptyBuffers()
            return d

        d.addCallback(_getAttrs)
        d.addCallback(_removeDirectory)
        d.addCallback(_getAttrs)
        return self.assertFailure(d, filetransfer.SFTPError)

    def testOpenDirectory(self):
        d = self.client.openDirectory('')
        self._emptyBuffers()
        files = []

        def _getFiles(openDir):
            def append(f):
                files.append(f)
                return openDir
            d = defer.maybeDeferred(openDir.next)
            self._emptyBuffers()
            d.addCallback(append)
            d.addCallback(_getFiles)
            d.addErrback(_close, openDir)
            return d

        def _checkFiles(ignored):
            fs = list(zip(*files)[0])
            fs.sort()
            self.failUnlessEqual(fs,
                                 ['.testHiddenFile', 'testDirectory',
                                  'testRemoveFile', 'testRenameFile',
                                  'testfile1'])

        def _close(_, openDir):
            d = openDir.close()
            self._emptyBuffers()
            return d

        d.addCallback(_getFiles)
        d.addCallback(_checkFiles)
        return d

    def testLinkDoesntExist(self):
        d = self.client.getAttrs('testLink')
        self._emptyBuffers()
        return self.assertFailure(d, filetransfer.SFTPError)

    def testLinkSharesAttrs(self):
        d = self.client.makeLink('testLink', 'testfile1')
        self._emptyBuffers()
        def _getFirstAttrs(_):
            d = self.client.getAttrs('testLink', 1)
            self._emptyBuffers()
            return d
        def _getSecondAttrs(firstAttrs):
            d = self.client.getAttrs('testfile1')
            self._emptyBuffers()
            d.addCallback(self.assertEqual, firstAttrs)
            return d
        d.addCallback(_getFirstAttrs)
        return d.addCallback(_getSecondAttrs)

    def testLinkPath(self):
        d = self.client.makeLink('testLink', 'testfile1')
        self._emptyBuffers()
        def _readLink(_):
            d = self.client.readLink('testLink')
            self._emptyBuffers()
            d.addCallback(self.failUnlessEqual,
                          os.path.join(os.getcwd(), self.testDir, 'testfile1'))
            return d
        def _realPath(_):
            d = self.client.realPath('testLink')
            self._emptyBuffers()
            d.addCallback(self.failUnlessEqual,
                          os.path.join(os.getcwd(), self.testDir, 'testfile1'))
            return d
        d.addCallback(_readLink)
        d.addCallback(_realPath)
        return d

    def testExtendedRequest(self):
        d = self.client.extendedRequest('testExtendedRequest', 'foo')
        self._emptyBuffers()
        d.addCallback(self.failUnlessEqual, 'bar')
        d.addCallback(self._cbTestExtendedRequest)
        return d

    def _cbTestExtendedRequest(self, ignored):
        d = self.client.extendedRequest('testBadRequest', '')
        self._emptyBuffers()
        return self.assertFailure(d, NotImplementedError)
