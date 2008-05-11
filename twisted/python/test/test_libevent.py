# Copyright (c) 2007-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{libevent} wrapper.
"""

import socket, errno, sys, os, weakref, gc, signal

from twisted.trial import unittest
from twisted.internet.defer import Deferred

try:
    from twisted.python import libevent
except ImportError:
    libevent = None



class EventTestCase(unittest.TestCase):
    """
    Tests for libevent bindings.
    """

    def test_create(self):
        """
        Test the creation of an event object.
        """
        evt = libevent.createEvent(1, libevent.EV_READ, lambda *args: None)
        evt.addToLoop()
        evt.removeFromLoop()
        self.assertEquals(evt.eventBase, libevent.DefaultEventBase)


    def test_validObjectStructure(self):
        """
        Check that event attributes match what was passed.
        """
        def cb(*args):
            pass
        evt = libevent.createEvent(sys.stdout, libevent.EV_READ, cb)
        self.assertEquals(evt.fileno(), sys.stdout.fileno())
        self.assertEquals(evt.callback, cb)
        self.assertEquals(evt.events & libevent.EV_READ, libevent.EV_READ)
        self.assertEquals(evt.numCalls, 0)
        self.assertEquals(evt.priority, 1)


    def test_badCreate(self):
        """
        Test that attempting to create an libevent object with some random
        objects raises a C{TypeError}.
        """
        def _test(*args):
            self.assertRaises(TypeError, libevent.createEvent, *args)
        _test("egg", libevent.EV_READ, lambda *args: None)
        _test(1, "spam", lambda *args: None)
        _test(1, libevent.EV_READ, "foo")
        _test(None)


    def test_timeout(self):
        """
        Test timeout facility.
        """
        timerEvents = []
        timerEvt = libevent.createTimer(lambda *args: timerEvents.append(args))
        timerEvt.addToLoop(0.0001)
        libevent.loop(libevent.EVLOOP_ONCE)
        self.assertEquals(timerEvents, [(-1, libevent.EV_TIMEOUT, timerEvt)])


    def test_reference(self):
        """
        Test that event object doesn't leek references.
        """
        def cb(*args):
            pass
        org = sys.getrefcount(cb)
        evt = libevent.createEvent(sys.stdout, libevent.EV_READ, cb)
        evt.addToLoop()
        evt.removeFromLoop()
        del evt
        gc.collect()
        self.assertEquals(sys.getrefcount(cb), org)


    def test_timerFlags(self):
        """
        Test flag values of a timer object.
        """
        timer = libevent.createTimer(lambda *args: None)
        timer.addToLoop(10)
        self.assertTrue(timer.pending() & libevent.EV_TIMEOUT)
        timer.removeFromLoop()
        self.assertFalse(timer.pending() & libevent.EV_TIMEOUT)


    def test_settingPriority(self):
        """
        Tests setting priority of an event object. The value of priority
        should change or it should raise an error if the event is already
        active.
        """
        evt = libevent.createTimer(lambda *args: None)
        evt.setPriority(2)
        self.assertEqual(evt.priority, 2)
        evt.addToLoop()
        self.assertRaises(libevent.EventError, evt.setPriority, 3)

        evt = libevent.createEvent(1, libevent.EV_READ, lambda *args: None)
        evt.addToLoop()
        evt.setPriority(2)
        self.assertEqual(evt.priority, 2)



class ConnectedEventTestCase(unittest.TestCase):
    """
    Tests for event with socket bindings.
    """

    def setUp(self):
        """
        Create a listening server port and a list to keep track
        of created sockets.
        """
        self.serverSocket = socket.socket()
        self.serverSocket.bind(('127.0.0.1', 0))
        self.serverSocket.listen(1)
        self.connections = [self.serverSocket]


    def tearDown(self):
        """
        Close any sockets which were opened by the test.
        """
        for skt in self.connections:
            skt.close()


    def _connectedPair(self):
        """
        Return the two sockets which make up a new TCP connection.
        """
        client = socket.socket()
        client.setblocking(False)
        try:
            client.connect(('127.0.0.1', self.serverSocket.getsockname()[1]))
        except socket.error, e:
            self.assertEquals(e.args[0], errno.EINPROGRESS)
        server, addr = self.serverSocket.accept()

        self.connections.extend((client, server))
        return client, server


    def test_loop(self):
        """
        Test waiting on an libevent object which has had some sockets added to
        it: first check write availability, write, then remove from loop.
        """
        clientEvents = []
        serverEvents = []
        timerEvents = []
        client, server = self._connectedPair()
        clientEvt = libevent.createEvent(client.fileno(),
            libevent.EV_READ | libevent.EV_WRITE | libevent.EV_PERSIST,
            lambda *args: clientEvents.append(args))
        serverEvt = libevent.createEvent(server.fileno(),
            libevent.EV_READ | libevent.EV_WRITE | libevent.EV_PERSIST,
            lambda *args: serverEvents.append(args))
        clientEvt.addToLoop()
        serverEvt.addToLoop()

        timerEvt = libevent.createTimer(lambda *args: timerEvents.append(args))
        timerEvt.addToLoop(1.0)
        libevent.loop(libevent.EVLOOP_ONCE)
        timerEvt.removeFromLoop()
        self.assertEquals(clientEvents,
            [(client.fileno(), libevent.EV_WRITE, clientEvt)])
        self.assertEquals(serverEvents,
            [(server.fileno(), libevent.EV_WRITE, serverEvt)])
        self.failIf(timerEvents)

        clientEvents = []
        serverEvents = []

        client.send("Hello!")
        server.send("world!!!")

        timerEvt.addToLoop(1.0)
        libevent.loop(libevent.EVLOOP_ONCE)

        self.assertEquals(clientEvents,
            [(client.fileno(), libevent.EV_READ | libevent.EV_WRITE, clientEvt)])
        self.assertEquals(serverEvents,
            [(server.fileno(), libevent.EV_READ | libevent.EV_WRITE, serverEvt)])
        self.failIf(timerEvents)

        clientEvents = []
        serverEvents = []

        clientEvt.removeFromLoop()
        serverEvt.removeFromLoop()

        timerEvt.addToLoop(0.01)
        libevent.loop(libevent.EVLOOP_ONCE)
        self.assertEquals(timerEvents, [(-1, libevent.EV_TIMEOUT, timerEvt)])
        self.failIf(clientEvents)
        self.failIf(serverEvents)



class EventBaseTestCase(unittest.TestCase):
    """
    Test L{libevent.EventBase} usage.
    """

    def setUp(self):
        """
        Create a weakvaluedict in order to hold potentially leaked objects,
        and another dict to hold potentially destroyed objects.
        """
        self._leaks = weakref.WeakValueDictionary()
        self._survivors = {}


    def _watchForLeaks(self, *args):
        """
        Watch the given objects for leaks, by creating weakrefs to them.
        """
        for obj in args:
            key = id(obj), repr(obj)
            self._leaks[key] = obj


    def _watchForSurvival(self, *args):
        """
        Watch the given objects for survival, by creating weakrefs to them.
        """
        for obj in args:
            key = id(obj), repr(obj)
            self._survivors[key] = weakref.ref(obj)


    def _assertLeaks(self):
        """
        Assert that all objects watched for leaks have been destroyed.
        """
        # Trigger cycle breaking
        gc.collect()
        if len(self._leaks):
            self.fail("%d objects have leaked: %s" % (
                len(self._leaks),
                ", ".join([key[1] for key in self._leaks])
                ))


    def _assertSurvival(self):
        """
        Assert that all objects watched for survival have survived.
        """
        # Trigger cycle breaking
        gc.collect()
        dead = []
        for (id_, repr_), ref in self._survivors.items():
            if ref() is None:
                dead.append(repr_)
        if dead:
            self.fail("%d objects should have survived "
                "but have been destroyed: %s" % (len(dead), ", ".join(dead)))


    def _allocateStuff(self):
        """
        Allocate some objects so as to try to overwrite dead objects with other
        stuff. Not guaranteed to work but at least we try :-)
        """
        # Reclaim memory, then fill it. We create a lot of plain objects so
        # that the main allocator is exercised.
        gc.collect()
        class _Dummy(object):
            pass
        [_Dummy() for i in xrange(10000)]


    def test_create(self):
        """
        Test the creation of an event base object, then an event on this object.
        """
        newEventBase = libevent.EventBase()
        evt = newEventBase.createEvent(1, libevent.EV_READ, lambda *args: None)
        self.assertEquals(evt.eventBase, newEventBase)


    def test_badCreate(self):
        """
        Test that giving garbage arguments raises exceptions.
        """
        self.assertRaises(TypeError, libevent.EventBase, "foo")
        self.assertRaises(ValueError, libevent.EventBase, -1)
        self.assertRaises(TypeError, libevent.EventBase, ())


    def test_switch(self):
        """
        Change the event base of an event.
        """
        newEventBase = libevent.EventBase()
        evt = libevent.createEvent(1, libevent.EV_READ, lambda *args: None)
        self.failIfEquals(evt.eventBase, newEventBase)
        evt.setEventBase(newEventBase)
        self.assertEquals(evt.eventBase, newEventBase)


    def test_customPriority(self):
        """
        Test setting priority of the eventBase, and check it modifies default
        priority of events.
        """
        newEventBase = libevent.EventBase(numPriorities=420)
        evt = newEventBase.createEvent(0, libevent.EV_READ, lambda *args: None)
        self.assertEqual(evt.priority, 210)


    def test_loopExit(self):
        """
        Test loop exit: it should stop dispatch method. It can't be done with
        L{libevent.DefaultEventBase} or the tests wouldn't run with the libevent
        reactor.
        """
        newEventBase = libevent.EventBase()
        cb = lambda fd, events, obj: newEventBase.loopExit(0)
        timer = newEventBase.createTimer(cb)
        timer.addToLoop(0.01)
        newEventBase.dispatch()


    def test_loopError(self):
        """
        Test that loop forward exception raised in callback.
        """
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            raise RuntimeError("foo")
        timer = newEventBase.createTimer(cb)
        timer.addToLoop(0.01)
        self.assertRaises(RuntimeError, newEventBase.loop, libevent.EVLOOP_ONCE)


    def test_dispatchError(self):
        """
        Check that dispatch forwards exception raised in callback.
        """
        newEventBase = libevent.EventBase()
        fireEvents = []

        def eb(fd, events, obj):
            raise RuntimeError("foo")
        timer = newEventBase.createTimer(eb)
        timer.addToLoop(0.001)

        def cb(fd, events, obj):
            fireEvents.append((fd, events, obj))
        timer = newEventBase.createTimer(cb)
        timer.addToLoop(0.001)

        self.assertRaises(RuntimeError, newEventBase.dispatch)
        if not fireEvents:
            # If we distpatch again, it should fire it
            newEventBase.dispatch()
        self.assertEquals(len(fireEvents), 1)


    def test_successfulCallbackReference(self):
        """
        Check that successful callbacks aren't leaked.
        """
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            pass
        self._watchForLeaks(cb)
        timer = newEventBase.createTimer(cb)
        timer.addToLoop(0.002)
        newEventBase.dispatch()

        del cb, timer
        self._assertLeaks()


    def test_failedCallbackReference(self):
        """
        Check that failed callbacks aren't leaked.
        """
        newEventBase = libevent.EventBase()
        def eb(fd, events, obj):
            raise RuntimeError("foo")
        self._watchForLeaks(eb)
        timer = newEventBase.createTimer(eb)
        timer.addToLoop(0.002)
        self.assertRaises(RuntimeError, newEventBase.dispatch)

        del eb, timer
        self._assertLeaks()


    def test_unfiredCallbackReference(self):
        """
        Check that unfired callbacks aren't leaked when the eventBase is
        destroyed.
        """
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            pass
        self._watchForLeaks(cb)
        timer = newEventBase.createTimer(cb)
        timer.addToLoop(1)

        del cb, timer, newEventBase
        self._assertLeaks()


    def test_callbackReference(self):
        """
        Check that a simple unregistered callback doesn't leak.
        """
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            pass
        timer = newEventBase.createTimer(cb)
        self._watchForLeaks(cb)

        del cb, timer
        self._assertLeaks()


    def test_callbackExceptionReference(self):
        """
        Check that exceptions propagated from callbacks aren't leaked.
        """
        # Custom subclass so that weakref's are possible
        class _Exception(RuntimeError):
            pass
        exc = [None]
        newEventBase = libevent.EventBase()
        def eb(fd, events, obj):
            exc[0] = _Exception("foo")
            raise exc[0]
        timer = newEventBase.createTimer(eb)
        timer.addToLoop(0.002)
        self.assertRaises(RuntimeError, newEventBase.dispatch)
        self._watchForLeaks(exc[0])

        del exc[0]
        self._assertLeaks()


    def test_callbackSurvival(self):
        """
        Check that a registered callback survives even when the local reference
        dies.
        """
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            pass
        timer = newEventBase.createTimer(cb)
        timer.addToLoop(1)
        self._watchForSurvival(cb)

        del cb, timer
        self._assertSurvival()


    def test_persistentCallbackSurvival(self):
        """
        Check that a persistent callback survives after been fired.
        """
        rfd, wfd = os.pipe()
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            newEventBase.loopExit(0)
        timer = newEventBase.createEvent(rfd,
            libevent.EV_READ | libevent.EV_PERSIST, cb)
        timer.addToLoop()
        os.write(wfd, " ")
        newEventBase.dispatch()
        self._watchForSurvival(cb)

        del cb, timer
        self._assertSurvival()


    def test_persistentFailedCallbackSurvival(self):
        """
        Check that a persistent callback survives after raising an exception.
        """
        rfd, wfd = os.pipe()
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            newEventBase.loopExit(0)
            raise RuntimeError("foo")
        timer = newEventBase.createEvent(rfd,
            libevent.EV_READ | libevent.EV_PERSIST, cb)
        timer.addToLoop()
        os.write(wfd, " ")
        self.assertRaises(RuntimeError, newEventBase.dispatch)
        self._watchForSurvival(cb)

        del cb, timer
        self._assertSurvival()


    def test_persistentCallbackReference(self):
        """
        Check that a persistent callback doesn't leak when the eventBase
        is destroyed.
        """
        rfd, wfd = os.pipe()
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            newEventBase.loopExit(0)
        timer = newEventBase.createEvent(rfd,
            libevent.EV_READ | libevent.EV_PERSIST, cb)
        timer.addToLoop()
        os.write(wfd, " ")
        newEventBase.dispatch()
        self._watchForLeaks(cb)

        newEventBase = None
        del cb, timer
        self._assertLeaks()


    def test_dispatchedEventRefCount(self):
        """
        Check that dispatched event refcounts don't grow.
        """
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            pass
        timer = newEventBase.createTimer(cb)
        orig = sys.getrefcount(timer)
        timer.addToLoop(0.01)
        newEventBase.dispatch()
        # Perhaps some dead cycles involve our object -> break them
        gc.collect()
        self.assertEquals(orig, sys.getrefcount(timer))


    def test_keyErrorCleanup(self):
        """
        If a non-persistent event calls C{removeFromLoop}, it should not raise
        a random exception.
        """
        newEventBase = libevent.EventBase()
        def cb(fd, events, obj):
            pass
        timer = newEventBase.createTimer(cb, persist=False)
        timer.addToLoop(0.01)
        newEventBase.dispatch()
        timer.removeFromLoop()
        # Before the bug was correct in EventBase_UnregisterEvent, this line
        # killed python. Not very unity...
        gc.collect()


    def test_createSignalHandler(self):
        """
        C{createSignalHandler} builds an event that fires a callback when the
        specified signal is sent to the process.
        """
        newEventBase = libevent.EventBase()
        d = Deferred()
        def cbSignal(fd, events, obj):
            d.callback((fd, events, obj))
        evt = newEventBase.createSignalHandler(signal.SIGUSR1, cbSignal,
                                               persist=False)
        evt.addToLoop()
        def cbTimer(fd, events, obj):
            os.kill(os.getpid(), signal.SIGUSR1)
        timer = newEventBase.createTimer(cbTimer, persist=False)
        timer.addToLoop(0.01)
        newEventBase.dispatch()
        def check(result):
            self.assertIdentical(result[2], evt)
        return d.addCallback(check)

    if getattr(signal, "SIGUSR1", None) is None:
        test_createSignalHandler.skip = "SIGUSR1 not available"



if libevent is None:
    EventTestCase.skip = "libevent module unavailable"
    ConnectedEventTestCase.skip = "libevent module unavailable"
    EventBaseTestCase.skip = "libevent module unavailable"

