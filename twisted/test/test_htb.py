# -*- Python -*-

__version__ = '$Revision: 1.3 $'[11:-2]

from twisted.trial import unittest
from twisted.protocols import htb

class DummyClock:
    time = 0
    def set(self, when):
        self.time = when

    def __call__(self):
        return self.time

class SomeBucket(htb.Bucket):
    maxburst = 100
    rate = 2

class TestBucketBase(unittest.TestCase):
    def setUp(self):
        self._realTimeFunc = htb.time
        self.clock = DummyClock()
        htb.time = self.clock

    def tearDown(self):
        htb.time = self._realTimeFunc

class TestBucket(TestBucketBase):
    def testBucketSize(self):
        """Testing the size of the bucket."""
        b = SomeBucket()
        fit = b.add(1000)
        self.failUnlessEqual(100, fit)

    def testBucketDrian(self):
        """Testing the bucket's drain rate."""
        b = SomeBucket()
        fit = b.add(1000)
        self.clock.set(10)
        fit = b.add(1000)
        self.failUnlessEqual(20, fit)

class TestBucketNesting(TestBucketBase):
    def setUp(self):
        TestBucketBase.setUp(self)
        self.parent = SomeBucket()
        self.child1 = SomeBucket(self.parent)
        self.child2 = SomeBucket(self.parent)

    def testBucketParentSize(self):
        # Use up most of the parent bucket.
        self.child1.add(90)
        fit = self.child2.add(90)
        self.failUnlessEqual(10, fit)

    def testBucketParentRate(self):
        # Make the parent bucket drain slower.
        self.parent.rate = 1
        # Fill both child1 and parent.
        self.child1.add(100)
        self.clock.set(10)
        fit = self.child1.add(100)
        # How much room was there?  The child bucket would have had 20,
        # but the parent bucket only ten (so no, it wouldn't make too much
        # sense to have a child bucket draining faster than its parent in a real
        # application.)
        self.failUnlessEqual(10, fit)


# TODO: Test the Transport stuff?

from test_pcp import DummyConsumer

class ConsumerShaperTest(TestBucketBase):
    def setUp(self):
        TestBucketBase.setUp(self)
        self.underlying = DummyConsumer()
        self.bucket = SomeBucket()
        self.shaped = htb.ShapedConsumer(self.underlying, self.bucket)

    def testRate(self):
        # Start off with a full bucket, so the burst-size dosen't factor in
        # to the calculations.
        delta_t = 10
        self.bucket.add(100)
        self.shaped.write("x" * 100)
        self.clock.set(delta_t)
        self.shaped.resumeProducing()
        self.failUnlessEqual(len(self.underlying.getvalue()),
                             delta_t * self.bucket.rate)

    def testBucketRefs(self):
        self.failUnlessEqual(self.bucket._refcount, 1)
        self.shaped.stopProducing()
        self.failUnlessEqual(self.bucket._refcount, 0)
