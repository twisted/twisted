# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import shutil

from twisted.python import dir
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
        L = [e[0] for e in self.d]
        L.sort()
        self.assertEquals(L[:2], ['.', '..'])
        self.assertEquals(L[2:], map(str, range(10)))

    def testRewind(self):
        d = self.d
        list(d)
        d.rewind()
        L = [e[0] for e in d]
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
        i.next()
        i.next()
        l = d.tell()
        v = i.next()
        for _ in range(100):
            d.seek(l)
            self.assertEquals(i.next(), v)
        self.failIfEquals(v, i.next())

    def testScan(self):
        d = self.d
        L = list(d.scan(lambda d: d[0].startswith('5')))
        self.assertEquals(len(L), 1)
        self.assertEquals(L[0][0], '5')

class FunctionsTestCase(unittest.TestCase):
    def testListDirectories(self):
        d = dir.listDirectories(os.pardir)
        self.failIf(os.curdir in d)
        self.failIf(os.pardir in d)
        
        d.sort()
        listed = []
        for D in os.listdir(os.pardir):
            Dir = os.path.join(os.pardir, D)
            if os.path.isdir(Dir):
                listed.append(D)
        listed.sort()
        
        self.assertEquals(listed, d)

    def testListLinks(self):
        os.symlink('d', 'c')
        os.symlink('c', 'b')
        os.symlink('b', 'a')
        
        file('b', 'w').close()

        links = dir.listLinks('.')
        links.sort()
        expected = filter(os.path.islink, os.listdir('.'))
        expected.sort()        
        self.assertEquals(links, expected)
        