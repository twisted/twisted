# Original Header:
# Written by Bram Cohen
# see LICENSE.txt for license information
#
# This is from the BitTorrent-3.3 release
#
# The text from LICENSE.txt is as follows: <<EOF
#
# Unless otherwise noted, all files are released under the MIT
# license, exceptions contain licensing information in them.
# 
# Copyright (C) 2001-2002 Bram Cohen
# 
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# The Software is provided "AS IS", without warranty of any kind,
# express or implied, including but not limited to the warranties of
# merchantability,  fitness for a particular purpose and
# noninfringement. In no event shall the  authors or copyright holders
# be liable for any claim, damages or other liability, whether in an
# action of contract, tort or otherwise, arising from, out of or in
# connection with the Software or the use or other dealings in the
# Software.
# EOF
#
# - Martin Murray <murrayma@citi.umich.edu>
#                 <mmurray@monkey.org>

from select import select, error
from time import sleep
from types import IntType
from bisect import bisect
POLLIN = 1
POLLOUT = 2
POLLERR = 8
POLLHUP = 16

class poll:
    def __init__(self):
        self.rlist = []
        self.wlist = []
        
    def register(self, f, t):
        if type(f) != IntType:
            f = f.fileno()
        if (t & POLLIN) != 0:
            insert(self.rlist, f)
        else:
            remove(self.rlist, f)
        if (t & POLLOUT) != 0:
            insert(self.wlist, f)
        else:
            remove(self.wlist, f)
        
    def unregister(self, f):
        if type(f) != IntType:
            f = f.fileno()
        remove(self.rlist, f)
        remove(self.wlist, f)

    def poll(self, timeout = None):
        if self.rlist != [] or self.wlist != []:
            r, w, e = select(self.rlist, self.wlist, [], timeout)
        else:
            sleep(timeout)
            return []
        result = []
        for s in r:
            result.append((s, POLLIN))
        for s in w:
            result.append((s, POLLOUT))
        return result

def remove(list, item):
    i = bisect(list, item)
    if i > 0 and list[i-1] == item:
        del list[i-1]

def insert(list, item):
    i = bisect(list, item)
    if i == 0 or list[i-1] != item:
        list.insert(i, item)

def test_remove():
    x = [2, 4, 6]
    remove(x, 2)
    assert x == [4, 6]
    x = [2, 4, 6]
    remove(x, 4)
    assert x == [2, 6]
    x = [2, 4, 6]
    remove(x, 6)
    assert x == [2, 4]
    x = [2, 4, 6]
    remove(x, 5)
    assert x == [2, 4, 6]
    x = [2, 4, 6]
    remove(x, 1)
    assert x == [2, 4, 6]
    x = [2, 4, 6]
    remove(x, 7)
    assert x == [2, 4, 6]
    x = [2, 4, 6]
    remove(x, 5)
    assert x == [2, 4, 6]
    x = []
    remove(x, 3)
    assert x == []

def test_insert():
    x = [2, 4]
    insert(x, 1)
    assert x == [1, 2, 4]
    x = [2, 4]
    insert(x, 3)
    assert x == [2, 3, 4]
    x = [2, 4]
    insert(x, 5)
    assert x == [2, 4, 5]
    x = [2, 4]
    insert(x, 2)
    assert x == [2, 4]
    x = [2, 4]
    insert(x, 4)
    assert x == [2, 4]
    x = [2, 3, 4]
    insert(x, 3)
    assert x == [2, 3, 4]
    x = []
    insert(x, 3)
    assert x == [3]
