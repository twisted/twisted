# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
#

"""
Tests for L{twisted.trial.util}
"""

import os

from zope.interface import implements

from twisted.internet.interfaces import IProcessTransport
from twisted.internet import defer
from twisted.internet.base import DelayedCall

from twisted.trial.unittest import TestCase
from twisted.trial import util
from twisted.trial.util import DirtyReactorAggregateError, _Janitor
from twisted.trial.test import packages



class TestMktemp(TestCase):
    def test_name(self):
        name = self.mktemp()
        dirs = os.path.dirname(name).split(os.sep)[:-1]
        self.failUnlessEqual(
            dirs, ['twisted.trial.test.test_util', 'TestMktemp', 'test_name'])

    def test_unique(self):
        name = self.mktemp()
        self.failIfEqual(name, self.mktemp())

    def test_created(self):
        name = self.mktemp()
        dirname = os.path.dirname(name)
        self.failUnless(os.path.exists(dirname))
        self.failIf(os.path.exists(name))

    def test_location(self):
        path = os.path.abspath(self.mktemp())
        self.failUnless(path.startswith(os.getcwd()))


class TestIntrospection(TestCase):
    def test_containers(self):
        import suppression
        parents = util.getPythonContainers(
            suppression.TestSuppression2.testSuppressModule)
        expected = [suppression.TestSuppression2, suppression]
        for a, b in zip(parents, expected):
            self.failUnlessEqual(a, b)


