# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from twisted.trial import unittest
from twisted.internet import reactor, protocol, error, app
from twisted.internet.defer import SUCCESS, FAILURE, Deferred, succeed, fail
from twisted.python import threadable, log
threadable.init(1)

import sys
import time
import threading
import types


class SystemEventTestCase(unittest.TestCase):
    def setUp(self):
        self.triggers = []
    def addTrigger(self, event, phase, func):
        t = reactor.addSystemEventTrigger(event, phase, func)
        self.triggers.append(t)
        return t
    def removeTrigger(self, trigger):
        reactor.removeSystemEventTrigger(trigger)
        self.triggers.remove(trigger)
    def tearDown(self):
        for t in self.triggers:
            try:
                reactor.removeSystemEventTrigger(t)
            except:
                pass
    
    def testTriggerSystemEvent1(self):
        l = []
        l2 = []
        d = Deferred()
        d2 = Deferred()
        def _returnDeferred(d=d):
            return d
        def _returnDeferred2(d2=d2):
            return d2
        def _appendToList(l=l):
            l.append(1)
        def _appendToList2(l2=l2):
            l2.append(1)
        ##         d.addCallback(lambda x: sys.stdout.write("firing d\n"))
        ##         d2.addCallback(lambda x: sys.stdout.write("firing d2\n"))
        r = reactor

        self.addTrigger("before", "test", _appendToList)
        self.addTrigger("during", "test", _appendToList)
        self.addTrigger("after", "test", _appendToList)
        self.assertEquals(len(l), 0, "Nothing happened yet.")
        r.fireSystemEvent("test")
        r.iterate()
        self.assertEquals(len(l), 3, "Should have filled the list.")

        l[:]=[]
        self.addTrigger("before", "defer", _returnDeferred)
        self.addTrigger("before", "defer", _returnDeferred2)
        self.addTrigger("during", "defer", _appendToList)
        self.addTrigger("after", "defer", _appendToList)
        r.fireSystemEvent("defer")
        self.assertEquals(len(l), 0, "Event should not have fired yet.")
        d.callback(None)
        self.assertEquals(len(l), 0, "Event still should not have fired yet.")
        d2.callback(None)
        self.assertEquals(len(l), 2)

        l[:]=[]
        a = self.addTrigger("before", "remove", _appendToList)
        b = self.addTrigger("before", "remove", _appendToList2)
        self.removeTrigger(b)
        r.fireSystemEvent("remove")
        self.assertEquals(len(l), 1)
        self.assertEquals(len(l2), 0)

    def testTriggerSystemEvent2(self):
        # one of the "before" trigger functions returns a deferred. A later
        # "before" trigger fires the deferred. A third before runs. Then a
        # "during" should be run. One of the failure modes for the old
        # cReactor code is to start the "during" as soon as the deferred
        # fires, rather than waiting for the "before" phase to be finished
        l = []
        d = Deferred()
        d2 = Deferred()
        def _returnDeferred(d=d):
            return d
        def _fireDeferred(d=d):
            d.callback(None)
        def _returnDeferred2(d2=d2):
            return d2
        def _appendToList(l=l):
            l.append(1)
        r = reactor
        # to test this properly, the triggers must fire in this sequence:
        # _returnDeferred, _fireDeferred, _returnDeferred2 . cReactor happens
        # to run triggers in the order in which they were added.
        self.addTrigger("before", "defer2", _returnDeferred)
        self.addTrigger("before", "defer2", _fireDeferred)
        self.addTrigger("before", "defer2", _returnDeferred2)
        self.addTrigger("during", "defer2", _appendToList)
        self.addTrigger("after", "defer2", _appendToList)
        r.fireSystemEvent("defer2")
        self.assertEquals(len(l), 0, "Event should not have fired yet.")
        d2.callback(None)
        self.assertEquals(len(l), 2)

    def testTriggerSystemEvent3(self):
        # make sure reactor can survive the loss of an event type while
        # waiting for a before-trigger's Deferred to fire
        l = []
        d = Deferred()
        d2 = Deferred()
        def _returnDeferred(d=d):
            return d
        def _appendToList(l=l):
            l.append(1)
        def _ignore(failure):
            return None
        r = reactor
        b1 = self.addTrigger("before", "defer3", _returnDeferred)
        b2 = self.addTrigger("after", "defer3", _appendToList)
        r.fireSystemEvent("defer3")
        self.assertEquals(len(l), 0, "Event should not have fired yet.")
        self.removeTrigger(b1)
        self.removeTrigger(b2)
        try:
            d.callback(None) # cReactor gives errback to deferred
        except ValueError:
            pass
        self.assertEquals(len(l), 0)
        d.addErrback(_ignore)

    def testTriggerSystemEvent4(self):
        # make sure interleaved event types do not interfere with each other.
        # Old cReactor code had a single defer_list for all event types.
        l = []
        l2 = []
        d = Deferred()
        d2 = Deferred()
        def _returnDeferred(d=d):
            return d
        def _returnDeferred2(d2=d2):
            return d2
        def _appendToList(l=l):
            l.append(1)
        def _appendToList2(l2=l2):
            l2.append(1)
        r = reactor
        self.addTrigger("before", "event1", _returnDeferred)
        self.addTrigger("after", "event1", _appendToList)
        self.addTrigger("before", "event2", _returnDeferred2)
        self.addTrigger("after", "event2", _appendToList2)
        r.fireSystemEvent("event1")
        # event1 should be waiting on deferred 'd'
        r.fireSystemEvent("event2")
        # event2 should be waiting on deferred 'd2'
        self.assertEquals(len(l), 0, "Event should not have fired yet.")
        self.assertEquals(len(l2), 0, "Event should not have fired yet.")
        d.callback(None)
        # event1 should run "during" and "after" stages
        # event2 should still be waiting on d2
        self.assertEquals(len(l), 1)
        self.assertEquals(len(l2), 0)
        d2.callback(None)
        # event2 should run "during" and "after" stages
        self.assertEquals(len(l), 1)
        self.assertEquals(len(l2), 1)

    def testTriggerSystemEvent5(self):
        # make sure the reactor can handle attempts to remove bogus triggers
        l = []
        def _appendToList(l=l):
            l.append(1)
        r = reactor
        b = self.addTrigger("after", "event1", _appendToList)
        self.removeTrigger(b)
        if type(b) == types.IntType:
            bogus = b + 40
            self.failUnlessRaises(ValueError,
                                  r.removeSystemEventTrigger, bogus)
        self.failUnlessRaises(TypeError,
                              r.removeSystemEventTrigger, None)


