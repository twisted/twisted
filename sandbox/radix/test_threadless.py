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

try:
    import stackless
    import threadless
except ImportError:
    StacklessTester.skip = "This test requires Stackless Python"