class TestFindObject(packages.SysPathManglingTest):
    """
    Tests for L{twisted.trial.util.findObject}
    """

    def test_deprecation(self):
        """
        Calling L{findObject} results in a deprecation warning
        """
        util.findObject('')
        warningsShown = self.flushWarnings()
        self.assertEquals(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEquals(warningsShown[0]['message'],
                          "twisted.trial.util.findObject was deprecated "
                          "in Twisted 10.1.0: Please use "
                          "twisted.python.reflect.namedAny instead.")


    def test_importPackage(self):
        package1 = util.findObject('package')
        import package as package2
        self.failUnlessEqual(package1, (True, package2))

    def test_importModule(self):
        test_sample2 = util.findObject('goodpackage.test_sample')
        from goodpackage import test_sample
        self.failUnlessEqual((True, test_sample), test_sample2)

    def test_importError(self):
        self.failUnlessRaises(ZeroDivisionError,
                              util.findObject, 'package.test_bad_module')

    def test_sophisticatedImportError(self):
        self.failUnlessRaises(ImportError,
                              util.findObject, 'package2.test_module')

    def test_importNonexistentPackage(self):
        self.failUnlessEqual(util.findObject('doesntexist')[0], False)

    def test_findNonexistentModule(self):
        self.failUnlessEqual(util.findObject('package.doesntexist')[0], False)

    def test_findNonexistentObject(self):
        self.failUnlessEqual(util.findObject(
            'goodpackage.test_sample.doesnt')[0], False)
        self.failUnlessEqual(util.findObject(
            'goodpackage.test_sample.AlphabetTest.doesntexist')[0], False)

    def test_findObjectExist(self):
        alpha1 = util.findObject('goodpackage.test_sample.AlphabetTest')
        from goodpackage import test_sample
        self.failUnlessEqual(alpha1, (True, test_sample.AlphabetTest))



class TestRunSequentially(TestCase):
    """
    Sometimes it is useful to be able to run an arbitrary list of callables,
    one after the other.

    When some of those callables can return Deferreds, things become complex.
    """

    def test_emptyList(self):
        """
        When asked to run an empty list of callables, runSequentially returns a
        successful Deferred that fires an empty list.
        """
        d = util._runSequentially([])
        d.addCallback(self.assertEqual, [])
        return d


    def test_singleSynchronousSuccess(self):
        """
        When given a callable that succeeds without returning a Deferred,
        include the return value in the results list, tagged with a SUCCESS
        flag.
        """
        d = util._runSequentially([lambda: None])
        d.addCallback(self.assertEqual, [(defer.SUCCESS, None)])
        return d


    def test_singleSynchronousFailure(self):
        """
        When given a callable that raises an exception, include a Failure for
        that exception in the results list, tagged with a FAILURE flag.
        """
        d = util._runSequentially([lambda: self.fail('foo')])
        def check(results):
            [(flag, fail)] = results
            fail.trap(self.failureException)
            self.assertEqual(fail.getErrorMessage(), 'foo')
            self.assertEqual(flag, defer.FAILURE)
        return d.addCallback(check)


    def test_singleAsynchronousSuccess(self):
        """
        When given a callable that returns a successful Deferred, include the
        result of the Deferred in the results list, tagged with a SUCCESS flag.
        """
        d = util._runSequentially([lambda: defer.succeed(None)])
        d.addCallback(self.assertEqual, [(defer.SUCCESS, None)])
        return d


    def test_singleAsynchronousFailure(self):
        """
        When given a callable that returns a failing Deferred, include the
        failure the results list, tagged with a FAILURE flag.
        """
        d = util._runSequentially([lambda: defer.fail(ValueError('foo'))])
        def check(results):
            [(flag, fail)] = results
            fail.trap(ValueError)
            self.assertEqual(fail.getErrorMessage(), 'foo')
            self.assertEqual(flag, defer.FAILURE)
        return d.addCallback(check)


    def test_callablesCalledInOrder(self):
        """
        Check that the callables are called in the given order, one after the
        other.
        """
        log = []
        deferreds = []

        def append(value):
            d = defer.Deferred()
            log.append(value)
            deferreds.append(d)
            return d

        d = util._runSequentially([lambda: append('foo'),
                                   lambda: append('bar')])

        # runSequentially should wait until the Deferred has fired before
        # running the second callable.
        self.assertEqual(log, ['foo'])
        deferreds[-1].callback(None)
        self.assertEqual(log, ['foo', 'bar'])

        # Because returning created Deferreds makes jml happy.
        deferreds[-1].callback(None)
        return d


    def test_continuesAfterError(self):
        """
        If one of the callables raises an error, then runSequentially continues
        to run the remaining callables.
        """
        d = util._runSequentially([lambda: self.fail('foo'), lambda: 'bar'])
        def check(results):
            [(flag1, fail), (flag2, result)] = results
            fail.trap(self.failureException)
            self.assertEqual(flag1, defer.FAILURE)
            self.assertEqual(fail.getErrorMessage(), 'foo')
            self.assertEqual(flag2, defer.SUCCESS)
            self.assertEqual(result, 'bar')
        return d.addCallback(check)


    def test_stopOnFirstError(self):
        """
        If the C{stopOnFirstError} option is passed to C{runSequentially}, then
        no further callables are called after the first exception is raised.
        """
        d = util._runSequentially([lambda: self.fail('foo'), lambda: 'bar'],
                                  stopOnFirstError=True)
        def check(results):
            [(flag1, fail)] = results
            fail.trap(self.failureException)
            self.assertEqual(flag1, defer.FAILURE)
            self.assertEqual(fail.getErrorMessage(), 'foo')
        return d.addCallback(check)


    def test_stripFlags(self):
        """
        If the C{stripFlags} option is passed to C{runSequentially} then the
        SUCCESS / FAILURE flags are stripped from the output. Instead, the
        Deferred fires a flat list of results containing only the results and
        failures.
        """
        d = util._runSequentially([lambda: self.fail('foo'), lambda: 'bar'],
                                  stripFlags=True)
        def check(results):
            [fail, result] = results
            fail.trap(self.failureException)
            self.assertEqual(fail.getErrorMessage(), 'foo')
            self.assertEqual(result, 'bar')
        return d.addCallback(check)
    test_stripFlags.todo = "YAGNI"



class DirtyReactorAggregateErrorTest(TestCase):
    """
    Tests for the L{DirtyReactorAggregateError}.
    """

    def test_formatDelayedCall(self):
        """
        Delayed calls are formatted nicely.
        """
        error = DirtyReactorAggregateError(["Foo", "bar"])
        self.assertEquals(str(error),
                          """\
Reactor was unclean.
DelayedCalls: (set twisted.internet.base.DelayedCall.debug = True to debug)
Foo
bar""")


    def test_formatSelectables(self):
        """
        Selectables are formatted nicely.
        """
        error = DirtyReactorAggregateError([], ["selectable 1", "selectable 2"])
        self.assertEquals(str(error),
                          """\
Reactor was unclean.
Selectables:
selectable 1
selectable 2""")


    def test_formatDelayedCallsAndSelectables(self):
        """
        Both delayed calls and selectables can appear in the same error.
        """
        error = DirtyReactorAggregateError(["bleck", "Boozo"],
                                           ["Sel1", "Sel2"])
        self.assertEquals(str(error),
                          """\
Reactor was unclean.
DelayedCalls: (set twisted.internet.base.DelayedCall.debug = True to debug)
bleck
Boozo
Selectables:
Sel1
Sel2""")



class StubReactor(object):
    """
    A reactor stub which contains enough functionality to be used with the
    L{_Janitor}.

    @ivar iterations: A list of the arguments passed to L{iterate}.
    @ivar removeAllCalled: Number of times that L{removeAll} was called.
    @ivar selectables: The value that will be returned from L{removeAll}.
    @ivar delayedCalls: The value to return from L{getDelayedCalls}.
    """

    def __init__(self, delayedCalls, selectables=None):
        """
        @param delayedCalls: See L{StubReactor.delayedCalls}.
        @param selectables: See L{StubReactor.selectables}.
        """
        self.delayedCalls = delayedCalls
        self.iterations = []
        self.removeAllCalled = 0
        if not selectables:
            selectables = []
        self.selectables = selectables


    def iterate(self, timeout=None):
        """
        Increment C{self.iterations}.
        """
        self.iterations.append(timeout)


    def getDelayedCalls(self):
        """
        Return C{self.delayedCalls}.
        """
        return self.delayedCalls


    def removeAll(self):
        """
        Increment C{self.removeAllCalled} and return C{self.selectables}.
        """
        self.removeAllCalled += 1
        return self.selectables



class StubErrorReporter(object):
    """
    A subset of L{twisted.trial.itrial.IReporter} which records L{addError}
    calls.

    @ivar errors: List of two-tuples of (test, error) which were passed to
        L{addError}.
    """

    def __init__(self):
        self.errors = []


    def addError(self, test, error):
        """
        Record parameters in C{self.errors}.
        """
        self.errors.append((test, error))



class JanitorTests(TestCase):
    """
    Tests for L{_Janitor}!
    """

    def test_cleanPendingSpinsReactor(self):
        """
        During pending-call cleanup, the reactor will be spun twice with an
        instant timeout. This is not a requirement, it is only a test for
        current behavior. Hopefully Trial will eventually not do this kind of
        reactor stuff.
        """
        reactor = StubReactor([])
        jan = _Janitor(None, None, reactor=reactor)
        jan._cleanPending()
        self.assertEquals(reactor.iterations, [0, 0])


    def test_cleanPendingCancelsCalls(self):
        """
        During pending-call cleanup, the janitor cancels pending timed calls.
        """
        def func():
            return "Lulz"
        cancelled = []
        delayedCall = DelayedCall(300, func, (), {},
                                  cancelled.append, lambda x: None)
        reactor = StubReactor([delayedCall])
        jan = _Janitor(None, None, reactor=reactor)
        jan._cleanPending()
        self.assertEquals(cancelled, [delayedCall])


    def test_cleanPendingReturnsDelayedCallStrings(self):
        """
        The Janitor produces string representations of delayed calls from the
        delayed call cleanup method. It gets the string representations
        *before* cancelling the calls; this is important because cancelling the
        call removes critical debugging information from the string
        representation.
        """
        delayedCall = DelayedCall(300, lambda: None, (), {},
                                  lambda x: None, lambda x: None,
                                  seconds=lambda: 0)
        delayedCallString = str(delayedCall)
        reactor = StubReactor([delayedCall])
        jan = _Janitor(None, None, reactor=reactor)
        strings = jan._cleanPending()
        self.assertEquals(strings, [delayedCallString])


    def test_cleanReactorRemovesSelectables(self):
        """
        The Janitor will remove selectables during reactor cleanup.
        """
        reactor = StubReactor([])
        jan = _Janitor(None, None, reactor=reactor)
        jan._cleanReactor()
        self.assertEquals(reactor.removeAllCalled, 1)


    def test_cleanReactorKillsProcesses(self):
        """
        The Janitor will kill processes during reactor cleanup.
        """
        class StubProcessTransport(object):
            """
            A stub L{IProcessTransport} provider which records signals.
            @ivar signals: The signals passed to L{signalProcess}.
            """
            implements(IProcessTransport)

            def __init__(self):
                self.signals = []

            def signalProcess(self, signal):
                """
                Append C{signal} to C{self.signals}.
                """
                self.signals.append(signal)

        pt = StubProcessTransport()
        reactor = StubReactor([], [pt])
        jan = _Janitor(None, None, reactor=reactor)
        jan._cleanReactor()
        self.assertEquals(pt.signals, ["KILL"])


    def test_cleanReactorReturnsSelectableStrings(self):
        """
        The Janitor returns string representations of the selectables that it
        cleaned up from the reactor cleanup method.
        """
        class Selectable(object):
            """
            A stub Selectable which only has an interesting string
            representation.
            """
            def __repr__(self):
                return "(SELECTABLE!)"

        reactor = StubReactor([], [Selectable()])
        jan = _Janitor(None, None, reactor=reactor)
        self.assertEquals(jan._cleanReactor(), ["(SELECTABLE!)"])


    def test_postCaseCleanupNoErrors(self):
        """
        The post-case cleanup method will return True and not call C{addError}
        on the result if there are no pending calls.
        """
        reactor = StubReactor([])
        test = object()
        reporter = StubErrorReporter()
        jan = _Janitor(test, reporter, reactor=reactor)
        self.assertTrue(jan.postCaseCleanup())
        self.assertEquals(reporter.errors, [])


    def test_postCaseCleanupWithErrors(self):
        """
        The post-case cleanup method will return False and call C{addError} on
        the result with a L{DirtyReactorAggregateError} Failure if there are
        pending calls.
        """
        delayedCall = DelayedCall(300, lambda: None, (), {},
                                  lambda x: None, lambda x: None,
                                  seconds=lambda: 0)
        delayedCallString = str(delayedCall)
        reactor = StubReactor([delayedCall], [])
        test = object()
        reporter = StubErrorReporter()
        jan = _Janitor(test, reporter, reactor=reactor)
        self.assertFalse(jan.postCaseCleanup())
        self.assertEquals(len(reporter.errors), 1)
        self.assertEquals(reporter.errors[0][1].value.delayedCalls,
                          [delayedCallString])


    def test_postClassCleanupNoErrors(self):
        """
        The post-class cleanup method will not call C{addError} on the result
        if there are no pending calls or selectables.
        """
        reactor = StubReactor([])
        test = object()
        reporter = StubErrorReporter()
        jan = _Janitor(test, reporter, reactor=reactor)
        jan.postClassCleanup()
        self.assertEquals(reporter.errors, [])


    def test_postClassCleanupWithPendingCallErrors(self):
        """
        The post-class cleanup method call C{addError} on the result with a
        L{DirtyReactorAggregateError} Failure if there are pending calls.
        """
        delayedCall = DelayedCall(300, lambda: None, (), {},
                                  lambda x: None, lambda x: None,
                                  seconds=lambda: 0)
        delayedCallString = str(delayedCall)
        reactor = StubReactor([delayedCall], [])
        test = object()
        reporter = StubErrorReporter()
        jan = _Janitor(test, reporter, reactor=reactor)
        jan.postClassCleanup()
        self.assertEquals(len(reporter.errors), 1)
        self.assertEquals(reporter.errors[0][1].value.delayedCalls,
                          [delayedCallString])


    def test_postClassCleanupWithSelectableErrors(self):
        """
        The post-class cleanup method call C{addError} on the result with a
        L{DirtyReactorAggregateError} Failure if there are selectables.
        """
        selectable = "SELECTABLE HERE"
        reactor = StubReactor([], [selectable])
        test = object()
        reporter = StubErrorReporter()
        jan = _Janitor(test, reporter, reactor=reactor)
        jan.postClassCleanup()
        self.assertEquals(len(reporter.errors), 1)
        self.assertEquals(reporter.errors[0][1].value.selectables,
                          [repr(selectable)])

