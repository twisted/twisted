# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

import os

from twisted.trial import unittest
from twisted.persisted.filepile import FilePile, LenientIntCompare, readlink, ISorter, DefaultSorter, symlink

class SymlinkIntSorter(DefaultSorter):

    __implements__ = ISorter

    def loadItem(self, fullpath):
        return int(readlink(fullpath))

class SymlinkIntPlusSorter(SymlinkIntSorter):
    comparePathFragments = LenientIntCompare()

class LowLevelFilePileTest(unittest.TestCase):

    def pile(self):
        return FilePile(self.caseMethodName, SymlinkIntSorter())

    def intpile(self):
        return FilePile(self.caseMethodName+'-int',
                        SymlinkIntPlusSorter())

    def fourFilePile(self):
        pl = self.pile()
        pl.insertLink("1", "a")
        pl.insertLink("2", "a", "ba")
        pl.insertLink("4", "a", "bc", "hello")
        pl.insertLink("3", "a", "bb", "c")
        return pl

    def testSimple(self):
        pl = self.fourFilePile()
        self.assertEquals(list(pl), range(1,5))

    def testReverse(self):
        pl = self.fourFilePile()
        l = range(1, 5)
        l.reverse()
        list(pl) # exhaust!
        self.assertEquals(list(pl.backwards()), l)

    def testBackAndForth(self):
        pl = iter(self.fourFilePile())
        for i in range(1,5):
            for x in range(10):
                self.assertEquals(pl.next(), i)
                self.assertEquals(pl.prev(), i)
            pl.next()

    def testDifferentOrderings(self):
        pl = self.pile()
        pl2 = self.intpile()
        for p in pl, pl2:
            p.insertLink("1", "1")
            p.insertLink("2", "2")
            p.insertLink("3", "3")
            p.insertLink("11","11")
            p.insertLink("12","12")
            p.insertLink("13","13")
        self.assertEquals(list(pl),
                          [1, 11, 12, 13, 2, 3])
        self.assertEquals(list(pl2),
                          [1, 2, 3, 11, 12, 13])

    def testNumberedLinksHardcore(self):
        # kick it off before the insanity starts thanks to yucky maildir
        p = self.intpile()
        p.numberedLink("0")
        import threading
        def target():
            mypile = self.intpile()
            for x in range(10):
                mypile.numberedLink("0")
            # d = os.open(os.path.join(mypile.dirname, '0.pile'),0)
            # os.fdatasync(d)
            # os.close(d)

        threads = []
        for x in range(10):
            t = threading.Thread(target=target)
            threads.append(t)
            t.start()
        for thread in threads:
            thread.join()
        p = self.intpile()
        self.assertEquals(p.numberedLink("0"),
                          os.path.join(p.dirname,"0.pile","101.item"))
        self.assertEquals(list(p), range(102))
        

    def testJumpTo(self):
        pl = self.intpile()
        for a in range(10):
            for b in range(10):
                for c in range(10):
                    pl.insertLink(''.join(map(str,[a,b,c])),
                                  *map(str,[a,b,c]))
        pl = iter(pl)
        for num in 112, 417, 16, 943:
            pl.jumpTo(*''.join(list('%0.3d'% num)))
            self.assertEquals(list(pl),
                              range(num,1000))

class RoloEntry:
    def __init__(self, first, last):
        self.first = first
        self.last = last

    def __cmp__(self, other):
        x = cmp(self.last.lower(), other.last.lower())
        if x:
            return x
        else:
            return cmp(self.first.lower(), other.first.lower())

    def __repr__(self):
        return 'RoloEntry(%r,%r)' % (self.first, self.last)

class RoloSorter:

    __implements__ = ISorter

    allowDuplicates = False

    def pathFromItem(self, item):
        return [item.last.lower(), item.first.lower()]

    def pathFromKey(self, key):
        return key.split(', ')

    def compareItemToKey(self, item, key):
        return cmp((item.last+', '+item.first).lower(), key)

    def loadItem(self, fullpath):
        encodedName = readlink(fullpath)
        first, last = encodedName.decode('base64').split('---')
        return RoloEntry(first, last)

    def saveItem(self, item, fullpath):
        encodedName = (item.first + '---' + item.last).encode('base64')
        os.makedirs(os.path.dirname(fullpath))
        symlink(encodedName, fullpath)

    def comparePathFragments(self, path1, path2):
        return cmp(path1.lower(), path2.lower())

class HighLevelFilePileTest(unittest.TestCase):

    def testRolo(self):
        fp = FilePile(self.caseMethodName, RoloSorter())
        bob = RoloEntry("Bob", "jones")
        bob2 = RoloEntry("Bob", "JONEZ")
        bob3 = RoloEntry("Cesar", "JONESs")
        nb1 = RoloEntry("Bleh", "janes")
        nb2 = RoloEntry("Bleh", "jznes")
        fp.add(bob)
        fp.add(bob2)
        fp.add(bob3)
        l = [bob, bob2, bob3]
        l.sort()
        l2 = list(fp.itemsBetween('jb', 'jy'))
        self.assertEquals( l, l2 )
        fp.add(nb1)
        fp.add(nb2)
        l2 = list(fp.itemsBetween('jb', 'jy'))
        self.assertEquals( l, l2 )
