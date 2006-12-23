# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest
from twisted.internet import reactor, protocol, error, abstract, defer
from twisted.internet import interfaces, base

from twisted.test.time_helpers import Clock

try:
    from twisted.internet import ssl
except ImportError:
    ssl = None
if ssl and not ssl.supported:
    ssl = None

from twisted.internet.defer import Deferred, maybeDeferred
from twisted.python import util

import os
import sys
import time
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
    """
    Tests for a random pile of crap in twisted.internet, I suppose.
    """

    def test_callLater(self):
        """
        Test that a DelayedCall really calls the function it is supposed to call.
        """
        d = Deferred()
        reactor.callLater(0, d.callback, None)
        d.addCallback(self.assertEqual, None)
        return d


    def test_cancelDelayedCall(self):
        """
        Test that when a DelayedCall is cancelled it does not run.
        """
        called = []
        def function():
            called.append(None)
        call = reactor.callLater(0, function)
        call.cancel()

        # Schedule a call in two "iterations" to check to make sure that the
        # above call never ran.
        d = Deferred()
        def check():
            try:
                self.assertEqual(called, [])
            except:
                d.errback()
            else:
                d.callback(None)
        reactor.callLater(0, reactor.callLater, 0, check)
        return d


    def test_cancelCancelledDelayedCall(self):
        """
        Test that cancelling a DelayedCall which has already been cancelled
        raises the appropriate exception.
        """
        call = reactor.callLater(0, lambda: None)
        call.cancel()
        self.assertRaises(error.AlreadyCancelled, call.cancel)


    def test_cancelCalledDelayedCallSynchronous(self):
        """
        Test that cancelling a DelayedCall in the DelayedCall's function as
        that function is being invoked by the DelayedCall raises the
        appropriate exception.
        """
        d = Deferred()
        def later():
            try:
                self.assertRaises(error.AlreadyCalled, call.cancel)
            except:
                d.errback()
            else:
                d.callback(None)
        call = reactor.callLater(0, later)
        return d


    def test_cancelCalledDelayedCallAsynchronous(self):
        """
        Test that cancelling a DelayedCall after it has run its function
        raises the appropriate exception.
        """
        d = Deferred()
        def check():
            try:
                self.assertRaises(error.AlreadyCalled, call.cancel)
            except:
                d.errback()
            else:
                d.callback(None)
        def later():
            reactor.callLater(0, check)
        call = reactor.callLater(0, later)
        return d


    def testCallLaterDelayAndReset(self):
        clock = Clock()
        clock.install()
        try:
            callbackTimes = [None, None]

            def resetCallback():
                callbackTimes[0] = clock()

            def delayCallback():
                callbackTimes[1] = clock()

            ireset = reactor.callLater(2, resetCallback)
            idelay = reactor.callLater(3, delayCallback)

            clock.pump(reactor, [0, 1])

            ireset.reset(2) # (now)1 + 2 = 3
            idelay.delay(3) # (orig)3 + 3 = 6

            clock.pump(reactor, [0, 1])

            self.assertIdentical(callbackTimes[0], None)
            self.assertIdentical(callbackTimes[0], None)

            clock.pump(reactor, [0, 1])

            self.assertEquals(callbackTimes[0], 3)
            self.assertEquals(callbackTimes[1], None)

            clock.pump(reactor, [0, 3])
            self.assertEquals(callbackTimes[1], 6)
        finally:
            clock.uninstall()


    def testCallLaterTime(self):
        d = reactor.callLater(10, lambda: None)
        try:
            self.failUnless(d.getTime() - (time.time() + 10) < 1)
        finally:
            d.cancel()

    def testCallInNextIteration(self):
        calls = []
        def f1():
            calls.append('f1')
            reactor.callLater(0.0, f2)
        def f2():
            calls.append('f2')
            reactor.callLater(0.0, f3)
        def f3():
            calls.append('f3')

        reactor.callLater(0, f1)
        self.assertEquals(calls, [])
        reactor.iterate()
        self.assertEquals(calls, ['f1'])
        reactor.iterate()
        self.assertEquals(calls, ['f1', 'f2'])
        reactor.iterate()
        self.assertEquals(calls, ['f1', 'f2', 'f3'])

    def testCallLaterOrder(self):
        l = []
        l2 = []
        def f(x):
            l.append(x)
        def f2(x):
            l2.append(x)
        def done():
            self.assertEquals(l, range(20))
        def done2():
            self.assertEquals(l2, range(10))

        for n in range(10):
            reactor.callLater(0, f, n)
        for n in range(10):
            reactor.callLater(0, f, n+10)
            reactor.callLater(0.1, f2, n)

        reactor.callLater(0, done)
        reactor.callLater(0.1, done2)
        d = Deferred()
        reactor.callLater(0.2, d.callback, None)
        return d

    testCallLaterOrder.todo = "See bug 1396"
    testCallLaterOrder.skip = "Trial bug, todo doesn't work! See bug 1397"
    def testCallLaterOrder2(self):
        # This time destroy the clock resolution so that it fails reliably
        # even on systems that don't have a crappy clock resolution.

        def seconds():
            return int(time.time())

        from twisted.internet import base
        from twisted.python import runtime
        base_original = base.seconds
        runtime_original = runtime.seconds
        base.seconds = seconds
        runtime.seconds = seconds

        def cleanup(x):
            runtime.seconds = runtime_original
            base.seconds = base_original
            return x
        return maybeDeferred(self.testCallLaterOrder).addBoth(cleanup)

    testCallLaterOrder2.todo = "See bug 1396"
    testCallLaterOrder2.skip = "Trial bug, todo doesn't work! See bug 1397"

    def testDelayedCallStringification(self):
        # Mostly just make sure str() isn't going to raise anything for
        # DelayedCalls within reason.
        dc = reactor.callLater(0, lambda x, y: None, 'x', y=10)
        str(dc)
        dc.reset(5)
        str(dc)
        dc.cancel()
        str(dc)

        dc = reactor.callLater(0, lambda: None, x=[({'hello': u'world'}, 10j), reactor], *range(10))
        str(dc)
        dc.cancel()
        str(dc)

        def calledBack(ignored):
            str(dc)
        d = Deferred().addCallback(calledBack)
        dc = reactor.callLater(0, d.callback, None)
        str(dc)
        return d


    def testDelayedCallSecondsOverride(self):
        """
        Test that the C{seconds} argument to DelayedCall gets used instead of
        the default timing function, if it is not None.
        """
        def seconds():
            return 10
        dc = base.DelayedCall(5, lambda: None, (), {}, lambda dc: None, lambda dc: None, seconds)
        self.assertEquals(dc.getTime(), 5)
        dc.reset(3)
        self.assertEquals(dc.getTime(), 13)


