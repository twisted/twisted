#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

"""
test twisted's doctest support
"""
import exceptions, sys

from twisted import trial
from twisted.trial import doctest, runner, tdoctest, unittest, reporter
from twisted.trial import itrial
from twisted.trial.reporter import  FAILURE, ERROR, SUCCESS
from twisted.trial.assertions import *
from twisted.python import failure

from twisted.trial.test import trialdoctest1, trialdoctest2, common

from pprint import pprint

import zope.interface as zi

class RegistryBaseMixin(common.RegistryBaseMixin):
    def setUp(self):
        super(RegistryBaseMixin, self).setUp()
        self.runners = []
        self.reporter.verify = lambda *a, **kw: None

    def tearDown(self):
        super(RegistryBaseMixin, self).tearDown()
        self.runners = None


class TestRunners(RegistryBaseMixin, unittest.TestCase):
    EXPECTED_STATI = ((SUCCESS, 5), (FAILURE, 1), (ERROR, 1))
    def setUpClass(self):
        if sys.version_info[0:2] == (2,2):
            raise SkipTest, 'doctest support only works on 2.3 or later'
        super(TestRunners, self).setUpClass()
    
    def setUp(self):
        super(TestRunners, self).setUp()
        self.doctests = trialdoctest2.__doctests__

    def tearDownClass(self):
        if sys.version_info[0:2] == (2,2):
            return
        super(TestRunners, self).tearDownClass()

    def tearDown(self):
        super(TestRunners, self).tearDown()

    def testDocTestRunnerRunTests(self):
        dtf = doctest.DocTestFinder()
        tests = dtf.find(trialdoctest1)

        methodsWithStatus = {}

        for test in tests:
            runner = itrial.ITestRunner(test)
            self.runners.append(runner)
            runner.parent = self
            runner.runTests()
            for k, v in runner.methodsWithStatus.iteritems():
                methodsWithStatus.setdefault(k, []).extend(v)
        self.verifyStatus(methodsWithStatus)


    def verifyStatus(self, mws, *expected):
        for status, lenMeths in expected:
            assert_(mws[status])
            assertEqual(len(mws[status]), lenMeths)

    def testModuleDocTestsRunner(self):
        mdtr = tdoctest.ModuleDocTestsRunner(self.doctests)
        mdtr.parent = self
        mdtr.runTests()
        self.verifyStatus(mdtr.methodsWithStatus, *self.EXPECTED_STATI)
#:        for line in self.reporter.out.split('\n'):
#:            print "\t%s" % (line,)

    def testSuite(self):
        self.suite.addModule(trialdoctest2)
        self.suite.run()

        # XXX: this children[idx] thing is pretty lame
        # it relies on the implementation of the suite, which is incorrect
        mws = self.suite.children[1].methodsWithStatus
        
        self.verifyStatus(mws, *self.EXPECTED_STATI)
        n = 0
        for v in mws.itervalues():
            n += len(v)

        # test to make sure correct count is reporterated
        assertSubstring("Ran %s tests in" % (n,), self.reporter.out)

    def testSingleDoctestFailure(self):
        self.suite.addDoctest(trialdoctest1.Counter.__eq__)
        self.suite.run()

        mws = self.suite.children[0].methodsWithStatus
        self.verifyStatus(mws, (FAILURE, 1))

    def testSingleDoctestSuccess(self):
        self.suite.addDoctest(trialdoctest1.Counter.incr)
        self.suite.run()

        mws = self.suite.children[0].methodsWithStatus
        self.verifyStatus(mws, (SUCCESS, 1))

    def testSingleDoctestError(self):
        self.suite.addDoctest(trialdoctest1.Counter.unexpectedException)
        self.suite.run()

        mws = self.suite.children[0].methodsWithStatus
        self.verifyStatus(mws, (ERROR, 1))

