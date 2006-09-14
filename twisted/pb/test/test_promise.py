
from twisted.trial import unittest

from twisted.python import failure
from twisted.internet import defer, reactor
from twisted.pb.promise import Promise, when

class Target:
    def __init__(self):
        self.calls = []
    def one(self, a):
        self.calls.append(("one", a))
        return a+1
    def two(self, a, b=2, **kwargs):
        self.calls.append(("two", a, b, kwargs))
    def three(self, c, *args):
        self.calls.append(("three", c, args))
        return self.d
    def four(self, newtarget, arg):
        return newtarget.one(arg)

class TestPromise(unittest.TestCase):
    def testWhen(self):
        d0 = defer.Deferred()
        p = Promise(d0)
        d = when(p)
        results = []
        d.addCallback(results.append)
        self.failUnlessEqual(results, [])
        d0.callback(42)
        self.failUnlessEqual(results, [42])

    def test1(self):
        t = Target()
        d = defer.Deferred()
        p = Promise(d)

        p.one(12)
        self.failUnlessEqual(t.calls, [])
        d.callback(t)
        self.failUnlessEqual(t.calls, [("one", 12)])

    def test2(self):
        t = Target()
        t.d = defer.Deferred()
        d = defer.Deferred()
        p = Promise(d)

        p1 = p.one(12)
        p.two(b=4, a=7, c=92)
        p3 = p.three(4, 5, 6)
        self.failUnlessEqual(t.calls, [])

        results0a = []
        d0a = when(p)
        d0a.addCallback(self._test2_0a, results0a)
        # the promise is not yet resolved, so this should not fire yet
        self.failUnlessEqual(results0a, [])

        d.callback(t)
        self.failUnlessEqual(t.calls, [("one", 12),
                                       ("two", 7, 4, {'c':92}),
                                       ("three", 4, (5,6)),
                                       ])
        self.failUnlessEqual(results0a, [t])

        results0b = []
        d0b = when(p)
        d0b.addCallback(self._test2_0b, t, results0b)
        # because the promise has already been fulfilled, this should fire
        # right away
        self.failUnlessEqual(results0b, [t])

        d1 = when(p1)
        d1.addCallback(self._test2_1)

        # p3 shouldn't fire until t.d is fired
        d3 = when(p3)
        d3.addCallback(self._test2_3)
        reactor.callLater(0, t.d.callback, 35)
        return defer.DeferredList([d0a, d0b, d1, d3])

    def _test2_0a(self, res, results):
        results.append(res)

    def _test2_0b(self, res, t, results):
        self.failUnlessIdentical(res, t)
        results.append(res)

    def _test2_1(self, res):
        self.failUnlessEqual(res, 13)
    
    def _test2_3(self, res):
        self.failUnlessEqual(res, 35)

    def testFailure(self):
        d0 = defer.Deferred()
        p = Promise(d0)

        wresults = ([],[])
        dw = when(p)
        dw.addCallbacks(wresults[0].append, wresults[1].append)

        cresults = ([],[])
        p2 = p.call(12)
        d2 = when(p2)
        d2.addCallbacks(cresults[0].append, cresults[1].append)

        f = failure.Failure(IndexError())
        d0.errback(f)

        self.failUnlessEqual(wresults, ([],[f]))
        self.failUnlessEqual(cresults, ([],[f])) # TODO: really?
