# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import time

from twisted.trial import unittest

from twisted.names import dns, cache

class Caching(unittest.TestCase):
    def testLookup(self):
        c = cache.CacheResolver({
            dns.Query(name='example.com', type=dns.MX, cls=dns.IN): (time.time(), ([], [], []))})
        return c.lookupMailExchange('example.com').addCallback(self.assertEqual, ([], [], []))
