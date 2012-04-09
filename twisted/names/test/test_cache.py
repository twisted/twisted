# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import time

from twisted.trial import unittest

from twisted.names import dns, cache
from twisted.internet import task

class Caching(unittest.TestCase):
    """
    Tests for L{cache.CacheResolver}.
    """

    def test_lookup(self):
        c = cache.CacheResolver({
            dns.Query(name='example.com', type=dns.MX, cls=dns.IN): (time.time(), ([], [], []))})
        return c.lookupMailExchange('example.com').addCallback(self.assertEqual, ([], [], []))


    def test_normalLookup(self):
        """
        When a cache lookup finds a cached entry from 1 second ago, it is
        returned with a TTL of original TTL minus the elapsed 1 second.
        """
        r = ([dns.RRHeader("example.com", dns.A, dns.IN, 60,
                           dns.Record_A("127.0.0.1", 60))],
             [dns.RRHeader("example.com", dns.A, dns.IN, 50,
                           dns.Record_A("127.0.0.1", 50))],
             [dns.RRHeader("example.com", dns.A, dns.IN, 40,
                           dns.Record_A("127.0.0.1", 40))])

        clock = task.Clock()

        c = cache.CacheResolver({
                dns.Query(name="example.com", type=dns.A, cls=dns.IN) :
                    (clock.seconds(), r)}, reactor=clock)

        clock.advance(1)

        def cbLookup(result):
            self.assertEquals(result[0][0].ttl, 59)
            self.assertEquals(result[1][0].ttl, 49)
            self.assertEquals(result[2][0].ttl, 39)
            self.assertEquals(result[0][0].name.name, "example.com")

        return c.lookupAddress("example.com").addCallback(cbLookup)


    def test_negativeTTLLookup(self):
        """
        When the cache is queried exactly as the cached entry should expire
        but before it has actually been cleared, the TTL will be 0, not
        negative.
        """
        r = ([dns.RRHeader("example.com", dns.A, dns.IN, 60,
                           dns.Record_A("127.0.0.1", 60))],
             [dns.RRHeader("example.com", dns.A, dns.IN, 50,
                           dns.Record_A("127.0.0.1", 50))],
             [dns.RRHeader("example.com", dns.A, dns.IN, 40,
                           dns.Record_A("127.0.0.1", 40))])

        clock = task.Clock()
        # Make sure timeouts never happen, so entries won't get cleared:
        clock.callLater = lambda *args, **kwargs: None

        c = cache.CacheResolver({
            dns.Query(name="example.com", type=dns.A, cls=dns.IN) :
                (clock.seconds(), r)}, reactor=clock)

        clock.advance(60.1)

        def cbLookup(result):
            self.assertEquals(result[0][0].ttl, 0)
            self.assertEquals(result[0][0].ttl, 0)
            self.assertEquals(result[0][0].ttl, 0)
            self.assertEquals(result[0][0].name.name, "example.com")

        return c.lookupAddress("example.com").addCallback(cbLookup)

