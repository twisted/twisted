import os.path

from twisted.trial import unittest

from twisted.vfs import ivfs, pathutils
from twisted.vfs.adapters import stream
from twisted.vfs.backends import inmem, osfs

from twisted.web2.stream import IByteStream

sftpAttrs = ['size', 'uid', 'gid', 'nlink', 'mtime', 'atime', 'permissions']

class StreamAdapterInmemTest(unittest.TestCase):
    def setUp(self):
        root = inmem.FakeDirectory()
        self.ned = ned = inmem.FakeDirectory('ned', root)
        self.f = f = inmem.FakeFile('file.txt', root, 'wobble\n')
        root._children = { 'ned' : ned, 'file.txt' : f }
        self.bs = IByteStream(self.f, None)

    def test_adapt(self):
        self.assertNotEquals(self.bs, None,
                          "Could not adapt %r to IByteStream" % (self.f))

    def test_read(self):
        self.assertEquals(self.bs.read(), 'wobble\n')

    def test_readOutofData(self):
        self.bs.read()
        self.assertEquals(self.bs.read(), None)

class StreamAdapterOSFSTest(StreamAdapterInmemTest):
    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        os.mkdir(os.path.join(self.tmpdir, 'ned'))
        f = open(os.path.join(self.tmpdir, 'file.txt'), 'wb')
        f.write('wobble\n')
        f.close()
        root = osfs.OSDirectory(self.tmpdir)
        self.f = root.child('file.txt')
        self.bs = IByteStream(self.f, None)
