# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorThreads}.
"""

__metaclass__ = type

from twisted.internet.test.reactormixins import ReactorBuilder


class ThreadTestsBuilder(ReactorBuilder):
    """
    Builder for defining tests relating to L{IReactorThreads}.
    """
    def test_delayedCallFromThread(self):
        """
        A function scheduled with L{IReactorThreads.callFromThread} invoked
        from a delayed call is run immediately in the next reactor iteration.

        When invoked from the reactor thread, previous implementations of
        L{IReactorThreads.callFromThread} would skip the pipe/socket based wake
        up step, assuming the reactor would wake up on its own.  However, this
        resulted in the reactor not noticing a insert into the thread queue at
        the right time (in this case, after the thread queue has been processed
        for that reactor iteration).
        """
        reactor = self.buildReactor()

        def threadCall():
            reactor.stop()

        # Set up the use of callFromThread being tested.
        reactor.callLater(0, reactor.callFromThread, threadCall)

        before = reactor.seconds()
        self.runReactor(reactor, 60)
        after = reactor.seconds()

        # We specified a timeout of 60 seconds.  The timeout code in runReactor
        # probably won't actually work, though.  If the reactor comes out of
        # the event notification API just a little bit early, say after 59.9999
        # seconds instead of after 60 seconds, then the queued thread call will
        # get processed but the timeout delayed call runReactor sets up won't!
        # Then the reactor will stop and runReactor will return without the
        # timeout firing.  As it turns out, select() and poll() are quite
        # likely to return *slightly* earlier than we ask them to, so the
        # timeout will rarely happen, even if callFromThread is broken.  So,
        # instead we'll measure the elapsed time and make sure it's something
        # less than about half of the timeout we specified.  This is heuristic.
        # It assumes that select() won't ever return after 30 seconds when we
        # asked it to timeout after 60 seconds.  And of course like all
        # time-based tests, it's slightly non-deterministic.  If the OS doesn't
        # schedule this process for 30 seconds, then the test might fail even
        # if callFromThread is working.
        self.assertTrue(after - before < 30)


globals().update(ThreadTestsBuilder.makeTestCaseClasses())