class InterfaceTestCase(unittest.TestCase):

    _called = 0

    def _callback(self, x, **d):
        """Callback for testCallLater"""
        self.assertEquals(x, 1)
        self.assertEquals(d, {'a': 1})
        self._called = 1
        self._calledTime = time.time()

    def testCallLater(self):
        # add and remove a callback
        def bad():
            raise RuntimeError, "this shouldn't have been called"
        i = reactor.callLater(0.1, bad)
        i.cancel()

        self.assertRaises(error.AlreadyCancelled, i.cancel)

        start = time.time()
        i = reactor.callLater(0.5, self._callback, 1, a=1)

        while time.time() - start < 0.6:
            reactor.iterate(0.01)

        self.assertEquals(self._called, 1)
        self.assert_( 0 < self._calledTime - start - 0.5 < 0.2 )
        self.assertRaises(error.AlreadyCalled, i.cancel)

        del self._called
        del self._calledTime

    def _resetcallback(self):
        self._resetcallbackTime = time.time()
    
    def _delaycallback(self):
        self._delaycallbackTime = time.time()
        
    def testCallLaterDelayAndReset(self):
        self._resetcallbackTime = None
        self._delaycallbackTime = None
        ireset = reactor.callLater(0.5, self._resetcallback)
        idelay = reactor.callLater(0.5, self._delaycallback)
        start = time.time()
        # chug a little before delaying
        while time.time() - start < 0.2:
            reactor.iterate(0.01)
        ireset.reset(0.3) # move expiration from 0.5 to (now)0.2+0.3=0.5
        idelay.delay(0.3) # move expiration from 0.5 to (orig)0.5+0.3=0.8
        # both should be called sometime during this
        while time.time() - start < 0.9:
            reactor.iterate(0.01)
        self.assert_(-0.1 < self._resetcallbackTime - start - 0.5 < 0.1)
        self.assert_(-0.1 < self._delaycallbackTime - start - 0.8 < 0.1)

        del self._resetcallbackTime
        del self._delaycallbackTime

    def testWakeUp(self):
        def wake(reactor=reactor):
            time.sleep(0.5)
            reactor.wakeUp()
        start = time.time()
        t = threading.Thread(target=wake).start()
        reactor.iterate(5)
        self.assert_( abs(time.time() - start - 0.5) < 0.5 )


