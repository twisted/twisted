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
from twisted.trial import unittest

from twisted.world.hashless import HashlessDictionary,\
     HashlessWeakKeyDictionary, HashlessWeakValueDictionary

import gc

class EvilClass:
    def __hash__(self):
        raise TypeError, "I'm so evil"

class TestHashlessDictionary(unittest.TestCase):
    def test_EvilClass(self):
        d = {}
        self.failUnlessRaises(TypeError, d.__setitem__, EvilClass(), EvilClass())

    def test_evil(self):
        e1, e2 = EvilClass(), EvilClass()
        d = HashlessDictionary()
        d[e1] = 1
        d[e2] = 1
        del d[e2]
        d[e2] = 1
        d[e2] = e1
        d[3] = 3
        self.failUnlessEqual(d[e2], e1)
        self.failUnlessEqual(len(d.items()), 3)

class TestHashlessWeakKeyDictionary(unittest.TestCase):
    def test_evil(self):
        e1, e2 = EvilClass(), EvilClass()
        d = HashlessWeakKeyDictionary()
        d[e1] = e1
        d[e2] = id(e2)
        e2 = d[e2]
        gc.collect()
        self.failUnlessEqual(len(d.data), len(d.items()))
        self.failUnlessEqual(len(d.data), 1)

class TestHashlessWeakValueDictionary(unittest.TestCase):
    def test_evil(self):
        e1, e2 = EvilClass(), EvilClass()
        d = HashlessWeakValueDictionary()
        d[e1] = e2
        del e2
        gc.collect()
        self.failUnlessRaises(KeyError, d.__getitem__, e1)
        self.failUnlessEqual(len(d.data), len(d.items()))
        self.failUnlessEqual(len(d.data), 0)
