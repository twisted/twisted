# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from unittest import TestCase

from twisted.internet import reactor
from twisted.internet._signals import _SIGCHLDWaker, _SocketWaker, _UnixWaker
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure


def benchmarkWithReactor():
    """
    Decorator for running the test with the benchmark.
    """

    def decorator(test_target):
        """
        This is the actual decorator.
        """

        def benchmark_test(self):
            def run_test():
                self.getDeferredResult(test_target(self))

            self.benchmark(run_test)

        return benchmark_test

    return decorator


class ReactorTestCase(TestCase):
    """
    Standard library unittest test case that can spin the reactor.

    Provides support for running deferred and start/stop the reactor during
    tests.
    """

    # Number of second to wait for a deferred to have a result.
    DEFERRED_TIMEOUT = 1

    # List of names for delayed calls which should not be considered as
    # required to wait for them when running the reactor.
    EXCEPTED_DELAYED_CALLS = []

    EXCEPTED_READERS = [
        _UnixWaker,
        _SocketWaker,
        _SIGCHLDWaker,
    ]

    # Scheduled event to stop waiting for a deferred.
    _reactor_timeout_call = None

    def setUp(self):
        super(ReactorTestCase, self).setUp()
        self._timeout_reached = False
        self._reactor_timeout_failure = None

    def tearDown(self):
        try:
            self.assertIsNone(self._reactor_timeout_failure)
            self._assertReactorIsClean()
        finally:
            self._cleanReactor()
        super(ReactorTestCase, self).tearDown()

    def _reactorQueueToString(self):
        """
        Return a string representation of all delayed calls from reactor
        queue.
        """
        result = []
        for delayed in reactor.getDelayedCalls():  # :cover
            result.append(str(delayed.func))
        return "\n".join(result)

    def _threadPoolQueue(self):
        """
        Return current tasks of thread Pool, or [] when threadpool does not
        exists.

        This should only be called at cleanup as it removes elements from
        the Twisted thread queue, which will never be called.
        """
        if not reactor.threadpool:
            return []

        result = []
        while len(reactor.threadpool._team._pending):
            result.append(reactor.threadpool._team._pending.pop())
        return result

    def _threadPoolThreads(self):
        """
        Return current threads from pool, or empty list when threadpool does
        not exists.
        """
        if not reactor.threadpool:
            return []
        else:
            return reactor.threadpool.threads

    def _threadPoolWorking(self):
        """
        Return working thread from pool, or empty when threadpool does not
        exists or has no job.
        """
        if not reactor.threadpool:
            return []
        else:
            return reactor.threadpool.working

    @classmethod
    def _cleanReactor(cls):
        """
        Remove all delayed calls, readers and writers from the reactor.

        This is only for cleanup purpose and should not be used by normal
        tests.
        """
        if not reactor:
            return
        try:
            reactor.removeAll()
        except (RuntimeError, KeyError):
            # FIXME:863:
            # When running threads tests the reactor touched from the test
            # case itself which run in one tread and from the fixtures/cleanup
            # code which is executed from another thread.
            # removeAll might fail since it detects that internal state
            # is changed from other source.
            pass

        reactor.threadCallQueue = []
        for delayed_call in reactor.getDelayedCalls():
            try:
                delayed_call.cancel()
            except (ValueError, AttributeError):
                # AlreadyCancelled and AlreadyCalled are ValueError.
                # Might be canceled from the separate thread.
                # AttributeError can occur when we do multi-threading.
                pass

    def _raiseReactorTimeoutError(self, timeout):
        """
        Signal an timeout error while executing the reactor.
        """
        self._timeout_reached = True
        failure = AssertionError(
            "Reactor took more than %.2f seconds to execute." % timeout
        )
        self._reactor_timeout_failure = failure

    def _initiateTestReactor(self, timeout):
        """
        Do the steps required to initiate a reactor for testing.
        """
        self._timeout_reached = False

        # Set up timeout.
        self._reactor_timeout_call = reactor.callLater(
            timeout, self._raiseReactorTimeoutError, timeout
        )

        # Don't start the reactor if it is already started.
        # This can happen if we prevent stop in a previous run.
        if reactor._started:
            return

        reactor._startedBefore = False
        reactor._started = False
        reactor._justStopped = False
        reactor.startRunning()

    def _iterateTestReactor(self, debug=False):
        """
        Iterate the reactor.
        """
        reactor.runUntilCurrent()
        if debug:  # :cover
            # When debug is enabled with iterate using a small delay in steps,
            # to have a much better debug output.
            # Otherwise the debug messages will flood the output.
            print(
                "delayed: %s\n"
                "threads: %s\n"
                "writers: %s\n"
                "readers: %s\n"
                "threadpool size: %s\n"
                "threadpool threads: %s\n"
                "threadpool working: %s\n"
                "\n"
                % (
                    self._reactorQueueToString(),
                    reactor.threadCallQueue,
                    reactor.getWriters(),
                    reactor.getReaders(),
                    reactor.getThreadPool().q.qsize(),
                    self._threadPoolThreads(),
                    self._threadPoolWorking(),
                )
            )
            t2 = reactor.timeout()
            # For testing we want to force to reactor to wake at an
            # interval of at most 1 second.
            if t2 is None or t2 > 1:
                t2 = 0.1
            t = reactor.running and t2
            reactor.doIteration(t)
        else:
            # FIXME:4428:
            # When not executed in debug mode, some test will fail as they
            # will not spin the reactor.
            # To not slow down all the tests, we run with a very small value.
            reactor.doIteration(0.000001)

    def _shutdownTestReactor(self, prevent_stop=False):
        """
        Called at the end of a test reactor run.

        When prevent_stop=True, the reactor will not be stopped.
        """
        if not self._timeout_reached:
            # Everything fine, disable timeout.
            if self._reactor_timeout_call and not self._reactor_timeout_call.cancelled:
                self._reactor_timeout_call.cancel()

        if prevent_stop:
            # Don't continue with stop procedure.
            return

        # Let the reactor know that we want to stop reactor.
        reactor.stop()
        # Let the reactor run one more time to execute the stop code.
        reactor.iterate()

        # Set flag to fake a clean reactor.
        reactor._startedBefore = False
        reactor._started = False
        reactor._justStopped = False
        reactor.running = False
        # Start running has consumed the startup events, so we need
        # to restore them.
        reactor.addSystemEventTrigger("during", "startup", reactor._reallyStartRunning)

    def _assertReactorIsClean(self):
        """
        Check that the reactor has no delayed calls, readers or writers.

        This should only be called at teardown.
        """
        if reactor is None:
            return

        def raise_failure(location, reason):
            raise AssertionError("Reactor is not clean. %s: %s" % (location, reason))

        if reactor._started:  # :cover
            # Reactor was not stopped, so stop it before raising the error.
            self._shutdownTestReactor()
            raise AssertionError("Reactor was not stopped.")

        # Look at threads queue.
        if len(reactor.threadCallQueue) > 0:
            raise_failure("queued threads", reactor.threadCallQueue)

        if reactor.threadpool and len(reactor.threadpool.working) > 0:
            raise_failure("active threads", reactor.threadCallQueue)

        pool_queue = self._threadPoolQueue()
        if pool_queue:
            raise_failure("threadpoool queue", pool_queue)

        if self._threadPoolWorking():
            raise_failure("threadpoool working", self._threadPoolWorking())

        if self._threadPoolThreads():
            raise_failure("threadpoool threads", self._threadPoolThreads())

        if len(reactor.getWriters()) > 0:  # :cover
            raise_failure("writers", str(reactor.getWriters()))

        for reader in reactor.getReaders():
            excepted = False
            for reader_type in self.EXCEPTED_READERS:
                if isinstance(reader, reader_type):
                    excepted = True
                    break
            if not excepted:  # :cover
                raise_failure("readers", str(reactor.getReaders()))

        for delayed_call in reactor.getDelayedCalls():
            if delayed_call.active():
                delayed_str = self._getDelayedCallName(delayed_call)
                if delayed_str in self.EXCEPTED_DELAYED_CALLS:
                    continue
                raise_failure("delayed calls", delayed_str)

    def _runDeferred(self, deferred, timeout=None, debug=False, prevent_stop=False):
        """
        This is low level method. In most tests you would like to use
        `getDeferredFailure` or `getDeferredResult`.

        Run the deferred in the reactor loop.

        Starts the reactor, waits for deferred execution,
        raises error in timeout, stops the reactor.

        This will do recursive calls, in case the original deferred returns
        another deferred.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            self._runDeferred(deferred)

            self.assertIsNotFailure(deferred)
            self.assertEqual('something', deferred.result)
        """
        if not isinstance(deferred, Deferred):
            raise AssertionError("This is not a deferred.")

        if timeout is None:
            timeout = self.DEFERRED_TIMEOUT

        try:
            self._initiateTestReactor(timeout=timeout)
            self._executeDeferred(deferred, timeout, debug=debug)
        finally:
            self._shutdownTestReactor(prevent_stop=prevent_stop)

    def _executeDeferred(self, deferred, timeout, debug):
        """
        Does the actual deferred execution.
        """
        if not deferred.called:
            deferred_done = False
            while not deferred_done:
                self._iterateTestReactor(debug=debug)
                deferred_done = deferred.called

                if self._timeout_reached:
                    raise AssertionError(
                        "Deferred took more than %d to execute." % timeout
                    )

        # Check executing all deferred from chained callbacks.
        result = deferred.result
        while isinstance(result, Deferred):
            self._executeDeferred(result, timeout=timeout, debug=debug)
            result = deferred.result

    def _getDelayedCallName(self, delayed_call):
        """
        Return a string representation of the delayed call.
        """
        raw_name = str(delayed_call.func)
        raw_name = raw_name.replace("<function ", "")
        raw_name = raw_name.replace("<bound method ", "")
        return raw_name.split(" ", 1)[0].split(".")[-1]

    def getDeferredFailure(
        self, deferred, timeout=None, debug=False, prevent_stop=False
    ):
        """
        Run the deferred and return the failure.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            failure = self.getDeferredFailure(deferred)

            self.assertFailureType(AuthenticationError, failure)
        """
        self._runDeferred(
            deferred,
            timeout=timeout,
            debug=debug,
            prevent_stop=prevent_stop,
        )
        self.assertIsFailure(deferred)
        failure = deferred.result
        self.ignoreFailure(deferred)
        return failure

    def successResultOf(self, deferred):
        """
        Return the current success result of C{deferred} or raise
        C{self.failException}.

        @param deferred: A L{Deferred<twisted.internet.defer.Deferred>} which
            has a success result.  This means
            L{Deferred.callback<twisted.internet.defer.Deferred.callback>} or
            L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
            been called on it and it has reached the end of its callback chain
            and the last callback or errback returned a
            non-L{failure.Failure}.
        @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

        @raise SynchronousTestCase.failureException: If the
            L{Deferred<twisted.internet.defer.Deferred>} has no result or has
            a failure result.

        @return: The result of C{deferred}.
        """
        # FIXME:1370:
        # Remove / re-route this code after upgrading to Twisted 13.0.
        result = []
        deferred.addBoth(result.append)
        if not result:
            self.fail(
                "Success result expected on %r, found no result instead" % (deferred,)
            )
        elif isinstance(result[0], Failure):
            self.fail(
                "Success result expected on %r, "
                "found failure result instead:\n%s"
                % (deferred, result[0].getBriefTraceback())
            )
        else:
            return result[0]

    def failureResultOf(self, deferred, *expectedExceptionTypes):
        """
        Return the current failure result of C{deferred} or raise
        C{self.failException}.

        @param deferred: A L{Deferred<twisted.internet.defer.Deferred>} which
            has a failure result.  This means
            L{Deferred.callback<twisted.internet.defer.Deferred.callback>} or
            L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
            been called on it and it has reached the end of its callback chain
            and the last callback or errback raised an exception or returned a
            L{failure.Failure}.
        @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

        @param expectedExceptionTypes: Exception types to expect - if
            provided, and the the exception wrapped by the failure result is
            not one of the types provided, then this test will fail.

        @raise SynchronousTestCase.failureException: If the
            L{Deferred<twisted.internet.defer.Deferred>} has no result, has a
            success result, or has an unexpected failure result.

        @return: The failure result of C{deferred}.
        @rtype: L{failure.Failure}
        """
        # FIXME:1370:
        # Remove / re-route this code after upgrading to Twisted 13
        result = []
        deferred.addBoth(result.append)
        if not result:
            self.fail(
                "Failure result expected on %r, found no result instead" % (deferred,)
            )
        elif not isinstance(result[0], Failure):
            self.fail(
                "Failure result expected on %r, "
                "found success result (%r) instead" % (deferred, result[0])
            )
        elif expectedExceptionTypes and not result[0].check(*expectedExceptionTypes):
            expectedString = " or ".join(
                [".".join((t.__module__, t.__name__)) for t in expectedExceptionTypes]
            )

            self.fail(
                "Failure of type (%s) expected on %r, "
                "found type %r instead: %s"
                % (
                    expectedString,
                    deferred,
                    result[0].type,
                    result[0].getBriefTraceback(),
                )
            )
        else:
            return result[0]

    def assertNoResult(self, deferred):
        """
        Assert that C{deferred} does not have a result at this point.

        If the assertion succeeds, then the result of C{deferred} is left
        unchanged. Otherwise, any L{failure.Failure} result is swallowed.

        @param deferred: A L{Deferred<twisted.internet.defer.Deferred>}
            without a result.  This means that neither
            L{Deferred.callback<twisted.internet.defer.Deferred.callback>} nor
            L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
            been called, or that the
            L{Deferred<twisted.internet.defer.Deferred>} is waiting on another
            L{Deferred<twisted.internet.defer.Deferred>} for a result.
        @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

        @raise SynchronousTestCase.failureException: If the
            L{Deferred<twisted.internet.defer.Deferred>} has a result.
        """
        # FIXME:1370:
        # Remove / re-route this code after upgrading to Twisted 13
        result = []

        def cb(res):
            result.append(res)
            return res

        deferred.addBoth(cb)
        if result:
            # If there is already a failure, the self.fail below will
            # report it, so swallow it in the deferred
            deferred.addErrback(lambda _: None)
            self.fail(
                "No result expected on %r, found %r instead" % (deferred, result[0])
            )

    def getDeferredResult(
        self, deferred, timeout=None, debug=False, prevent_stop=False
    ):
        """
        Run the deferred and return the result.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            result = self.getDeferredResult(deferred)

            self.assertEqual('something', result)
        """
        self._runDeferred(
            deferred,
            timeout=timeout,
            debug=debug,
            prevent_stop=prevent_stop,
        )
        self.assertIsNotFailure(deferred)
        return deferred.result

    def assertWasCalled(self, deferred):
        """
        Check that deferred was called.
        """
        if not deferred.called:
            raise AssertionError("This deferred was not called yet.")

    def ignoreFailure(self, deferred):
        """
        Ignore the current failure on the deferred.

        It transforms an failure into result `None` so that the failure
        will not be raised at reactor shutdown for not being handled.
        """
        deferred.addErrback(lambda failure: None)

    def assertIsFailure(self, deferred):
        """
        Check that deferred is a failure.
        """
        if not isinstance(deferred.result, Failure):
            raise AssertionError("Deferred is not a failure.")

    def assertIsNotFailure(self, deferred):
        """
        Raise assertion error if deferred is a Failure.

        The failed deferred is handled by this method, to avoid propagating
        the error into the reactor.
        """
        self.assertWasCalled(deferred)

        if isinstance(deferred.result, Failure):
            error = deferred.result
            self.ignoreFailure(deferred)
            raise AssertionError("Deferred contains a failure: %s" % (error))
