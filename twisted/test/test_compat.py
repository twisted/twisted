# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Matthew W. Lefkowitz
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

from twisted.trial import unittest

import os, sys

from twisted.python import compat

class IterableCounter:
    def __init__(self, lim=0):
        self.lim = lim
        self.i = -1

    def __iter__(self):
        return self

    def next(self):
        self.i += 1
        if self.i >= self.lim:
            raise StopIteration
        return self.i
        
class CopmatTestCase(unittest.TestCase):
    def testDict(self):
        dict = compat.dict
        d1 = {'a': 'b'}
        d2 = dict(d1)
        self.assertEquals(d1, d2)
        d1['a'] = 'c'
        self.assertNotEquals(d1, d2)
        d2 = dict(d1.items())
        self.assertEquals(d1, d2)
        d2 = dict(a='c')
        self.assertEquals(d1, d2)
        d2 = dict(d1, b='c')
        d3 = dict(d1.items(), b='c')
        d1['b'] = 'c'
        self.assertEquals(d1, d2)
        self.assertEquals(d1, d3)

    def testBool(self):
        bool = compat.bool
        True = compat.True
        False = compat.False
        self.assertEquals(bool('hi'), True)
        self.assertEquals(bool(True), True)
        self.assertEquals(bool(''), False)
        self.assertEquals(bool(False), False)

    def testIteration(self):
        iter = compat.iter
        StopIteration = compat.StopIteration
        
        lst1, lst2 = range(10), []
        
        for i in iter(lst1):
            lst2.append(i)
        self.assertEquals(lst1, lst2)
        del lst2[:]

        try:
            iterable = iter(lst1)
            while 1:
                lst2.append(iterable.next())
        except StopIteration:
            pass
        self.assertEquals(lst1, lst2)
        del lst2[:]

        for i in iter(IterableCounter(10)):
            lst2.append(i)
        self.assertEquals(lst1, lst2)
        del lst2[:]

        try:
            iterable = iter(IterableCounter(10))
            while 1:
                lst2.append(iterable.next())
        except StopIteration:
            pass
        self.assertEquals(lst1, lst2)
        del lst2[:]

        for i in iter(IterableCounter(20).next, 10):
            lst2.append(i)
        self.assertEquals(lst1, lst2)
        
    def testIsinstance(self):
        isinstance = compat.isinstance
        # is this really supposed to be injected into types?
        from types import StringTypes
        self.assert_(isinstance(u'hi', StringTypes))
        self.assert_(isinstance(self, unittest.TestCase))
        self.assert_(isinstance({}, dict))
