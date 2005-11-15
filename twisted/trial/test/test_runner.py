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

    def endTrial(self, suite):
        """at the end of a test run report the overall status and print out
        any errors caught
        @param suite: an object implementing ITrialResult, can be adapted to
                      ITestStats
        """
        self._calls.append('endTrial')

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
        self.standardReport = ['startTrial',
                         'startSuite', 
                         'startSuite',
                         'startTest',
                         'addSuccess',
                         'stopTest',
                         'startTest',
                         'addSuccess',
                         'stopTest',
                         'startTest',
                         'addSuccess',
                         'stopTest',
                         'endSuite',
                         'startSuite',
                         'startTest',
                         'addSuccess',
                         'stopTest',
                         'startTest',
                         'addSuccess',
                         'stopTest',
                         'endSuite',
                         'startSuite',
                         'startTest',
                         'addSuccess',
                         'stopTest',
                         'startTest',
                         'addSuccess',
                         'stopTest',
                         'endSuite',
                         'endSuite',
                         'endTrial']
        self.dryRunReport = ['startTrial',
                         'startSuite', 
                         'startSuite',
                         'startTest',
                         'stopTest',
                         'startTest',
                         'stopTest',
                         'startTest',
                         'stopTest',
                         'endSuite',
                         'startSuite',
                         'startTest',
                         'stopTest',
                         'startTest',
                         'stopTest',
                         'endSuite',
                         'startSuite',
                         'startTest',
                         'stopTest',
                         'startTest',
                         'stopTest',
                         'endSuite',
                         'endSuite',
                         'endTrial']

    def parseOptions(self, args):
        self.config.parseOptions(args)
        os.chdir(self.config['_origdir'])
    
    def test_contruct_with_config(self):
        my_runner = runner.TrialRunner(self.config)
        self.assertEqual(self.config, my_runner._config)

    def test_runner_can_get_reporter(self):
        self.parseOptions([])
        reporter = self.config.getReporter()
        my_runner = runner.TrialRunner(self.config)
        self.assertEqual(reporter, my_runner._getResult())

    def test_runner_get_result(self):
        self.parseOptions([])
        self.config.getReporter()
        my_runner = runner.TrialRunner(self.config)
        result = my_runner._getResult()
        self.assertEqual(result, self.config._reporter)

    def test_runner_dry_run(self):
        self.parseOptions(['--dry-run', '--reporter', 'capturing',
                           'twisted.trial.test.sample'])
        reporter = self.config.getReporter()
        my_runner = runner.TrialRunner(self.config)
        loader = runner.SafeTestLoader()
        suite = loader.loadByName('twisted.trial.test.sample', True)
        result = my_runner.run(suite)
        self.assertEqual(self.dryRunReport, reporter._calls)

    def test_runner_normal(self):
        self.parseOptions(['--reporter', 'capturing',
                           'twisted.trial.test.sample'])
        reporter = self.config.getReporter()
        my_runner = runner.TrialRunner(self.config)
        loader = runner.SafeTestLoader()
        suite = loader.loadByName('twisted.trial.test.sample', True)
        result = my_runner.run(suite)
        self.assertEqual(self.standardReport, reporter._calls)

    def test_runner_debug(self):
        self.parseOptions(['--reporter', 'capturing',
                           '--debug', 'twisted.trial.test.sample'])
        reporter = self.config.getReporter()
        my_runner = runner.TrialRunner(self.config)
        debugger = CapturingDebugger()
        def get_debugger():
            return debugger
        my_runner._getDebugger = get_debugger
        loader = runner.SafeTestLoader()
        suite = loader.loadByName('twisted.trial.test.sample', True)
        result = my_runner.run(suite)
        self.assertEqual(self.standardReport, reporter._calls)
        self.assertEqual(['runcall'], debugger._calls)


class TestTrialSuite(unittest.TestCase):

    def test_imports(self):
        from twisted.trial.runner import TrialSuite

    # FIXME, HTF do you test the reactor can be cleaned up ?!!!