class CallFromThreadTests(unittest.TestCase):
    def testWakeUp(self):
        # Make sure other threads can wake up the reactor
        d = Deferred()
        def wake():
            time.sleep(0.1)
            # callFromThread will call wakeUp for us
            reactor.callFromThread(d.callback, None)
        reactor.callInThread(wake)
        return d

    if interfaces.IReactorThreads(reactor, None) is None:
        testWakeUp.skip = "Nothing to wake up for without thread support"

    def _stopCallFromThreadCallback(self):
        self.stopped = True

    def _callFromThreadCallback(self, d):
        reactor.callFromThread(self._callFromThreadCallback2, d)
        reactor.callLater(0, self._stopCallFromThreadCallback)

    def _callFromThreadCallback2(self, d):
        try:
            self.assert_(self.stopped)
        except:
            # Send the error to the deferred
            d.errback()
        else:
            d.callback(None)

    def testCallFromThreadStops(self):
        """
        Ensure that callFromThread from inside a callFromThread
        callback doesn't sit in an infinite loop and lets other
        things happen too.
        """
        self.stopped = False
        d = defer.Deferred()
        reactor.callFromThread(self._callFromThreadCallback, d)
        return d


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


    def testRun(self):
        """
        Test that reactor.crash terminates reactor.run
        """
        for i in xrange(3):
            reactor.callLater(0.01, reactor.crash)
            reactor.run()


    def testIterate(self):
        """
        Test that reactor.iterate(0) doesn't block
        """
        start = time.time()
        # twisted timers are distinct from the underlying event loop's
        # timers, so this fail-safe probably won't keep a failure from
        # hanging the test
        t = reactor.callLater(10, reactor.crash)
        reactor.iterate(0) # shouldn't block
        stop = time.time()
        elapsed = stop - start
        #print "elapsed", elapsed
        self.failUnless(elapsed < 8)
        t.cancel()


    def test_crash(self):
        """
        reactor.crash should NOT fire shutdown triggers
        """
        events = []
        self.addTrigger(
            "before", "shutdown",
            lambda: events.append(("before", "shutdown")))

        # reactor.crash called from an "after-startup" trigger is too early
        # for the gtkreactor: gtk_mainloop is not yet running. Same is true
        # when called with reactor.callLater(0). Must be >0 seconds in the
        # future to let gtk_mainloop start first.
        reactor.callWhenRunning(
            reactor.callLater, 0, reactor.crash)
        reactor.run()
        self.failIf(events, "reactor.crash invoked shutdown triggers, but it "
                            "isn't supposed to.")

    # XXX Test that reactor.stop() invokes shutdown triggers



