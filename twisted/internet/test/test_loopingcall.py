from twisted.internet import defer, task
from twisted.trial.unittest import TestCase



class TestLoopingCall(TestCase):
    
    def test_deferredRentry(self):
        l = [defer.Deferred(), defer.Deferred()]
        firstCallResult = []
        secondCallResult = []
        l2 = l[:]

        c = task.LoopingCall(l.pop)
        clock = task.Clock()
        c.clock = clock
        expectResult = 'expected first call result'
        def appendToFirst(result):
            firstCallResult.append(result)
            return expectResult
        firstCall = c.start(1).addCallback(appendToFirst)
        c.clock.advance(1)
        self.assertEquals(l, l2[:1])
        c.stop()
        c.start(1).addCallback(secondCallResult.append)
        firstCallAfterSecond = []
        firstCall.addCallback(firstCallAfterSecond.append)
        c.clock.advance(1)
        self.assertEquals(l, l2[:1])
        l2[1].callback("Hello!")
        c.stop()
        self.assertEquals(firstCallResult, [c])
        self.assertEquals(secondCallResult, [c])
        self.assertEquals(firstCallAfterSecond, [expectResult])
