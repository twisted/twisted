from twisted.internet import defer, task
from twisted.trial.unittest import TestCase



class TestLoopingCall(TestCase):
    
    def test_deferredRentry(self):
        self.count = 0
        
        """
        def loopMe():
            print 'loop'
            self.count += 1

            d = defer.Deferred()

            if self.count < 3:
                clock.callLater(.33, c.stop)
            if self.count < 2:
                clock.callLater(.66, c.start, 0)

            clock.callLater(1, d.callback, None)
            return d
        """
        
        l = [defer.Deferred(), defer.Deferred()]
        
        l2 = l[:]
        
        c = task.LoopingCall(l.pop)
        clock = task.Clock()
        c.clock = clock
        c.start(1)
        c.clock.advance(1)
        self.assertEquals(l, l2[:1])
        c.stop()
        c.start(1)
        c.clock.advance(1)
        self.assertEquals(l, l2[:1])
