import time

from twisted.trial import unittest
from twisted.internet import reactor, defer

class StacklessTester(unittest.TestCase):

    def testTakesContinuation(self):
        self.expectedAssertions = 1

        def waiter():
            def contyFunc(cont, a):
                "I should be equivalent to a `return a + 1'"
                cont(a+1)
            contyFunc = threadless.takesContinuation(contyFunc)
            self.assertEquals(contyFunc(2), 3)

        threadless.theScheduler.callInTasklet(waiter)
        self.runReactor(5)

    def testDeferredBlocking(self):
        self.expectedAssertions = 1
        
        d = defer.Deferred()
        reactor.callLater(0.2, d.callback, "hi")

        def waiter():
            self.assertEquals(threadless.blockOn(d), "hi")

        threadless.theScheduler.callInTasklet(waiter)
        self.runReactor(0.3, seconds=True)

    def testDeferredErring(self):
        self.expectedAssertions = 1
        
        class MyExc(Exception):
            pass

        d = defer.Deferred()
        reactor.callLater(0.2, d.errback, MyExc())

        def waiter():
            self.assertRaises(MyExc, threadless.blockOn, d)

        threadless.theScheduler.callInTasklet(waiter)
        self.runReactor(0.3, seconds=True)

    def testSleep(self):
        self.expectedAssertions = 1
        def waiter():
            now = time.time()
            threadless.sleep(0.2)
            self.assert_(time.time() - now > 0.1)
        threadless.theScheduler.callInTasklet(waiter)
        self.runReactor(1, seconds=True)


    def testImmediateReturn(self):
        """
        This test probably isn't that useful...
        """
        self.expectedAssertions = 1
        def harness():
            def immediatelyReturn(cont):
                cont(1)
            immediatelyReturn = threadless.takesContinuation(immediatelyReturn)
            self.assert_(True)
        threadless.theScheduler.callInTasklet(harness)
        self.runReactor(5)


try:
    import stackless
    import threadless
except ImportError:
    StacklessTester.skip = "This test requires Stackless Python"
