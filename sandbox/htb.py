# -*- Python -*-

"""Heirarchial Token Bucket traffic shaping.

Patterened after U{Martin Devera's Hierarchical Token Bucket traffic
shaper for the Linux kernel<http://luxik.cdi.cz/~devik/qos/htb/>}.

@seealso: U{HTB Linux queuing discipline manual - user guide
  <http://luxik.cdi.cz/~devik/qos/htb/manual/userg.htm>}
@seealso: U{Token Bucket Filter in Linux Advanced Routing & Traffic Control
    HOWTO<http://lartc.org/howto/lartc.qdisc.classless.html#AEN682>}
@author: U{Kevin Turner<mailto:acapnotic@twistedmatrix.com>}
"""

__version__ = '$Revision: 1.1 $'[11:-2]

from twisted.python.components import Interface
from twisted.internet import tcp
from time import time

from twisted.python.compat import *

# TODO: Brush up on my traffic shaping lingo and re-name things appropriately.

class Bucket:
    """Token bucket, or something like it.

    I can hold up to a certain number of tokens, and I drain over time.

    @cvar maxburst: Size of the bucket, in bytes.  If None, the bucket is
        never full.
    @type maxburst: int
    @cvar rate: Rate the bucket drains, in bytes per second.  If None,
        the bucket drains instantaneously.
    @type rate: int
    """

    maxburst = None
    rate = None

    _refcount = 0

    def __init__(self, parentBucket=None):
        self.content = 0
        self.parentBucket=parentBucket
        self.lastDrip = time()

    def add(self, amount):
        """Add tokens to me.

        @param amount: A quanity of tokens to add.
        @type amount: int

        @returns: The number of tokens that fit.
        @returntype: int
        """
        self.drip()
        if self.maxburst is None:
            allowable = amount
        else:
            allowable = min(amount, self.maxburst - self.content)

        if self.parentBucket is not None:
            allowable = self.parentBucket.add(allowable)
        self.content += allowable
        return allowable

    def drip(self):
        """Let some of the bucket drain.

        How much of the bucket drains depends on how long it has been
        since I was last called.

        @returns: True if I am now empty.
        @returntype: bool
        """
        if self.parentBucket is not None:
            self.parentBucket.drip()

        if self.rate is None:
            self.content = 0
            return True
        else:
            now = time()
            deltaT = now - self.lastDrip
            self.content = long(max(0, self.content - deltaT * self.rate))
            self.lastDrip = now
            return False

class IBucketFilter(Interface):
    def getBucketFor(self, *somethings, **some_kw):
        """I'll give you a bucket for something.

        @returntype: L{Bucket}
        """

class HierarchicalBucketFilter:
    """I filter things into buckets, and I am nestable.

    @cvar bucketFactory: Class of buckets to make.
    @type bucketFactory: L{Bucket} class
    @cvar sweepInterval: Seconds between sweeping out the bucket cache.
    @type sweepInterval: int
    """

    __implements__ = (IBucketFilter,)

    bucketFactory = Bucket
    sweepInterval = None

    def __init__(self, parentFilter=None):
        self.buckets = {}
        self.parentFilter = parentFilter
        self.lastSweep = time()

    def getBucketFor(self, *a, **kw):
        """You want a bucket for that?  I'll give you a bucket.

        Any parameters are passed on to L{getBucketKey}, from them it
        decides which bucket you get.

        @returntype: L{Bucket}
        """
        if ((self.sweepInterval is not None)
            and ((time() - self.lastSweep) > self.sweepInterval)):
            self.sweep()

        if self.parentFilter:
            parentBucket = self.parentFilter.getBucketFor(self, *a, **kw)
        else:
            parentBucket = None

        key = self.getBucketKey(*a, **kw)
        bucket = self.buckets.get(key)
        if bucket is None:
            bucket = self.bucketFactory(parentBucket)
            self.buckets[key] = bucket
        return bucket

    def getBucketKey(self, *a, **kw):
        """I determine who gets which bucket.

        Unless I'm overridden, everything gets the same bucket.

        @returns: something to be used as a key in the bucket cache.
        """
        return None

    def sweep(self):
        """I throw away references to empty buckets."""
        for key, bucket in self.buckets.items():
            if (bucket._refcount == 0) and bucket.drip():
                del self.buckets[key]

        self.lastSweep = time()


class FilterByHost(HierarchicalBucketFilter):
    """A bucket filter with a bucket for each host.
    """
    sweepInterval = 60 * 20

    def getBucketKey(self, sock, proto, client, server, sessionno):
        return client[0]

class FilterByServer(HierarchicalBucketFilter):
    """A bucket filter with a bucket for each service.
    """
    sweepInterval = None

    def getBucketKey(self, sock, proto, client, server, sessionno):
        return server


class ThrottledServer(tcp.Server):
    """A Server whose sending rate is limited by a token bucket.
    """
    def __init__(self, bucket, *a, **kw):
        tcp.Server.__init__(self, *a, **kw)
        self.bucket = bucket
        bucket._refcount += 1

    def writeSomeData(self, data):
        # FIXME: I am afraid this is the wrong thing to do if the transport
        # has been asked to optimize for cost or throughput instead of latency.
        # This seems like it could generate lots of little packets, which would
        # incur a big overhead.  Do we need to slip another buffer layer below
        # this one, which buffers MTU bytes before it actually writes anything
        # to the wire?
        amount = self.bucket.add(len(data))
        return tcp.Server.writeSomeData(self, data[:amount])

    def connectionLost(self, reason):
        self.bucket._refcount -= 1
        return tcp.Server.connectionLost(self, reason)

class ThrottledServerFactory:
    """I make transports with buckets.

    Assign an instance of me to L{tcp.Port.transport}.
    """
    transport = ThrottledServer
    def __init__(self, filter):
        """Initialize.

        @param filter: The filter I will get my buckets from.
        @type filter: L{IBucketFilter}
        """
        self.filter = filter

    def __call__(self, *a, **kw):
        bucket = self.filter.getBucketFor(*a, **kw)
        return self.transport(bucket, *a, **kw)
