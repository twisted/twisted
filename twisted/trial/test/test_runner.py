# -*- test-case-name: twisted.trial.test.test_runner -*-

# Copyright (c) 2005 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Maintainer: Jonathan Lange <jml@twistedmatrix.com>
# Author: Robert Collins <robertc@robertcollins.net>


import StringIO
from zope.interface import implements

from twisted.trial.itrial import IReporter
from twisted.trial import unittest, runner, reporter
from twisted.python import failure, log, reflect
from twisted.scripts import trial
from twisted.plugins import twisted_trial
from twisted import plugin


pyunit = __import__('unittest')


class CapturingDebugger(object):

    def __init__(self):
        self._calls = []

    def runcall(self, *args, **kwargs):
        self._calls.append('runcall')
        args[0](*args[1:], **kwargs)



class CapturingReporter(object):
    """
    Reporter that keeps a log of all actions performed on it.
    """

    implements(IReporter)

    stream = None
    tbformat = None
    args = None
    separator = None
    testsRun = None

    def __init__(self, tbformat=None, args=None, realtime=None):
        """
        Create a capturing reporter.
        """
        self._calls = []
        self.shouldStop = False


    def startTest(self, method):
        """
        Report the beginning of a run of a single test method
        @param method: an object that is adaptable to ITestMethod
        """
        self._calls.append('startTest')


    def stopTest(self, method):
        """
        Report the status of a single test method
        @param method: an object that is adaptable to ITestMethod
        """
        self._calls.append('stopTest')


    def cleanupErrors(self, errs):
        """called when the reactor has been left in a 'dirty' state
        @param errs: a list of L{twisted.python.failure.Failure}s
        """
        self._calls.append('cleanupError')


    def upDownError(self, userMeth, warn=True, printStatus=True):
        """called when an error occurs in a setUp* or tearDown* method
        @param warn: indicates whether or not the reporter should emit a
                     warning about the error
        @type warn: Boolean
        @param printStatus: indicates whether or not the reporter should
                            print the name of the method and the status
                            message appropriate for the type of error
        @type printStatus: Boolean
        """
        self._calls.append('upDownError')


    def addSuccess(self, test):
        self._calls.append('addSuccess')


    def printErrors(self):
        pass


    def printSummary(self):
        pass


    def write(self, *args, **kw):
        pass


    def writeln(self, *args, **kw):
        pass



class TestTrialRunner(unittest.TestCase):

    def setUp(self):
        self.stream = StringIO.StringIO()
        self.runner = runner.TrialRunner(CapturingReporter, stream=self.stream)
        self.test = TestTrialRunner('test_empty')

    def test_empty(self):
        """
        Empty test method, used by the other tests.
        """

    def tearDown(self):
        self.runner._tearDownLogFile()

    def _getObservers(self):
        return log.theLogPublisher.observers

    def test_addObservers(self):
        originalCount = len(self._getObservers())
        self.runner.run(self.test)
        newCount = len(self._getObservers())
        self.failUnlessEqual(originalCount + 2, newCount)

    def test_addObservers_repeat(self):
        self.runner.run(self.test)
        count = len(self._getObservers())
        self.runner.run(self.test)
        newCount = len(self._getObservers())
        self.failUnlessEqual(count, newCount)

    def test_logFileAlwaysActive(self):
        """test that a new file is opened on each run"""
        self.runner.run(self.test)
        fd = self.runner._logFileObserver
        self.runner.run(self.test)
        fd2 = self.runner._logFileObserver
        self.failIf(fd is fd2, "Should have created a new file observer")

    def test_logFileGetsClosed(self):
        self.runner.run(self.test)
        fd = self.runner._logFileObject
        self.runner.run(self.test)
        self.failUnless(fd.closed)



