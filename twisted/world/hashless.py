# -*- test-case-name: twisted.test.test_hashless -*-
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
"""Mapping classes that use object identification 
rather than hash/equality properties.
"""

from __future__ import generators
from weakref import ref
import UserDict

class HashlessDictionary(UserDict.IterableUserDict):
    def __getitem__(self, key):
        return self.data[id(key)][1]

    def __repr__(self):
        return "<HashlessDictionary at %s>" % hex(id(self))

    def __delitem__(self, key):
        del self.data[id(key)]

    def __setitem__(self, key, value):
        self.data[id(key)] = key, value

    def copy(self):
        return self.__class__(self)

    def get(self, key, default=None):
        try:
            return self.data[id(key)][1]
        except KeyError:
            return default

    def has_key(self, key):
        return self.__contains__(key)

    def __contains__(self, key):
        return id(key) in self.data

    def items(self):
        return list(self.iteritems())

    def iteritems(self):
        return self.data.itervalues()

    def iterkeys(self):
        for (key, o) in self.iteritems():
            yield key
    __iter__ = iterkeys

    def itervalues(self):
        for (key, o) in self.iteritems():
            yield o

    def popitem(self):
        return self.data.popitem()[1]

    def pop(self, key, *args):
        try:
            return self.data.pop(id(key))[1]
        except KeyError:
            if args:
                return args[0]
            raise
        
    def setdefault(self, key, default):
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return default

    def update(self, dict):
        for key, o in dict.iteritems():
            self[key] = o

    def values(self):
        return list(self.itervalues())

    def keys(self):
        return list(self.iterkeys())

class HashlessWeakValueDictionary(HashlessDictionary):
    """Mapping class that references values weakly and keys by id.

    Internal storage is id(key) -> (key, ref(value))
    """
    def __getitem__(self, key):
        o = self.data[id(key)][1]()
        if o is None:
            raise KeyError, key
        else:
            return o

    def __repr__(self):
        return "<HashlessWeakValueDictionary at %s>" % hex(id(self))

    def __setitem__(self, key, value):
        self.data[id(key)] = key, ref(value, self.__makeremove(key))

    def get(self, key, default=None):
        try:
            wr = self.data[id(key)][1]
        except KeyError:
            return default
        else:
            o = wr()
            if o is None:
                # This should only happen
                return default
            else:
                return o

    def iteritems(self):
        for (key, wr) in self.data.itervalues():
            o = wr()
            if o is not None:
                yield key, o

    def popitem(self):
        while 1:
            idkey, (key, wr) = self.data.popitem()
            o = wr()
            if o is not None:
                return key, o

    def pop(self, key, *args):
        try:
            o = self.data.pop(id(key))[1]()
        except KeyError:
            if args:
                return args[0]
            raise
        if o is None:
            raise KeyError, key
        else:
            return o

    def __makeremove(self, key):
        self, key = ref(self), id(key)
        def remove(o):
            myself = self()
            if myself is not None and key in myself.data:
                del myself.data[key]
        return remove


class HashlessWeakKeyDictionary(HashlessDictionary):
    """ Mapping class that references keys weakly and by id.

    Internal storage is id(key) -> ref(key), value
    """

    def __repr__(self):
        return "<HashlessWeakKeyDictionary at %s>" % hex(id(self))

    def __setitem__(self, key, value):
        self.data[id(key)] = ref(key, self.__makeremove(key)), value

    def iteritems(self):
        for wr, v in self.data.itervalues():
            k = wr()
            if k is not None:
                yield k, v

    def popitem(self):
        while 1:
            idkey, (wr, v) = self.data.popitem()
            k = wr()
            if k is not None:
                return k, v

    def pop(self, key, *args):
        try:
            return self.data.pop(id(key))[1]
        except KeyError:
            return args[0]

    def __makeremove(self, key):
        self, key = ref(self), id(key)
        def remove(o):
            myself = self()
            if myself is not None and key in myself.data:
                del myself.data[key]
        return remove
