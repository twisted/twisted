# -*- test-case-name: twisted.trial.test.test_adapters -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import re, os, sys

from twisted.trial.test import erroneous, common
from twisted.trial import adapters, itrial, unittest, reporter
from twisted.trial.assertions import *
from twisted.python import failure

from pprint import pformat, pprint

class BogusError(Exception):
    pass

ERROR_MSG = "i did something dumb"

def gimmeAFailure():
    f = None
    try:
        raise BogusError, ERROR_MSG
    except:
        f = failure.Failure()
    return f

expectGimmieAFailure = [re.compile(r'.*test_adapters.py.*in gimmeAFailure'),
                        re.compile(r'.*BogusError.*'),
                        re.compile(r'.*test_adapters\.BogusError: %s' % (ERROR_MSG,))]

re_psep = re.escape(os.sep)

expectFailureInSetUp = [re.compile(r'.*twisted%(sep)sinternet%(sep)sdefer.py.*maybeDeferred' % {'sep': re_psep}), # XXX: this may break
                        None,
                        re.compile(r'.*test%(sep)serroneous.py.*in setUp' % {'sep': re_psep}),
                        re.compile(r'.*raise FoolishError.*'),
                        re.compile(r'.*erroneous.FoolishError: I am a broken setUp method')]

expectTestFailure = [reporter.DOUBLE_SEPARATOR,
                     '[FAIL]: testFailure (twisted.trial.test.common.FailfulTests)',
                     None,
                     None,
                     re.compile(r'.*common.py.*in testFailure'),
                     None,
                     'twisted.trial.assertions.FailTest: %s' % (common.FAILURE_MSG,)]

class TestFailureFormatting(common.RegistryBaseMixin, unittest.TestCase):
    def tearDown(self):
        if sys.version_info[0:2] == (2,2):
            self.registry._clearAdapterRegistry()
            self._suite = None
            return
        super(TestFailureFormatting, self).tearDown()

    def testNoExceptionCaughtHere(self):
        #test formatting of a traceback without a failure.EXCEPTION_CAUGHT_HERE line
        self.checkReporterSetup = False

        f = gimmeAFailure()

        output = adapters.formatFailureTraceback(f).split('\n')
        common.stringComparison(expectGimmieAFailure, output)

    def testExceptionCaughtHere(self):
        #test formatting of a traceback with a failure.EXCEPTION_CAUGHT_HERE line
        self.suite.addTestClass(erroneous.TestFailureInSetUp)
        self.suite.run()

        output = adapters.formatFailureTraceback(self.tm.errors[0]).split('\n')
        
        common.stringComparison(expectFailureInSetUp, output)

    def testMultilpeFailureTracebacks(self):
        self.checkReporterSetup = False
        L = []

        self.suite.addTestClass(erroneous.TestFailureInSetUp)
        self.suite.run()
        L.append(self.tm.errors[0])
        L.append(gimmeAFailure())

        output = adapters.formatMultipleFailureTracebacks(L).split('\n')

        common.stringComparison(expectFailureInSetUp + expectGimmieAFailure, output)
        assertEqual(adapters.formatMultipleFailureTracebacks([]), '')
        
    def testFormatTestMethodFailures(self):
        self.suite.addTestClass(erroneous.TestFailureInSetUp)
        self.suite.run()

        self.tm.errors.append(gimmeAFailure())

        output = adapters.formatTestMethodFailures(self.tm).split('\n')
        
        common.stringComparison(expectFailureInSetUp + expectGimmieAFailure, output)

    def testFormatErroredMethod(self):
        self.suite.addTestClass(erroneous.TestFailureInSetUp)
        self.suite.run()
        
        output = adapters.formatError(self.tm).split('\n')
        
        expect = [reporter.DOUBLE_SEPARATOR,
                  '[ERROR]: testMethod (twisted.trial.test.erroneous.TestFailureInSetUp)']

        expect.extend(expectFailureInSetUp)

        common.stringComparison(expect, output)

    def testFormatFailedMethod(self):
        self.suite.addMethod(common.FailfulTests.testFailure)
        self.suite.run()

        output = adapters.formatError(self.tm).split('\n')
        common.stringComparison(expectTestFailure, output)

    def testTrimFilename(self):
        self.checkReporterSetup = False
        path = os.sep.join(['foo', 'bar', 'baz', 'spam', 'spunk'])

        out = adapters.trimFilename(path, 3)
        s = "...%s" % (os.sep.join(['baz','spam','spunk']),)
        assertEqual(out, s)
        
        out = adapters.trimFilename(path, 10)
        s = os.sep.join(['foo','bar','baz','spam','spunk'])
        assertEqual(out, s)

    def testDoctestError(self):
        if sys.version_info[0:2] == (2,2):
            raise unittest.SkipTest, 'doctest support only works on 2.3 or later'
        from twisted.trial.test import trialdoctest1
        self.suite.addDoctest(trialdoctest1.Counter.unexpectedException)
        self.suite.run()

        itm = itrial.ITestMethod(self.suite.children[0].children[0])

        output = adapters.formatDoctestError(itm).split('\n')

        expect = [reporter.DOUBLE_SEPARATOR,
                  '[ERROR]: unexpectedException (...%s)' % (os.path.join('twisted', 'trial', 'test', 'trialdoctest1.py'),),
                  'docstring',
                  '---------',
                  '--> >>> 1/0',
                  'Traceback (most recent call last):',
                  None,
                  None,
                  re.compile('.*File.*doctest unexpectedException.*line 1.*in.*'),
                  re.compile('.*1/0'),
                  'ZeroDivisionError: integer division or modulo by zero']

        common.stringComparison(expect, output)

    def testImportError(self):
        self.failIfImportErrors = False
        # Add a module that fails to import
        if modname in sys.modules:
            # Previous tests might leave this hanging around in Python < 2.4.
            del sys.modules['twisted.trial.test.importErrors']
        self.suite.addModule('twisted.trial.test.importErrors')
        self.suite.run()

        output = self.reporter.out.split('\n')

        expect = [reporter.DOUBLE_SEPARATOR,
                  'IMPORT ERROR:']
        
        common.stringComparison(expect, output)