class DryRunMixin(object):
    def setUp(self):
        self.log = []
        self.stream = StringIO.StringIO()
        self.runner = runner.TrialRunner(CapturingReporter,
                                         runner.TrialRunner.DRY_RUN,
                                         stream=self.stream)
        self.makeTestFixtures()


    def makeTestFixtures(self):
        """
        Set C{self.test} and C{self.suite}, where C{self.suite} is an empty
        TestSuite.
        """


    def test_empty(self):
        """
        If there are no tests, the reporter should not receive any events to
        report.
        """
        result = self.runner.run(runner.TestSuite())
        self.assertEqual(result._calls, [])


    def test_singleCaseReporting(self):
        """
        If we are running a single test, check the reporter starts, passes and
        then stops the test during a dry run.
        """
        result = self.runner.run(self.test)
        self.assertEqual(result._calls, ['startTest', 'addSuccess', 'stopTest'])


    def test_testsNotRun(self):
        """
        When we are doing a dry run, the tests should not actually be run.
        """
        self.runner.run(self.test)
        self.assertEqual(self.log, [])




class DryRunTest(DryRunMixin, unittest.TestCase):
    """
    Check that 'dry run' mode works well with Trial tests.
    """
    def makeTestFixtures(self):
        class MockTest(unittest.TestCase):
            def test_foo(test):
                self.log.append('test_foo')
        self.test = MockTest('test_foo')
        self.suite = runner.TestSuite()



class PyUnitDryRunTest(DryRunMixin, unittest.TestCase):
    """
    Check that 'dry run' mode works well with stdlib unittest tests.
    """
    def makeTestFixtures(self):
        class PyunitCase(pyunit.TestCase):
            def test_foo(self):
                pass
        self.test = PyunitCase('test_foo')
        self.suite = pyunit.TestSuite()



class TestRunner(unittest.TestCase):

    def setUp(self):
        self.runners = []
        self.config = trial.Options()
        # whitebox hack a reporter in, because plugins are CACHED and will
        # only reload if the FILE gets changed.

        parts = reflect.qual(CapturingReporter).split('.')
        package = '.'.join(parts[:-1])
        klass = parts[-1]
        plugins = [twisted_trial._Reporter(
            "Test Helper Reporter",
            package,
            description="Utility for unit testing.",
            longOpt="capturing",
            shortOpt=None,
            klass=klass)]


        # XXX There should really be a general way to hook the plugin system
        # for tests.
        def getPlugins(iface, *a, **kw):
            self.assertEqual(iface, IReporter)
            return plugins + list(self.original(iface, *a, **kw))

        self.original = plugin.getPlugins
        plugin.getPlugins = getPlugins

        self.standardReport = ['startTest', 'addSuccess', 'stopTest',
                               'startTest', 'addSuccess', 'stopTest',
                               'startTest', 'addSuccess', 'stopTest',
                               'startTest', 'addSuccess', 'stopTest',
                               'startTest', 'addSuccess', 'stopTest',
                               'startTest', 'addSuccess', 'stopTest',
                               'startTest', 'addSuccess', 'stopTest']


    def tearDown(self):
        for x in self.runners:
            x._tearDownLogFile()
        self.runners = []
        plugin.getPlugins = self.original


    def parseOptions(self, args):
        self.config.parseOptions(args)

    def getRunner(self):
        r = trial._makeRunner(self.config)
        self.runners.append(r)
        return r

    def test_runner_can_get_reporter(self):
        self.parseOptions([])
        result = self.config['reporter']
        my_runner = self.getRunner()
        try:
            self.assertEqual(result, my_runner._makeResult().__class__)
        finally:
            my_runner._tearDownLogFile()

    def test_runner_get_result(self):
        self.parseOptions([])
        my_runner = self.getRunner()
        result = my_runner._makeResult()
        self.assertEqual(result.__class__, self.config['reporter'])

    def test_runner_working_directory(self):
        self.parseOptions(['--temp-directory', 'some_path'])
        runner = self.getRunner()
        try:
            self.assertEquals(runner.workingDirectory, 'some_path')
        finally:
            runner._tearDownLogFile()

    def test_runner_normal(self):
        self.parseOptions(['--temp-directory', self.mktemp(),
                           '--reporter', 'capturing',
                           'twisted.trial.test.sample'])
        my_runner = self.getRunner()
        loader = runner.TestLoader()
        suite = loader.loadByName('twisted.trial.test.sample', True)
        result = my_runner.run(suite)
        self.assertEqual(self.standardReport, result._calls)

    def test_runner_debug(self):
        self.parseOptions(['--reporter', 'capturing',
                           '--debug', 'twisted.trial.test.sample'])
        my_runner = self.getRunner()
        debugger = CapturingDebugger()
        def get_debugger():
            return debugger
        my_runner._getDebugger = get_debugger
        loader = runner.TestLoader()
        suite = loader.loadByName('twisted.trial.test.sample', True)
        result = my_runner.run(suite)
        self.assertEqual(self.standardReport, result._calls)
        self.assertEqual(['runcall'], debugger._calls)



