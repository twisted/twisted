# -*- coding: Latin-1 -*-

import os
import shutil

import dir
from twisted.trial import unittest

class DirTestCase(unittest.TestCase):
    def setUp(self):
        os.mkdir('dirent')
        for i in range(10):
            os.mkdir(os.path.join('dirent', str(i)))
        self.d = dir.DirType('dirent')
    
    def tearDown(self):
        shutil.rmtree('dirent')

    def testDir(self):
        L = [e.name for e in self.d]
        L.sort()
        self.assertEquals(L[:2], ['.', '..'])
        self.assertEquals(L[2:], map(str, range(10)))

    def testRewind(self):
        d = self.d
        list(d)
        d.rewind()
        L = [e.name for e in d]
        L.sort()
        self.assertEquals(L[:2], ['.', '..'])
        self.assertEquals(L[2:], map(str, range(10)))

    def testTell(self):
        d = self.d
        l = 0
        d.next()
        self.failUnless(d.tell() > l)
        l = d.tell()
        d.next()
        self.failUnless(d.tell() > l)
        l = d.tell()
        d.next()
        self.failUnless(d.tell() > l)
        l = d.tell()
        d.next()
        self.failUnless(d.tell() > l)
        l = d.tell()
        d.next()
        self.failUnless(d.tell() > l)


    def testClose(self):
        self.d.close()
        self.failUnlessRaises(dir.DirError, self.d.next)

    def testSeek(self):
        d = self.d
        l = d.tell()
        d.next()
        d.next()
        d.seek(l)
        self.assertEquals(d.tell(), l)
