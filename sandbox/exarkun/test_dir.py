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
    
    def tearDown(self):
        shutil.rmtree('dirent')

    def testDir(self):
        L = [e.name for e in dir.DirType('dirent')]
        L.sort()
        self.assertEquals(L[:2], ['.', '..'])
        self.assertEquals(L[2:], map(str, range(10)))

            
    def testRewind(self):
        d = dir.DirType('dirent')
        list(d)
        d.rewind()
        L = [e.name for e in d]
        L.sort()
        self.assertEquals(L[:2], ['.', '..'])
        self.assertEquals(L[2:], map(str, range(10)))
