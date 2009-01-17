# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A least-recently-used eviction cache for L{twisted.words.xish.domish}.
"""


class LRUCache(object):
    """
    A key/value cache which tries to keep the most recently used items.

    @ivar _size: The maximum number of items which will be allowed to remain
        in the cache.
    """
    def __init__(self, size):
        self._size = size
        self._items = {}
        self._get = self._items.get
        self._order = []
        self._remove = self._order.remove
        self._append = self._order.append


    def get(self, key):
        value = self._items[key]
        self._remove(key)
        self._append(key)
        return value


    def put(self, key, value):
        if key in self._items:
            self._items[key] = value
            self._remove(key)
            self._append(key)
        else:
            self._items[key] = value
            self._append(key)
            if len(self._order) > self._size:
                del self._items[self._order.pop(0)]
