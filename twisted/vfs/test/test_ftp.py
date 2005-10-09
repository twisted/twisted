# -*- test-case-name: twisted.vfs.test.test_ftp -*-
"""Tests for the FTP server VFS adapter."""

# TODO:
#  * more comprehensive testing of error conditions, e.g. deleting files that
#    don't exist.
#  * test more complex paths: such as subdirectories, /foo/../bar/.
#  * generalise Mock*, and add to Twisted as reusable testing helpers.

from zope.interface import implements

from twisted.trial import unittest
from twisted.protocols.ftp import FTP
from twisted.cred import portal
from twisted.python import failure
from twisted.internet import defer

from twisted.vfs.backends import inmem
from twisted.vfs import pathutils
from twisted.vfs.adapters.ftp import FileSystemToIFTPShellAdaptor


class MockTransport:
    def loseConnection(self):
        pass


class MockDTP:
    isConnected = True
    transport = MockTransport()
    def __init__(self):
        self.listResponse = []
        self.lines = []
        self.bytes = ''
    def sendListResponse(self, name, attrs):
        self.listResponse.append((name, attrs))
    def sendLine(self, line):
        self.lines.append(line)
    def write(self, bytes):
        self.bytes += bytes
    def registerConsumer(self, consumer):
        self.consumer = consumer
        self.whenDone = defer.Deferred()
        return self.whenDone
    def finished(self):
        self.whenDone.callback(None)
    def registerProducer(self, producer, streaming):
        producer.resumeProducing()
    def unregisterProducer(self):
        pass


class MockFactory:
    timeOut = 99


class FTPAdapterTestCase(unittest.TestCase):
    def setUp(self):
        # Make some VFS sample data
        self.root = root = inmem.FakeDirectory()
        filesystem = pathutils.FileSystem(root)
        self.ned = ned = inmem.FakeDirectory('ned', root)
        self.f = f = inmem.FakeFile('file.txt', root, 'wobble\n')
        root._children = {'ned': ned, 'file.txt': f}

        # Hook that up to an FTP server protocol instance, and stub out the
        # network bits.
        self.ftp = FTP()
        self.ftp.shell = FileSystemToIFTPShellAdaptor(filesystem)
        self.ftp.workingDirectory = []
        self.ftp.sendLine = lambda bytes: None
        self.ftp.dtpInstance = MockDTP()
        self.ftp.factory = MockFactory

    def tearDown(self):
        self.ftp.setTimeout(None)

    def testPWD(self):
        responseCode, pwd = self.ftp.ftp_PWD()
        self.assertEqual('/', pwd)

    def testLIST(self):
        d = self.ftp.ftp_LIST('')
        names = [name for (name, attrs) in self.ftp.dtpInstance.listResponse]
        names.sort()
        self.assertEqual(['.', '..', 'file.txt', 'ned'], names)

    def testNLST(self):
        d = self.ftp.ftp_NLST('')
        names = self.ftp.dtpInstance.lines
        names.sort()
        self.assertEqual(['.', '..', 'file.txt', 'ned'], names)

    def testCWD(self):
        self.ftp.ftp_CWD('ned')
        responseCode, pwd = self.ftp.ftp_PWD()
        self.assertEqual('/ned', pwd)

    def testRETR(self):
        self.ftp.ftp_RETR('file.txt')
        self.assertEqual('wobble\n', self.ftp.dtpInstance.bytes)

    def testSTOR(self):
        d = self.ftp.ftp_STOR('shazam!.txt')
        self.ftp.dtpInstance.consumer.write('abcdef')
        self.ftp.dtpInstance.finished()
        self.assertEqual('abcdef',
                         self.root.child('shazam!.txt').data.getvalue())

    def testSIZE(self):
        d = self.ftp.ftp_SIZE('file.txt')
        responseCode, size = d.result
        self.assertEqual('7', size)

    def testMDTM(self):
        d = self.ftp.ftp_MDTM('file.txt')
        responseCode, mdtm = d.result

    def testMKD(self):
        d = self.ftp.ftp_MKD('newdir')
        self.assert_(isinstance(self.root.child('newdir'), inmem.FakeDirectory))

        # Creating an already existing directory should fail.
        d = self.ftp.ftp_MKD('newdir')
        self.assert_(isinstance(d.result, failure.Failure),
                     'MKD newdir twice should cause a failure')

        # Cleanup the error.
        d.addErrback(lambda f: None)

    def testRMD(self):
        d = self.ftp.ftp_RMD('ned')
        self.assertNotIn('ned', self.root._children.keys())

        d = self.ftp.ftp_RMD('ned')
        self.assert_(isinstance(d.result, failure.Failure),
                     'RMD newdir twice should cause a failure')

        # Cleanup the error.
        d.addErrback(lambda f: None)

        d = self.ftp.ftp_RMD('file.txt')
        self.assert_(isinstance(d.result, failure.Failure),
                     'RMD should not be able to remove directories.')

        # Cleanup the error.
        d.addErrback(lambda f: None)

    def testDELE(self):
        d = self.ftp.ftp_DELE('file.txt')
        self.assertNotIn('file.txt', self.root._children.keys())

        d = self.ftp.ftp_DELE('file.txt')
        self.assert_(isinstance(d.result, failure.Failure),
                     'DELE newdir twice should cause a failure')

        # Cleanup the error.
        d.addErrback(lambda f: None)

        d = self.ftp.ftp_DELE('ned')
        self.assert_(isinstance(d.result, failure.Failure),
                     'DELE should not be able to remove directories.')

        # Cleanup the error.
        d.addErrback(lambda f: None)

    def testRename(self):
        self.ftp.ftp_RNFR('file.txt')
        self.ftp.ftp_RNTO('blah.txt')
        self.assertNotIn('file.txt', self.root._children.keys())
        self.assertIn('blah.txt', self.root._children.keys())

        # renaming a missing file should fail
        self.ftp.ftp_RNFR('file.txt')
        d = self.ftp.ftp_RNTO('blah.txt')
        self.assert_(isinstance(d.result, failure.Failure),
                     "renaming a missing file should cause a failure")

        # Cleanup the error.
        d.addErrback(lambda f: None)

        # renaming a file to an existing directory should fail
        self.ftp.ftp_RNFR('blah.txt')
        d = self.ftp.ftp_RNTO('ned')
        self.assert_(isinstance(d.result, failure.Failure),
                     "renaming a file into a dir should cause a failure")

        # Cleanup the error.
        d.addErrback(lambda f: None)