class ReactorCoreTestCase(unittest.TestCase):
    def setUp(self):
        self.triggers = []
        self.timers = []
    def addTrigger(self, event, phase, func):
        t = reactor.addSystemEventTrigger(event, phase, func)
        self.triggers.append(t)
        return t
    def removeTrigger(self, trigger):
        reactor.removeSystemEventTrigger(trigger)
        self.triggers.remove(trigger)
    def addTimer(self, when, func):
        t = reactor.callLater(when, func)
        self.timers.append(t)
        return t
    def removeTimer(self, timer):
        try:
            timer.cancel()
        except error.AlreadyCalled:
            pass
        self.timers.remove(timer)
        
    def tearDown(self):
        for t in self.triggers:
            try:
                reactor.removeSystemEventTrigger(t)
            except:
                pass
    def crash(self):
        reactor.crash()
    def stop(self):
        reactor.stop()
        
    def testIterate(self):
        reactor.callLater(0.1, self.stop)
        reactor.run() # returns once .stop is called
        reactor.callLater(0.1, self.stop)
        reactor.run() # returns once .stop is called

    def timeout(self):
        print "test timed out"
        self.problem = 1
        self.fail("test timed out")
    def count(self):
        self.counter += 1

    def testStop(self):
        # make sure shutdown triggers are run when the reactor is stopped
        self.counter = 0
        self.problem = 0
        self.addTrigger("before", "shutdown", self.count)
        self.addTimer(0.1, self.stop)
        self.addTimer(5, self.timeout)
        reactor.run()
        self.failUnless(self.counter == 1,
                        "reactor.stop didn't invoke shutdown triggers")
        self.failIf(self.problem, "the test timed out")

    def testCrash(self):
        self.counter = 0
        self.problem = 0
        self.addTrigger("before", "shutdown", self.count)
        # reactor.crash called from an "after-startup" trigger is too early
        # for the gtkreactor: gtk_mainloop is not yet running. Same is true
        # when called with reactor.callLater(0). Must be >0 seconds in the
        # future to let gtk_mainloop start first.
        self.addTimer(0.1, self.crash)
        self.addTimer(5, self.timeout)
        reactor.run()
        # this will fire reactor.crash, which ought to exit .run without
        # running the event triggers
        self.failUnless(self.counter == 0,
                        "reactor.crash invoked shutdown triggers, "
                        "but it isn't supposed to")
        self.failIf(self.problem, "the test timed out")
        
        
        
class DelayedTestCase(unittest.TestCase):
    def setUp(self):
        self.finished = 0
        self.counter = 0
        self.timers = {}
        # ick. Sometimes there are magic timers already running:
        # popsicle.Freezer.tick . Kill off all such timers now so they won't
        # interfere with the test. Of course, this kind of requires that
        # getDelayedCalls already works, so certain failure modes won't be
        # noticed.
        if not hasattr(reactor, "getDelayedCalls"):
            return
        for t in reactor.getDelayedCalls():
            t.cancel()
        reactor.iterate() # flush timers
    def tearDown(self):
        for t in self.timers.values():
            t.cancel()

    def checkTimers(self):
        l1 = self.timers.values()
        l1.sort()
        l2 = list(reactor.getDelayedCalls())
        l2.sort()

        # getDelayedCalls makes no promises about the order of the
        # delayedCalls it returns, but they should be the same objects as
        # we've recorded in self.timers. We sort both lists to make them
        # easier to compare.

        if l1 != l2:
            print "\nself.timers:"
            for i in l1: print " %s" % i
            print "getDelayedCalls():"
            for i in l2: print " %s" % i
            self.finished = 1
            self.fail("self.timers != reactor.getDelayedCalls()")

    def callback(self, tag):
        del self.timers[tag]
        self.checkTimers()

    def addCallback(self, tag):
        self.callback(tag)
        self.addTimer(15, self.callback)

    def done(self, tag):
        self.finished = 1
        self.callback(tag)

    def failsafe(self, tag):
        self.finished = 1
        self.fail("timeout")
        
    def addTimer(self, when, callback):
        self.timers[self.counter] = reactor.callLater(when * 0.01, callback,
                                                      self.counter)
        self.counter += 1
        self.checkTimers()
        
    def testGetDelayedCalls(self):
        if not hasattr(reactor, "getDelayedCalls"):
            return
        # This is not a race because we don't do anything which might call
        # the reactor until we have all the timers set up. If we did, this
        # test might fail on slow systems.
        self.checkTimers()
        self.addTimer(35, self.done)
        self.addTimer(20, self.callback)
        self.addTimer(30, self.callback)
        which = self.counter
        self.addTimer(30, self.callback)
        self.addTimer(25, self.addCallback)
        self.addTimer(25, self.callback)

        self.addTimer(50, self.failsafe)
        
        self.timers[which].cancel()
        del self.timers[which]
        self.checkTimers()

        while not self.finished:
            reactor.iterate(0.01)
        self.checkTimers()
        