class DelayedTestCase(unittest.TestCase):
    def setUp(self):
        self.finished = 0
        self.counter = 0
        self.timers = {}
        self.deferred = defer.Deferred()
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
        l2 = list(reactor.getDelayedCalls())

        # There should be at least the calls we put in.  There may be other
        # calls that are none of our business and that we should ignore,
        # though.

        missing = []
        for dc in l1:
            if dc not in l2:
                missing.append(dc)
        if missing:
            self.finished = 1
        self.failIf(missing, "Should have been missing no calls, instead was missing " + repr(missing))

    def callback(self, tag):
        del self.timers[tag]
        self.checkTimers()

    def addCallback(self, tag):
        self.callback(tag)
        self.addTimer(15, self.callback)

    def done(self, tag):
        self.finished = 1
        self.callback(tag)
        self.deferred.callback(None)

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
        self.addTimer(29, self.callback)
        self.addTimer(25, self.addCallback)
        self.addTimer(26, self.callback)

        self.timers[which].cancel()
        del self.timers[which]
        self.checkTimers()

        self.deferred.addCallback(lambda x : self.checkTimers())
        return self.deferred

    def testActive(self):
        dcall = reactor.callLater(0, lambda: None)
        self.assertEquals(dcall.active(), 1)
        reactor.iterate()
        self.assertEquals(dcall.active(), 0)

resolve_helper = """
import %(reactor)s
%(reactor)s.install()
from twisted.internet import reactor

class Foo:
    def __init__(self):
        reactor.callWhenRunning(self.start)
        self.timer = reactor.callLater(3, self.failed)
    def start(self):
        reactor.resolve('localhost').addBoth(self.done)
    def done(self, res):
        print 'done', res
        reactor.stop()
    def failed(self):
        print 'failed'
        self.timer = None
        reactor.stop()
f = Foo()
reactor.run()
"""

class ChildResolveProtocol(protocol.ProcessProtocol):
    def __init__(self, onCompletion):
        self.onCompletion = onCompletion

    def connectionMade(self):
        self.output = []
        self.error = []

    def outReceived(self, out):
        self.output.append(out)

    def errReceived(self, err):
        self.error.append(err)

    def processEnded(self, reason):
        self.onCompletion.callback((reason, self.output, self.error))
        self.onCompletion = None


