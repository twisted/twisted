"""Tests for mDNS."""

from twisted.trial import unittest
from twisted.internet import reactor
from twisted.protocols import dns
from twisted.python.runtime import seconds

import mdns


class FakeResolver:
    """Resolver for testing service subscriptions.

    Time runs ten times as fast as normal.
    """
    
    def __init__(self):
        self.protocol = self
        self.writes = []
        self.start = seconds()
        self.scheduled = []
        self.removed = []
    
    def write(self, **kwargs):
        self.writes.append(((seconds() - self.start) / 10, kwargs))

    def _removeSubscription(self, service):
        self.removed.append(service)
    
    def callLater(self, t, f, *args, **kwargs):
        # woo, make time go faster
        t = t * 0.1
        s = reactor.callLater(t, f, *args, **kwargs)
        self.scheduled.append(s)
        return s

    def close(self):
        for s in self.scheduled:
            if s.active(): s.cancel()


class ServiceSubscriptionTests(unittest.TestCase):

    def setUp(self):
        self.resolver = FakeResolver()
        self.sub = mdns.ServiceSubscription("_workstation._tcp.local", self.resolver)
        
    def tearDown(self):
        self.resolver.close()
    
    def deliverMessage(self, rr):
        m = dns.Message()
        m.answer = True
        m.answers = [rr]
        self.resolver.messageReceived(m)

    def testPTRSentAtIntervals(self):
        self.resolver.callLater(15, reactor.crash)
        reactor.run()
        self.assertEquals(len(self.resolver.writes), 4)
        self.testSubscription()
    
    def testPTRResponse(self):
        # should send SRV request in response
        self.testSubscription()
    
    def testSubscription(self):
        o = object()
        o2 = object()
        self.sub.subscribe(o)
        self.sub.subscribe(o2)
        self.sub.unsubscribe(o2)
        self.assertEquals(self.resolver.removed, [])
        self.sub.unsubscribe(o)
        self.assertEquals(self.resolver.removed, ["_workstation._tcp.local"])
        # after unsubscribe all scheduled stuff should be cancelled
        for s in self.resolver.scheduled:
            if s.active():
                raise RuntimeError, "%s was not cancelled" % s
    
    def testExpirationRemoval(self):
        self.testSubscription()

    def testExpirationResends(self):
        self.testSubscription()

    def testSRVRenewal(self):
        self.testSubscription()

    def testSRVReceived(self):
        self.testSubscription()
