from twisted.trial import unittest
from twisted.internet import reactor, defer

class StacklessTester(unittest.TestCase):

    def testTakesContinuation(self):
        l = []

        def testIt():
            def contyFunc(cont, a):
                "I should be equivalent to a `return a + 1'"
                cont(a+1)
            contyFunc = threadless.takesContinuation(contyFunc)
            l.append(contyFunc(2))

        threadless.theScheduler.callInTasklet(testIt)
        while not l:
            reactor.iterate()
        self.assertEquals(l[0], 3)

    def testDeferredBlocking(self):
        d = defer.Deferred()
        l = []
        reactor.callLater(0.2, d.callback, "hi")

        def waiter():
            l.append(threadless.blockOn(d))

        threadless.theScheduler.callInTasklet(waiter)
        while not l:
            reactor.iterate()
        self.assertEquals(l[0], "hi")

try:
    import stackless
    import threadless
except ImportError:
    StacklessTester.skip = "This test requires Stackless Python"