class Resolve(unittest.TestCase):
    def testChildResolve(self):
        # I've seen problems with reactor.run under gtk2reactor. Spawn a
        # child which just does reactor.resolve after the reactor has
        # started, fail if it does not complete in a timely fashion.
        helperPath = os.path.abspath(self.mktemp())
        helperFile = open(helperPath, 'w')

        # Eeueuuggg
        reactorName = reactor.__module__

        helperFile.write(resolve_helper % {'reactor': reactorName})
        helperFile.close()

        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)

        helperDeferred = Deferred()
        helperProto = ChildResolveProtocol(helperDeferred)

        reactor.spawnProcess(helperProto, sys.executable, ("python", "-u", helperPath), env)

        def cbFinished((reason, output, error)):
            # If the output is "done 127.0.0.1\n" we don't really care what
            # else happened.
            output = ''.join(output)
            if output != 'done 127.0.0.1\n':
                self.fail((
                    "The child process failed to produce the desired results:\n"
                    "   Reason for termination was: %r\n"
                    "   Output stream was: %r\n"
                    "   Error stream was: %r\n") % (reason.getErrorMessage(), output, ''.join(error)))

        helperDeferred.addCallback(cbFinished)
        return helperDeferred

if not interfaces.IReactorProcess(reactor, None):
    Resolve.skip = "cannot run test: reactor doesn't support IReactorProcess"

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


class callFromThreadTestCase(unittest.TestCase):
    """Task scheduling from threads tests."""

    if interfaces.IReactorThreads(reactor, None) is None:
        skip = "Nothing to test without thread support"

    def schedule(self, *args, **kwargs):
        """Override in subclasses."""
        reactor.callFromThread(*args, **kwargs)

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


class DummyProducer(object):
    """
    Very uninteresting producer implementation used by tests to ensure the
    right methods are called by the consumer with which it is registered.

    @type events: C{list} of C{str}
    @ivar events: The producer/consumer related events which have happened to
    this producer.  Strings in this list may be C{'resume'}, C{'stop'}, or
    C{'pause'}.  Elements are added as they occur.
    """

    def __init__(self):
        self.events = []


    def resumeProducing(self):
        self.events.append('resume')


    def stopProducing(self):
        self.events.append('stop')


    def pauseProducing(self):
        self.events.append('pause')



class SillyDescriptor(abstract.FileDescriptor):
    """
    A descriptor whose data buffer gets filled very fast.

    Useful for testing FileDescriptor's IConsumer interface, since
    the data buffer fills as soon as at least four characters are
    written to it, and gets emptied in a single doWrite() cycle.
    """
    bufferSize = 3
    connected = True

    def writeSomeData(self, data):
        """
        Always write all data.
        """
        return len(data)


    def startWriting(self):
        """
        Do nothing: bypass the reactor.
        """
    stopWriting = startWriting



class ReentrantProducer(DummyProducer):
    """
    Similar to L{DummyProducer}, but with a resumeProducing method which calls
    back into an L{IConsumer} method of the consumer against which it is
    registered.

    @ivar consumer: The consumer with which this producer has been or will
    be registered.

    @ivar methodName: The name of the method to call on the consumer inside
    C{resumeProducing}.

    @ivar methodArgs: The arguments to pass to the consumer method invoked in
    C{resumeProducing}.
    """
    def __init__(self, consumer, methodName, *methodArgs):
        super(ReentrantProducer, self).__init__()
        self.consumer = consumer
        self.methodName = methodName
        self.methodArgs = methodArgs


    def resumeProducing(self):
        super(ReentrantProducer, self).resumeProducing()
        getattr(self.consumer, self.methodName)(*self.methodArgs)



