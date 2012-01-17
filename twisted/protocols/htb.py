# -*- test-case-name: twisted.test.test_htb -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Hierarchical Token Bucket traffic shaping.

Patterned after U{Martin Devera's Hierarchical Token Bucket traffic
shaper for the Linux kernel<http://luxik.cdi.cz/~devik/qos/htb/>}.

@seealso: U{HTB Linux queuing discipline manual - user guide
  <http://luxik.cdi.cz/~devik/qos/htb/manual/userg.htm>}
@seealso: U{Token Bucket Filter in Linux Advanced Routing & Traffic Control
    HOWTO<http://lartc.org/howto/lartc.qdisc.classless.html#AEN682>}
@author: Kevin Turner
"""

from __future__ import nested_scopes

__version__ = '$Revision: 1.5 $'[11:-2]


# TODO: Investigate whether we should be using os.times()[-1] instead of
# time.time.  time.time, it has been pointed out, can go backwards.  Is
# the same true of os.times?
from time import time
from zope.interface import implements, Interface

from twisted.protocols import pcp


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
        """
        Let some of the bucket drain.

        How much of the bucket drains depends on how long it has been
        since I was last called.

        @returns: C{True} if the bucket is empty after this drip.
        @returntype: bool
        """
        if self.parentBucket is not None:
            self.parentBucket.drip()

        if self.rate is None:
            self.content = 0
        else:
            now = time()
            deltaT = now - self.lastDrip
            self.content = long(max(0, self.content - deltaT * self.rate))
            self.lastDrip = now
        return self.content == 0


class IBucketFilter(Interface):
    def getBucketFor(*somethings, **some_kw):
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

    implements(IBucketFilter)

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

    def getBucketKey(self, transport):
        return transport.getPeer()[1]


class FilterByServer(HierarchicalBucketFilter):
    """A bucket filter with a bucket for each service.
    """
    sweepInterval = None

    def getBucketKey(self, transport):
        return transport.getHost()[2]


class ShapedConsumer(pcp.ProducerConsumerProxy):
    """I wrap a Consumer and shape the rate at which it receives data.
    """
    # Providing a Pull interface means I don't have to try to schedule
    # traffic with callLaters.
    iAmStreaming = False

    def __init__(self, consumer, bucket):
        pcp.ProducerConsumerProxy.__init__(self, consumer)
        self.bucket = bucket
        self.bucket._refcount += 1

    def _writeSomeData(self, data):
        # In practice, this actually results in obscene amounts of
        # overhead, as a result of generating lots and lots of packets
        # with twelve-byte payloads.  We may need to do a version of
        # this with scheduled writes after all.
        amount = self.bucket.add(len(data))
        return pcp.ProducerConsumerProxy._writeSomeData(self, data[:amount])

    def stopProducing(self):
        pcp.ProducerConsumerProxy.stopProducing(self)
        self.bucket._refcount -= 1


class ShapedTransport(ShapedConsumer):
    """I wrap a Transport and shape the rate at which it receives data.

    I am a L{ShapedConsumer} with a little bit of magic to provide for
    the case where the consumer I wrap is also a Transport and people
    will be attempting to access attributes I do not proxy as a
    Consumer (e.g. loseConnection).
    """
    # Ugh.  We only wanted to filter IConsumer, not ITransport.

    iAmStreaming = False
    def __getattr__(self, name):
        # Because people will be doing things like .getPeer and
        # .loseConnection on me.
        return getattr(self.consumer, name)


class ShapedProtocolFactory:
    """I dispense Protocols with traffic shaping on their transports.

    Usage::

        myserver = SomeFactory()
        myserver.protocol = ShapedProtocolFactory(myserver.protocol,
                                                  bucketFilter)

    Where SomeServerFactory is a L{twisted.internet.protocol.Factory}, and
    bucketFilter is an instance of L{HierarchicalBucketFilter}.
    """
    def __init__(self, protoClass, bucketFilter):
        """Tell me what to wrap and where to get buckets.

        @param protoClass: The class of Protocol I will generate
          wrapped instances of.
        @type protoClass: L{Protocol<twisted.internet.interfaces.IProtocol>}
          class
        @param bucketFilter: The filter which will determine how
          traffic is shaped.
        @type bucketFilter: L{HierarchicalBucketFilter}.
        """
        # More precisely, protoClass can be any callable that will return
        # instances of something that implements IProtocol.
        self.protocol = protoClass
        self.bucketFilter = bucketFilter

    def __call__(self, *a, **kw):
        """Make a Protocol instance with a shaped transport.

        Any parameters will be passed on to the protocol's initializer.

        @returns: a Protocol instance with a L{ShapedTransport}.
        """
        proto = self.protocol(*a, **kw)
        origMakeConnection = proto.makeConnection
        def makeConnection(transport):
            bucket = self.bucketFilter.getBucketFor(transport)
            shapedTransport = ShapedTransport(transport, bucket)
            return origMakeConnection(shapedTransport)
        proto.makeConnection = makeConnection
        return proto
