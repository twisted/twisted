# -*- test-case-name: twisted.trial.test.test_runner -*-

# Copyright (c) 2005 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Robert Collins <robertc@robertcollins.net>

import os
from zope.interface import implements

from twisted.trial.itrial import IReporter
from twisted.trial import unittest, runner
from twisted.python import reflect
from twisted.scripts import trial
from twisted.plugins import twisted_trial


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
        
    def setUpReporter(self):
        """performs reporter setup. DEPRECATED"""
        self._calls.append('setUp')

    def tearDownReporter(self):
        """performs reporter termination. DEPRECATED"""
        self._calls.append('tearDown')

    def reportImportError(self, name, exc):
        """report an import error
        @param name: the name that could not be imported
        @param exc: the exception
        @type exc: L{twisted.python.failure.Failure}
        """
        self._calls.append('importError')

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

    def startTrial(self, expectedTests):
        """kick off this trial run
        @param expectedTests: the number of tests we expect to run
        """
        self._calls.append('startTrial')

    def startClass(self, klass):
        "called at the beginning of each TestCase with the class"
        self._calls.append('startClass')

    def endClass(self, klass):
        "called at the end of each TestCase with the class"
        self._calls.append('endClass')

    def startSuite(self, module):
        "called at the beginning of each module"
        self._calls.append('startSuite')

    def endSuite(self, module):
        "called at the end of each module"
        self._calls.append('endSuite')

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


class TestRunner(unittest.TestCase):
    
    def setUp(self):
        unittest.TestCase.setUp(self)
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
        
    def parseOptions(self, args):
        self.config.parseOptions(args)

    def getRunner(self):
        return trial._makeRunner(self.config)
    
    def test_runner_can_get_reporter(self):
        self.parseOptions([])
        reporter = self.config['reporter']
        my_runner = self.getRunner()
        self.assertEqual(reporter, my_runner._makeResult().__class__)

    def test_runner_get_result(self):
        self.parseOptions([])
        my_runner = self.getRunner()
        result = my_runner._makeResult()
        self.assertEqual(result.__class__, self.config['reporter'])

    def test_runner_working_directory(self):
        self.parseOptions(['--temp-directory', 'some_path'])
        runner = self.getRunner()
        self.assertEquals(runner.workingDirectory, 'some_path')

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