class Counter:
    index = 0

    def add(self):
        self.index = self.index + 1


class Order:

    stage = 0

    def a(self):
        if self.stage != 0: raise RuntimeError
        self.stage = 1

    def b(self):
        if self.stage != 1: raise RuntimeError
        self.stage = 2

    def c(self):
        if self.stage != 2: raise RuntimeError
        self.stage = 3


class ThreadOrder(threading.Thread, Order):

    def run(self):
        self.schedule(self.a)
        self.schedule(self.b)
        self.schedule(self.c)


class callFromThreadTestCase(unittest.TestCase):
    """Task scheduling from threads tests."""

    def schedule(self, *args, **kwargs):
        """Override in subclasses."""
        apply(reactor.callFromThread, args, kwargs)

    def testScheduling(self):
        c = Counter()
        for i in range(100):
            self.schedule(c.add)
        for i in range(100):
            reactor.iterate()
        self.assertEquals(c.index, 100)

    def testCorrectOrder(self):
        o = Order()
        self.schedule(o.a)
        self.schedule(o.b)
        self.schedule(o.c)
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()
        self.assertEquals(o.stage, 3)

    def testNotRunAtOnce(self):
        c = Counter()
        self.schedule(c.add)
        # scheduled tasks should not be run at once:
        self.assertEquals(c.index, 0)
        reactor.iterate()
        self.assertEquals(c.index, 1)


class MyProtocol(protocol.Protocol):
    """Sample protocol."""

class MyFactory(protocol.Factory):
    """Sample factory."""

    protocol = MyProtocol


class ProtocolTestCase(unittest.TestCase):

    def testFactory(self):
        factory = MyFactory()
        protocol = factory.buildProtocol(None)
        self.assertEquals(protocol.factory, factory)
        self.assert_( isinstance(protocol, factory.protocol) )


class StopError(Exception): pass

class StoppingService(app.ApplicationService):

    def __init__(self, name, succeed):
        app.ApplicationService.__init__(self, name)
        self.succeed = succeed

    def stopService(self):
        if self.succeed:
            return succeed("yay!")
        else:
            return fail(StopError('boo'))

class StoppingServiceII(app.ApplicationService):
    def stopService(self):
        # The default stopService returns None.
        return None # return app.ApplicationService.stopService(self)

class MultiServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.callbackRan = 0

    def testDeferredStopService(self):
        ms = app.MultiService("MultiService")
        self.s1 = StoppingService("testService", 0)
        self.s2 = StoppingService("testService2", 1)
        ms.addService(self.s1)
        ms.addService(self.s2)
        ms.stopService().addCallback(self.woohoo)

    def woohoo(self, res):
        self.callbackRan = 1
        self.assertEqual(res[self.s1][0], 0)
        self.assertEqual(res[self.s2][0], 1)

    def testStopServiceNone(self):
        """MultiService.stopService returns Deferred when service returns None.
        """
        ms = app.MultiService("MultiService")
        self.s1 = StoppingServiceII("testService")
        ms.addService(self.s1)
        d = ms.stopService()
        d.addCallback(self.cb_nonetest)

    def cb_nonetest(self, res):
        self.callbackRan = 1
        self.assertEqual((SUCCESS, None), res[self.s1])

    def testEmptyStopService(self):
        """MutliService.stopService returns Deferred when empty."""
        ms = app.MultiService("MultiService")
        d = ms.stopService()
        d.addCallback(self.cb_emptytest)

    def cb_emptytest(self, res):
        self.callbackRan = 1
        self.assertEqual(len(res), 0)

    def tearDown(self):
        log.flushErrors (StopError)
        self.failUnless(self.callbackRan, "Callback was never run.")

if __name__ == '__main__':
    unittest.main()
