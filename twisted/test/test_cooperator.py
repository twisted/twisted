
from twisted.internet import reactor, defer, task
from twisted.trial import unittest


class TestCooperator(unittest.TestCase):
    RESULT = 'done'

    def ebIter(self, err):
        err.trap(task.SchedulerStopped)
        return self.RESULT


    def cbIter(self, ign):
        self.fail()


    def testStoppedRejectsNewTasks(self):
        """
        Test that Cooperators refuse new tasks when they have been stopped.
        """
        def testwith(stuff):
            c = task.Cooperator()
            c.stop()
            d = c.coiterate(iter(()), stuff)
            d.addCallback(self.cbIter)
            d.addErrback(self.ebIter)
            return d.addCallback(lambda result:
                                 self.assertEquals(result, self.RESULT))
        return testwith(None).addCallback(lambda ign: testwith(defer.Deferred()))


    def testStopRunning(self):
        """
        Test that a running iterator will not run to completion when the
        cooperator is stopped.
        """
        c = task.Cooperator()
        def myiter():
            for myiter.value in range(3):
                yield myiter.value
        myiter.value = -1
        d = c.coiterate(myiter())
        d.addCallback(self.cbIter)
        d.addErrback(self.ebIter)
        c.stop()
        def doasserts(result):
            self.assertEquals(result, self.RESULT)
            self.assertEquals(myiter.value, -1)
        d.addCallback(doasserts)
        return d


    def testStopOutstanding(self):
        """
        Test that a running iterator paused on a third-party Deferred will
        properly stop when .stop() is called.
        """
        testControlD = defer.Deferred()
        outstandingD = defer.Deferred()
        def myiter():
            reactor.callLater(0, testControlD.callback, None)
            yield outstandingD
            self.fail()
        c = task.Cooperator()
        d = c.coiterate(myiter())
        def stopAndGo(ign):
            c.stop()
            outstandingD.callback('arglebargle')

        testControlD.addCallback(stopAndGo)
        d.addCallback(self.cbIter)
        d.addErrback(self.ebIter)

        return d.addCallback(lambda result: self.assertEquals(result, self.RESULT))


    def testUnexpectedError(self):
        c = task.Cooperator()
        def myiter():
            if 0:
                yield None
            else:
                raise RuntimeError()
        d = c.coiterate(myiter())
        return self.assertFailure(d, RuntimeError)


    def testUnexpectedErrorActuallyLater(self):
        def myiter():
            D = defer.Deferred()
            reactor.callLater(0, D.errback, RuntimeError())
            yield D

        c = task.Cooperator()
        d = c.coiterate(myiter())
        return self.assertFailure(d, RuntimeError)


    def testUnexpectedErrorNotActuallyLater(self):
        def myiter():
            yield defer.fail(RuntimeError())

        c = task.Cooperator()
        d = c.coiterate(myiter())
        return self.assertFailure(d, RuntimeError)


    def testCooperation(self):
        L = []
        def myiter(things):
            for th in things:
                L.append(th)
                yield None

        groupsOfThings = ['abc', (1, 2, 3), 'def', (4, 5, 6)]

        c = task.Cooperator()
        tasks = []
        for stuff in groupsOfThings:
            tasks.append(c.coiterate(myiter(stuff)))

        return defer.DeferredList(tasks).addCallback(
            lambda ign: self.assertEquals(tuple(L), sum(zip(*groupsOfThings), ())))


    def testResourceExhaustion(self):
        output = []
        def myiter():
            for i in range(100):
                output.append(i)
                if i == 9:
                    _TPF.stopped = True
                yield i

        class _TPF:
            stopped = False
            def __call__(self):
                return self.stopped

        c = task.Cooperator(terminationPredicateFactory=_TPF)
        c.coiterate(myiter()).addErrback(self.ebIter)
        c._delayedCall.cancel()
        # testing a private method because only the test case will ever care
        # about this, so we have to carefully clean up after ourselves.
        c._tick()
        c.stop()
        self.failUnless(_TPF.stopped)
        self.assertEquals(output, range(10))


    def testCallbackReCoiterate(self):
        """
        If a callback to a deferred returned by coiterate calls coiterate on
        the same Cooperator, we should make sure to only do the minimal amount
        of scheduling work.  (This test was added to demonstrate a specific bug
        that was found while writing the scheduler.)
        """
        calls = []

        class FakeCall:
            def __init__(self, func):
                self.func = func

            def __repr__(self):
                return '<FakeCall %r>' % (self.func,)

        def sched(f):
            self.failIf(calls, repr(calls))
            calls.append(FakeCall(f))
            return calls[-1]

        c = task.Cooperator(scheduler=sched, terminationPredicateFactory=lambda: lambda: True)
        d = c.coiterate(iter(()))

        done = []
        def anotherTask(ign):
            c.coiterate(iter(())).addBoth(done.append)

        d.addCallback(anotherTask)

        work = 0
        while not done:
            work += 1
            while calls:
                calls.pop(0).func()
                work += 1
            if work > 50:
                self.fail("Cooperator took too long")
