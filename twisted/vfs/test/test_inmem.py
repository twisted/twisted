# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.vfs.backends import inmem
from twisted.vfs import ivfs

class InMemTest(unittest.TestCase):
    def setUp(self):
        self.root = inmem.InMemNode(filesystem={
            'afile': 'some data',
            'adir': {
                'anotherfile': 'more data',
            }
        })

    def tearDown(self):
        pass

    def test_exists_does(self):
        return self.root.child('adir').exists().addCallback(self.assert_)

    def test_exists_doesnt(self):
        return self.root.child('badfile').exists().addCallback(self.assertNot)

    def test_exists_does_1deep(self):
        self.root.child('adir', 'anotherfile').exists().addCallback(self.assert_)

    def test_exists_doesnt_1deep(self):
        self.root.child('adir', 'badfile').exists().addCallback(self.assertNot)

    def test_children(self):        
        def _check(children):
            names = [name for name, ob in children]
            names.sort()
            self.assertEqual(names, ['adir', 'afile'])
        return self.root.children().addCallback(_check)

    def test_children_notContainer(self):        
        d = self.root.child('afile').children()
        self.assertFailure(d, ivfs.NotAContainerError)
        return d

    def test_children_notFound(self):
        d = self.root.child('froar').children()
        self.assertFailure(d, ivfs.NotFoundError)
        return d

    def test_isdir(self):
        return self.root.child('adir').isdir().addCallback(self.assert_)

    def test_isdir_notContainer(self):
        return self.root.child('afile').isdir().addCallback(self.assertNot)

    def test_isdir_notFound(self):
        d = self.root.child('froar').isdir()
        self.assertFailure(d, ivfs.NotFoundError)
        return d

    def test_isfile(self):
        return self.root.child('afile').isfile().addCallback(self.assert_)

    def test_isfile_notLeaf(self):
        return self.root.child('adir').isfile().addCallback(self.assertNot)

    def test_isfile_notFound(self):
        d = self.root.child('froar').isfile()
        self.assertFailure(d, ivfs.NotFoundError)
        return d

    def test_createDirectory(self):
        def _check(result):
            return self.root.child('adir').child('newdir').isdir(
                ).addCallback(self.assert_)
        return self.root.child('adir').createDirectory('newdir'
            ).addCallback(_check)

    def test_createDirectory_alreadyExists(self):
        d = self.root.createDirectory('afile')
        self.assertFailure(d, ivfs.VFSError)
        return d

    def test_createDirectory_notContainer(self):
        d = self.root.child('afile').createDirectory('afile')
        self.assertFailure(d, ivfs.NotAContainerError)
        return d

    def test_createDirectory_notFound(self):
        d = self.root.child('froar').createDirectory('afile')
        self.assertFailure(d, ivfs.NotFoundError)
        return d

    def test_createFile(self):
        def _check(result):
            return self.root.child('adir').child('newfile').isfile(
                ).addCallback(self.assert_)
        return self.root.child('adir').createFile('newfile'
            ).addCallback(_check)

    def test_createFile_alreadyExists_container(self):
        d = self.root.createFile('adir')
        self.assertFailure(d, ivfs.VFSError)
        return d

    def test_createFile_alreadyExists_leaf(self):
        d = self.root.createFile('afile')
        self.assertFailure(d, ivfs.VFSError)
        return d

    def test_createFile_alreadyExists_leafNonExclusive(self):
        def _check(result):
            #XXX - check that the file is truncated
            return self.root.child('afile').isfile(
                ).addCallback(self.assert_)
        return self.root.createFile('afile', False
            ).addCallback(_check)

    def test_createFile_notContainer(self):
        d = self.root.child('afile').createFile('afile')
        self.assertFailure(d, ivfs.NotAContainerError)
        return d

    def test_createFile_notFound(self):
        d = self.root.child('froar').createFile('afile')
        self.assertFailure(d, ivfs.NotFoundError)
        return d

