# -*- test-case-name: twisted.trial.test.test_runner -*-

# Copyright (c) 2005 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Robert Collins <robertc@robertcollins.net>

import StringIO
from zope.interface import implements

from twisted.trial.itrial import IReporter
from twisted.trial import unittest, runner, reporter
from twisted.python import reflect
from twisted.scripts import trial


class CapturingDebugger(object):

    def __init__(self):
        self._calls = []

    def runcall(self, *args, **kwargs):
        self._calls.append('runcall')
        args[0](*args[1:], **kwargs)


class CapturingReporter(object):

    implements(IReporter)

    stream = None
    tbformat = None
    args = None
    separator = None
    testsRun = None

    def __init__(self, tbformat=None, args=None, realtime=None):
        """Create a capturing reporter."""
        self._calls = []
        self.shouldStop = False
        
    def startTest(self, method):
        """report the beginning of a run of a single test method
        @param method: an object that is adaptable to ITestMethod
        """
        self._calls.append('startTest')

    def stopTest(self, method):
        """report the status of a single test method
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


class TestImports(unittest.TestCase):

    def test_imports(self):
        from twisted.trial.runner import TrialRunner


class TestTrialRunner(unittest.TestCase):

    def setUp(self):
        self.stream = StringIO.StringIO()
        self.runner = runner.TrialRunner(CapturingReporter, stream=self.stream)
        self.test = TestImports('test_imports')

    def tearDown(self):
        self.runner._tearDownLogFile()
        
    def _getObservers(self):
        from twisted.python import log
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

class TestRunner(unittest.TestCase):
    
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.runners = []        
        self.config = trial.Options()
        # whitebox hack a reporter in, because plugins are CACHED and will
        # only reload if the FILE gets changed.
        self.config.optToQual['capturing'] = reflect.qual(CapturingReporter)
        self.standardReport = [
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            ]
        self.dryRunReport = [
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            'startTest',
            'addSuccess',
            'stopTest',
            ]

    def tearDown(self):
        for x in self.runners:
            x._tearDownLogFile()
        self.runners = []

    def parseOptions(self, args):
        self.config.parseOptions(args)

    def getRunner(self):
        r = trial._makeRunner(self.config)
        self.runners.append(r)
        return r
    
    def test_runner_can_get_reporter(self):
        self.parseOptions([])
        reporter = self.config['reporter']
        my_runner = self.getRunner()
        try:
            self.assertEqual(reporter, my_runner._makeResult().__class__)
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

    def test_runner_dry_run(self):
        self.parseOptions(['--dry-run', '--reporter', 'capturing',
                           'twisted.trial.test.sample'])
        my_runner = self.getRunner()
        loader = runner.TestLoader()
        suite = loader.loadByName('twisted.trial.test.sample', True)
        result = my_runner.run(suite)
        self.assertEqual(self.dryRunReport, result._calls)

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
        from twisted.trial.runner import TrialSuite

    # FIXME, HTF do you test the reactor can be cleaned up ?!!!


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
        
