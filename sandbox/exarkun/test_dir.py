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
        i = iter(d)
        l = 0
        i.next()
        self.failUnless(d.tell() > l)
        l = d.tell()
        i.next()
        self.failUnless(d.tell() > l)
        l = d.tell()
        i.next()
        self.failUnless(d.tell() > l)
        l = d.tell()
        i.next()
        self.failUnless(d.tell() > l)
        l = d.tell()
        i.next()
        self.failUnless(d.tell() > l)


    def testClose(self):
        self.d.close()
        self.failUnlessRaises(dir.DirError, iter(self.d).next)

    def testSeek(self):
        d = self.d
        i = iter(d)
        l = d.tell()
        i.next()
        i.next()
        d.seek(l)
        self.assertEquals(d.tell(), l)

    def testScan(self):
        d = self.d
        L = list(d.scan(lambda d: d.name.startswith('5')))
        self.assertEquals(len(L), 1)
        self.assertEquals(L[0].name, '5')