class TestProducer(unittest.TestCase):
    """
    Test abstract.FileDescriptor's consumer interface.
    """
    def test_doubleProducer(self):
        """
        Verify that registering a non-streaming producer invokes its
        resumeProducing() method and that you can only register one producer
        at a time.
        """
        fd = abstract.FileDescriptor()
        fd.connected = 1
        dp = DummyProducer()
        fd.registerProducer(dp, 0)
        self.assertEquals(dp.events, ['resume'])
        self.assertRaises(RuntimeError, fd.registerProducer, DummyProducer(), 0)


    def test_unconnectedFileDescriptor(self):
        """
        Verify that registering a producer when the connection has already
        been closed invokes its stopProducing() method.
        """
        fd = abstract.FileDescriptor()
        fd.disconnected = 1
        dp = DummyProducer()
        fd.registerProducer(dp, 0)
        self.assertEquals(dp.events, ['stop'])


    def _dontPausePullConsumerTest(self, methodName):
        descriptor = SillyDescriptor()
        producer = DummyProducer()
        descriptor.registerProducer(producer, streaming=False)
        self.assertEqual(producer.events, ['resume'])
        del producer.events[:]

        # Fill up the descriptor's write buffer so we can observe whether or
        # not it pauses its producer in that case.
        getattr(descriptor, methodName)('1234')

        self.assertEqual(producer.events, [])


    def test_dontPausePullConsumerOnWrite(self):
        """
        Verify that FileDescriptor does not call producer.pauseProducing() on a
        non-streaming pull producer in response to a L{IConsumer.write} call
        which results in a full write buffer. Issue #2286.
        """
        return self._dontPausePullConsumerTest('write')


    def test_dontPausePullConsumerOnWriteSequence(self):
        """
        Like L{test_dontPausePullConsumerOnWrite}, but for a call to
        C{writeSequence} rather than L{IConsumer.write}.

        C{writeSequence} is not part of L{IConsumer}, but
        L{abstract.FileDescriptor} has supported consumery behavior in response
        to calls to L{writeSequence} forever.
        """
        return self._dontPausePullConsumerTest('writeSequence')


    def _reentrantStreamingProducerTest(self, methodName):
        descriptor = SillyDescriptor()
        producer = ReentrantProducer(descriptor, methodName, 'spam')
        descriptor.registerProducer(producer, streaming=True)

        # Start things off by filling up the descriptor's buffer so it will
        # pause its producer.
        getattr(descriptor, methodName)('spam')

        # Sanity check - make sure that worked.
        self.assertEqual(producer.events, ['pause'])
        del producer.events[:]

        # After one call to doWrite, the buffer has been emptied so the
        # FileDescriptor should resume its producer.  That will result in an
        # immediate call to FileDescriptor.write which will again fill the
        # buffer and result in the producer being paused.
        descriptor.doWrite()
        self.assertEqual(producer.events, ['resume', 'pause'])
        del producer.events[:]

        # After a second call to doWrite, the exact same thing should have
        # happened.  Prior to the bugfix for which this test was written,
        # FileDescriptor would have incorrectly believed its producer was
        # already resumed (it was paused) and so not resume it again.
        descriptor.doWrite()
        self.assertEqual(producer.events, ['resume', 'pause'])


    def test_reentrantStreamingProducerUsingWrite(self):
        """
        Verify that FileDescriptor tracks producer's paused state correctly.
        Issue #811, fixed in revision r12857.
        """
        return self._reentrantStreamingProducerTest('write')


    def test_reentrantStreamingProducerUsingWriteSequence(self):
        """
        Like L{test_reentrantStreamingProducerUsingWrite}, but for calls to
        C{writeSequence}.

        C{writeSequence} is B{not} part of L{IConsumer}, however
        C{abstract.FileDescriptor} has supported consumery behavior in response
        to calls to C{writeSequence} forever.
        """
        return self._reentrantStreamingProducerTest('writeSequence')



class PortStringification(unittest.TestCase):
    if interfaces.IReactorTCP(reactor, None) is not None:
        def testTCP(self):
            p = reactor.listenTCP(0, protocol.ServerFactory())
            portNo = p.getHost().port
            self.assertNotEqual(str(p).find(str(portNo)), -1,
                                "%d not found in %s" % (portNo, p))
            return p.stopListening()

    if interfaces.IReactorUDP(reactor, None) is not None:
        def testUDP(self):
            p = reactor.listenUDP(0, protocol.DatagramProtocol())
            portNo = p.getHost().port
            self.assertNotEqual(str(p).find(str(portNo)), -1,
                                "%d not found in %s" % (portNo, p))
            return p.stopListening()

    if interfaces.IReactorSSL(reactor, None) is not None and ssl:
        def testSSL(self, ssl=ssl):
            pem = util.sibpath(__file__, 'server.pem')
            p = reactor.listenSSL(0, protocol.ServerFactory(), ssl.DefaultOpenSSLContextFactory(pem, pem))
            portNo = p.getHost().port
            self.assertNotEqual(str(p).find(str(portNo)), -1,
                                "%d not found in %s" % (portNo, p))
            return p.stopListening()
