import sets

from twisted.trial import unittest, assertions as A

from twisted.vfs import ivfs, pathutils
from twisted.vfs.adapters import stream
from twisted.vfs.backends import inmem

from twisted.web2.stream import IByteStream

sftpAttrs = ['size', 'uid', 'gid', 'nlink', 'mtime', 'atime', 'permissions']

class StreamAdapterTest(unittest.TestCase):
    def setUp(self):
        root = inmem.FakeDirectory()
        filesystem = pathutils.FileSystem( root )
        self.ned = ned = inmem.FakeDirectory('ned', root)
        self.f = f = inmem.FakeFile('file.txt', root, 'wobble\n')
        root._children = { 'ned' : ned, 'file.txt' : f }
        self.bs = IByteStream(self.f, None)

    def test_adapt(self):
        A.assertNotEquals(self.bs, None,
                          "Could not adapt %r to IByteStream" % (self.f))

    def test_read(self):
        A.assertEquals(self.bs.read(), 'wobble\n')

    def test_readOutofData(self):
        self.bs.read()
        A.assertEquals(self.bs.read(), None)