class TestTrialSuite(unittest.TestCase):

    def test_imports(self):
        # FIXME, HTF do you test the reactor can be cleaned up ?!!!
        from twisted.trial.runner import TrialSuite
        # silence pyflakes warning
        silencePyflakes = TrialSuite



class TestUntilFailure(unittest.TestCase):
    class FailAfter(unittest.TestCase):
        count = []
        def test_foo(self):
            self.count.append(None)
            if len(self.count) == 3:
                self.fail('Count reached 3')

    def setUp(self):
        TestUntilFailure.FailAfter.count = []
        self.test = TestUntilFailure.FailAfter('test_foo')

    def test_runUntilFailure(self):
        stream = StringIO.StringIO()
        trialRunner = runner.TrialRunner(reporter.Reporter, stream=stream)
        result = trialRunner.runUntilFailure(self.test)
        self.failUnlessEqual(result.testsRun, 1)
        self.failIf(result.wasSuccessful())
        self.failUnlessEqual(len(result.failures), 1)



class BreakingSuite(runner.TestSuite):
    """
    A L{TestSuite} that logs an error when it is run.
    """

    def run(self, result):
        try:
            raise RuntimeError("error that occurs outside of a test")
        except RuntimeError, e:
            log.err(failure.Failure())



class TestLoggedErrors(unittest.TestCase):
    """
    It is possible for an error generated by a test to be logged I{outside} of
    any test. The log observers constructed by L{TestCase} won't catch these
    errors. Here we try to generate such errors and ensure they are reported to
    a L{TestResult} object.
    """

    def tearDown(self):
        self.flushLoggedErrors(RuntimeError)


    def test_construct(self):
        """
        Check that we can construct a L{runner.LoggedSuite} and that it
        starts empty.
        """
        suite = runner.LoggedSuite()
        self.assertEqual(suite.countTestCases(), 0)


    def test_capturesError(self):
        """
        Chek that a L{LoggedSuite} reports any logged errors to its result.
        """
        result = reporter.TestResult()
        suite = runner.LoggedSuite([BreakingSuite()])
        suite.run(result)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0][0].id(), runner.NOT_IN_TEST)
        self.failUnless(result.errors[0][1].check(RuntimeError))



class TestTestHolder(unittest.TestCase):

    def setUp(self):
        self.description = "description"
        self.holder = runner.TestHolder(self.description)


    def test_holder(self):
        """
        Check that L{runner.TestHolder} takes a description as a parameter
        and that this description is returned by the C{id} and
        C{shortDescription} methods.
        """
        self.assertEqual(self.holder.id(), self.description)
        self.assertEqual(self.holder.shortDescription(), self.description)



class TestErrorHolder(TestTestHolder):
    """
    Test L{runner.ErrorHolder} shares behaviour with L{runner.TestHolder}.
    """

    def setUp(self):
        self.description = "description"
        # make a real Failure so we can construct ErrorHolder()
        try:
            1/0
        except ZeroDivisionError:
            error = failure.Failure()
        self.holder = runner.ErrorHolder(self.description, error)
