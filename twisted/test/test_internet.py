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

from pyunit import unittest
from twisted.internet import reactor, protocol, error, app
from twisted.internet.defer import SUCCESS, FAILURE, Deferred, succeed, fail
from twisted.python import threadable, log
threadable.init(1)

import sys
import time
import threading


class InterfaceTestCase(unittest.TestCase):

    def testTriggerSystemEvent(self):
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
        r.addSystemEventTrigger("before", "test", _appendToList)
        r.addSystemEventTrigger("during", "test", _appendToList)
        r.addSystemEventTrigger("after", "test", _appendToList)
        self.assertEquals(len(l), 0, "Nothing happened yet.")
        r.fireSystemEvent("test")
        r.iterate()
        self.assertEquals(len(l), 3, "Should have filled the list.")
        l[:]=[]
        r.addSystemEventTrigger("before", "defer", _returnDeferred)
        r.addSystemEventTrigger("before", "defer", _returnDeferred2)
        r.addSystemEventTrigger("during", "defer", _appendToList)
        r.addSystemEventTrigger("after", "defer", _appendToList)
        r.fireSystemEvent("defer")
        self.assertEquals(len(l), 0, "Event should not have fired yet.")
        d.callback(None)
        self.assertEquals(len(l), 0, "Event still should not have fired yet.")
        d2.callback(None)
        self.assertEquals(len(l), 2)
        l[:]=[]
        a = r.addSystemEventTrigger("before", "remove", _appendToList)
        b = r.addSystemEventTrigger("before", "remove", _appendToList2)
        r.removeSystemEventTrigger(b)
        r.fireSystemEvent("remove")
        self.assertEquals(len(l), 1)
        self.assertEquals(len(l2), 0)

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
        ireset.reset(0.3)
        idelay.delay(0.3)
        # both should be called sometime during this
        while time.time() - start < 0.9:
            reactor.iterate(0.01)
        self.assert_(0 < self._resetcallbackTime - start - 0.5 < 0.2)
        self.assert_(0 < self._delaycallbackTime - start - 0.8 < 0.2)

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
    """Task scheduling rom threads tests."""

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
