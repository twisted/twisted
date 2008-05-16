# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorCore}.
"""

__metaclass__ = type

import signal

from twisted.internet.defer import Deferred
from twisted.internet.test.reactormixins import ReactorBuilder


class SystemEventTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorCore.addSystemEventTrigger}
    and L{IReactorCore.fireSystemEvent}.
    """
    def test_stopWhenNotStarted(self):
        """
        C{reactor.stop()} raises L{RuntimeError} when called when the reactor
        has not been started.
        """
        reactor = self.buildReactor()
        self.assertRaises(RuntimeError, reactor.stop)


    def test_stopWhenAlreadyStopped(self):
        """
        C{reactor.stop()} raises L{RuntimeError} when called after the reactor
        has been stopped.
        """
        reactor = self.buildReactor()
        reactor.callWhenRunning(reactor.stop)
        reactor.run()
        self.assertRaises(RuntimeError, reactor.stop)


    def test_callWhenRunningOrder(self):
        """
        Functions are run in the order that they were passed to
        L{reactor.callWhenRunning}.
        """
        reactor = self.buildReactor()
        events = []
        reactor.callWhenRunning(events.append, "first")
        reactor.callWhenRunning(events.append, "second")
        reactor.callWhenRunning(reactor.stop)
        reactor.run()
        self.assertEqual(events, ["first", "second"])


    def test_runningForStartupEvents(self):
        """
        The reactor is not running when C{"before"} C{"startup"} triggers are
        called and is running when C{"during"} and C{"after"} C{"startup"}
        triggers are called.
        """
        reactor = self.buildReactor()
        state = {}
        def beforeStartup():
            state['before'] = reactor.running
        def duringStartup():
            state['during'] = reactor.running
        def afterStartup():
            state['after'] = reactor.running
        reactor.addSystemEventTrigger("before", "startup", beforeStartup)
        reactor.addSystemEventTrigger("during", "startup", duringStartup)
        reactor.addSystemEventTrigger("after", "startup", afterStartup)
        reactor.callWhenRunning(reactor.stop)
        self.assertEqual(state, {})
        reactor.run()
        self.assertEqual(
            state,
            {"before": False,
             "during": True,
             "after": True})


    def test_signalHandlersInstalledDuringStartup(self):
        """
        Signal handlers are installed in responsed to the C{"during"}
        C{"startup"}.
        """
        reactor = self.buildReactor()
        phase = [None]
        def beforeStartup():
            phase[0] = "before"
        def afterStartup():
            phase[0] = "after"
        reactor.addSystemEventTrigger("before", "startup", beforeStartup)
        reactor.addSystemEventTrigger("after", "startup", afterStartup)

        sawPhase = [None]
        def fakeSignal(signum, action):
            sawPhase[0] = phase[0]
        self.patch(signal, 'signal', fakeSignal)
        reactor.callWhenRunning(reactor.stop)
        self.assertEqual(phase[0], None)
        self.assertEqual(sawPhase[0], None)
        reactor.run()
        self.assertEqual(sawPhase[0], "before")
        self.assertEqual(phase[0], "after")


    def test_stopShutDownEvents(self):
        """
        C{reactor.stop()} fires all three phases of shutdown event triggers
        before it makes C{reactor.run()} return.
        """
        reactor = self.buildReactor()
        events = []
        reactor.addSystemEventTrigger(
            "before", "shutdown",
            lambda: events.append(("before", "shutdown")))
        reactor.addSystemEventTrigger(
            "during", "shutdown",
            lambda: events.append(("during", "shutdown")))
        reactor.addSystemEventTrigger(
            "after", "shutdown",
            lambda: events.append(("after", "shutdown")))
        reactor.callWhenRunning(reactor.stop)
        reactor.run()
        self.assertEquals(events, [("before", "shutdown"),
                                   ("during", "shutdown"),
                                   ("after", "shutdown")])


    def test_shutdownFiresTriggersAsynchronously(self):
        """
        C{"before"} C{"shutdown"} triggers are not run synchronously from
        L{reactor.stop}.
        """
        reactor = self.buildReactor()
        events = []
        reactor.addSystemEventTrigger(
            "before", "shutdown", events.append, "before shutdown")
        def stopIt():
            reactor.stop()
            events.append("stopped")
        reactor.callWhenRunning(stopIt)
        self.assertEqual(events, [])
        reactor.run()
        self.assertEqual(events, ["stopped", "before shutdown"])


    def test_multipleRun(self):
        """
        C{reactor.run()} emits a warning when called when the reactor is
        already running.  The re-entrant run blocks until the reactor is
        stopped.  Stopping the reactor causes all calls to run to return.
        """
        events = []
        def reentrantRun():
            self.assertWarns(
                DeprecationWarning,
                "Reactor already running! This behavior is deprecated since "
                "Twisted 8.0",
                __file__,
                lambda: reactor.run())
            events.append("tested")
        reactor = self.buildReactor()
        reactor.callWhenRunning(reentrantRun)
        reactor.callWhenRunning(reactor.stop)
        reactor.run()
        self.assertEqual(events, ["tested"])


    def test_runWithAsynchronousBeforeStartupTrigger(self):
        """
        When there is a C{'before'} C{'startup'} trigger which returns an
        unfired L{Deferred}, C{reactor.run()} starts the reactor and does not
        return until after C{reactor.stop()} is called
        """
        events = []
        def trigger():
            events.append('trigger')
            d = Deferred()
            d.addCallback(callback)
            reactor.callLater(0, d.callback, None)
            return d
        def callback(ignored):
            events.append('callback')
            reactor.stop()
        reactor = self.buildReactor()
        reactor.addSystemEventTrigger('before', 'startup', trigger)
        reactor.run()
        self.assertEqual(events, ['trigger', 'callback'])


    def test_crash(self):
        """
        C{reactor.crash()} stops the reactor and does not fire shutdown
        triggers.
        """
        reactor = self.buildReactor()
        events = []
        reactor.addSystemEventTrigger(
            "before", "shutdown",
            lambda: events.append(("before", "shutdown")))
        reactor.callWhenRunning(reactor.callLater, 0, reactor.crash)
        reactor.run()
        self.assertFalse(reactor.running)
        self.assertFalse(
            events,
            "Shutdown triggers invoked but they should not have been.")


    def test_runAfterCrash(self):
        """
        C{reactor.run()} restarts the reactor after it has been stopped by
        C{reactor.crash()}.
        """
        events = []
        def crash():
            events.append('crash')
            reactor.crash()
        reactor = self.buildReactor()
        reactor.callWhenRunning(crash)
        reactor.run()
        def stop():
            events.append(('stop', reactor.running))
            reactor.stop()
        reactor.callWhenRunning(stop)
        reactor.run()
        self.assertEqual(events, ['crash', ('stop', True)])


globals().update(SystemEventTestsBuilder.makeTestCaseClasses())
