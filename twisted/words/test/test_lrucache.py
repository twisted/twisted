# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.xish._lrucache}.
"""

from twisted.trial.unittest import TestCase

from twisted.words.xish._lrucache import LRUCache


class LRUCacheTests(TestCase):
    """
    Tests for L{LRUCache}.
    """
    def test_getMiss(self):
        """
        L{LRUCache.get} raises L{KeyError} when passed a key which has no
        corresponding value in the cache.
        """
        cache = LRUCache(1)
        self.assertRaises(KeyError, cache.get, "foo")


    def test_getHit(self):
        """
        L{LRUCache.put} associates a value with a key in the cache and
        causes L{LRUCache.get} to return that value when passed that key in
        the future.
        """
        cache = LRUCache(1)
        cache.put("foo", "bar")
        self.assertEqual(cache.get("foo"), "bar")


    def test_putBelowLimit(self):
        """
        When the number of items in a cache is below the size limit passed
        to the initializer, L{LRUCache.put} does not evict any items.
        """
        cache = LRUCache(3)
        cache.put("foo", "bar")
        cache.put("baz", "quux")
        cache.put("apple", "orange")
        self.assertEqual(cache.get("foo"), "bar")
        self.assertEqual(cache.get("baz"), "quux")
        self.assertEqual(cache.get("apple"), "orange")


    def test_putAboveLimit(self):
        """
        When the number of items in a cache exceeds the size limit passed to
        the initializer, L{LRUCache.put} evicts the least recently accessed
        item from the cache.
        """
        cache = LRUCache(3)
        cache.put("foo", "bar")
        cache.put("baz", "quux")
        cache.put("apple", "orange")

        # The only access so far has been puts.  "foo" was the least
        # recently put key.  It should be evicted.
        cache.put("orange", "banana")
        self.assertRaises(KeyError, cache.get, "foo")

        # Other items should remain.
        self.assertEqual(cache.get("baz"), "quux")
        self.assertEqual(cache.get("apple"), "orange")
        self.assertEqual(cache.get("orange"), "banana")

        # "baz" would be next evicted, but this get will make it the most
        # recently accessed.  That means "apple" will be the least recently
        # accessed.
        cache.get("baz")
        cache.put("pear", "grape")
        self.assertEqual(cache.get("baz"), "quux")
        self.assertRaises(KeyError, cache.get, "apple")
        self.assertEqual(cache.get("orange"), "banana")
        self.assertEqual(cache.get("pear"), "grape")

