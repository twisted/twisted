
from twisted.trial import unittest
from twisted.internet import reactor, interfaces
from twisted.python import log

class Resolve(unittest.TestCase):
    def testResolve(self):
        # sometimes the newpb connection/negotiation tests all fail. I have a
        # hunch that this is because some earlier test has somehow killed off
        # the threadpool, so reactor.resolve() never completes. This test is
        # intended as instrumentation to prove this theory: if all the newpb
        # tests fail, and this one does to, then the problem is with the
        # threadpool and not in newpb.
        self._dumpThreadpoolInfo()
        log.msg("starting reactor.resolve()")
        d = reactor.resolve("localhost")
        self.timer = reactor.callLater(30, self._resolveTimedOut)
        d.addBoth(self._resolved)
        return d
    testResolve.timeout = 60

    def _resolved(self, res):
        log.msg("reactor.resolve() completed")
        if self.timer:
            self.timer.cancel()
        self._dumpThreadpoolInfo()
        return res

    def _resolveTimedOut(self):
        log.msg("reactor.resolve() did not complete within 30 seconds")
        self.timer = None
        self._dumpThreadpoolInfo()

    def _dumpThreadpoolInfo(self):
        log.msg("dumping existing threadpool state")
        treactor = interfaces.IReactorThreads(reactor, None)
        if treactor is not None:
            if hasattr(treactor, "threadpool"):
                tp = treactor.threadpool
                log.msg("threadpool object: %s" % (tp,))
                if tp:
                    log.msg("threadpool contents: %s" % tp.__dict__)
        log.msg("done dumping any existing threadpool state")
