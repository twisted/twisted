# -*- test-case-name: twisted.test.test_world -*-
#
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

from __future__ import generators

class BoundProxy:
    __original = None
    def __init__(self, o, binder):
        self.__binder = binder
        self.__original = o

    def __getattr__(self, attr):
        return getattr(self.__original, attr)

    def __setattr__(self, attr, val):
        if self.__original is not None:
            return setattr(self.__original, attr, val)
        self.__dict__[attr] = val


class Backwards(object):
    def __init__(self, lst):
        self.data = lst

    def __repr__(self):
        return 'Backwards('+repr(self.data)+')'

    def __cmp__(self, other):
        try:
            iother = iter(other)
            iself = iter(self)
        except TypeError:
            return object.__cmp__(self, other)
        try:
            while 1:
                res = cmp(iself.next(), iother.next())
                if res != 0:
                    return res
        except StopIteration:
            pass
        try:
            iself.next()
            res += 1
        except StopIteration:
            pass
        try:
            iother.next()
            res -= 1
        except StopIteration:
            pass
        return res

    def __lt__(self, other):
        return cmp(self, other) < 0

    def __le__(self, other):
        return cmp(self, other) <= 0

    def __eq__(self, other):
        return cmp(self, other) == 0

    def __ne__(self, other):
        return cmp(self, other) != 0

    def __gt__(self, other):
        return cmp(self, other) == 1

    def __ge__(self, other):
        return cmp(self, other) >= 1

    def __contains__(self, item):
        return item in self.data

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        for i in xrange(len(self)):
            yield self[i]
    
    def __getitem__(self, i):
        return self.data[-(i+1)]

    def __setitem__(self, i, item):
        self.data[-(i+1)] = item

    def __delitem__(self, i):
        del self.data[-(i+1)]

    def __getslice__(self, i, j):
        i = max(i, 0); j = max(j, 0)
        i, j = -j+1, -(i+1)
        return self.__class__(self.data[i:j])

    def __setslice__(self, i, j, other):
        i = max(i, 0); j = max(j, 0)
        i, j = -(j+1), -(i+1)
        if isinstance(other, UserList):
            self.data[i:j] = other.data
        elif isinstance(other, type(self.data)):
            self.data[i:j] = other
        else:
            self.data[i:j] = list(other)

    def __delslice__(self, i, j):
        i = max(i, 0); j = max(j, 0)
        i, j = -(j+1), -(i+1)
        del self.data[i:j]

    def __add__(self, other):
        return list(self) + other

    def __radd__(self, other):
        return other + list(self)

    def __iadd__(self, other):
        for x in other:
            self.append(x)

    def __mul__(self, n):
        return self.__class__(self.data * n)
    __rmul__ = __mul__

    def __imul__(self, n):
        self.data *= n
        return self

    def append(self, item):
        self.data.insert(0, item)

    def insert(self, i, item):
        self.data.insert(len(self) - i, item)
    
    def pop(self, i=-1):
        return self.data.pop(len(self) - (i + 1))

    def remove(self, item):
        self.data.remove(item)

    def count(self, item):
        return self.data.count(item)
        
    def index(self, item):
        return self.data.index(item)

    def reverse(self):
        self.data.reverse()

    def sort(self, *args):
        self.data.sort(*args)
        # do we sort 'forwards' or backwards??
        # I guess backwards
        self.data.reverse()

    def extend(self, other):
        for x in other:
            self.append(x)
