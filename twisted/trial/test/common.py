# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import re, types
from cStringIO import StringIO

from twisted import trial
from twisted.trial import reporter, util, runner, unittest
from twisted.internet import defer
from twisted.trial.assertions import assertIdentical, assertEqual, assert_
from twisted.trial.assertions import assertSubstring

from twisted.python import components
import zope.interface as zi

FAILURE_MSG = "this test failed"

class FailfulTests(unittest.TestCase):
    def testTracebackReporting(self):
        1/0
    def testFailure(self):
        raise unittest.FailTest, FAILURE_MSG

class BaseTest(object):
    setUpCalled = tearDownCalled = setUpClassCalled = tearDownClassCalled = False
    methodCalled = False
    def setUpClass(self):
        self.setUpClassCalled = True

    def setUp(self):
        self.setUpCalled = True

    def tearDown(self):
        self.tearDownCalled = True

    def tearDownClass(self):
        self.tearDownClassCalled = True

    def testMethod(self):
        self.methodCalled = True


bogus = lambda *a, **kw: None

class BogusReporter(reporter.TreeReporter):
    tbformat = 'default'
    names = ('module', 'class', 'test')

    cleanerrs = importError = None
    setUpReporterCalled = tearDownReporterCalled = False
    
    def __init__(self):
        super(BogusReporter, self).__init__(StringIO(), 'default', None, False)
        self.startCtr = dict([(n, 0) for n in self.names])
        self.endCtr = self.startCtr.copy()

    out = property(lambda self:self.stream.getvalue())

    def setUpReporter(self):
        self.setUpReporterCalled = True
        return defer.succeed(None)

    def tearDownReporter(self):
        self.tearDownReporterCalled = True
        return defer.succeed(None)

    def startModule(self, mod):
        super(BogusReporter, self).startModule(mod)
        self.startCtr['module'] += 1
        self.module = mod

    def endModule(self, mod):
        super(BogusReporter, self).endModule(mod)
        self.endCtr['module'] += 1
        assertEqual(self.module, mod)

    def startClass(self, klass):
        super(BogusReporter, self).startClass(klass)
        self.startCtr['class'] += 1
        self.klass = klass

    def endClass(self, klass):
        super(BogusReporter, self).endClass(klass)
        self.endCtr['class'] += 1
        assertEqual(self.klass, klass)

    def startTest(self, tm):
        super(BogusReporter, self).startTest(tm)
        self.startCtr['test'] += 1
        self.tm = tm
        
    def endTest(self, tm):
        super(BogusReporter, self).endTest(tm)
        self.endCtr['test'] += 1
        assertEqual(self.tm, tm)

    def upDownError(self, method, warn=True, printStatus=True):
        super(BogusReporter, self).upDownError(method, False, printStatus)
        self.udeMethod = method

    def reportImportError(self, name, exc):
        self.importError = (name, exc)

    def cleanupErrors(self, errs):
        self.cleanerrs = errs

    def verify(self, failIfImportErrors=True, checkReporterSetup=True):
        if checkReporterSetup:
            for v in 'setUpReporterCalled', 'tearDownReporterCalled':
                assert_(getattr(self, v), 'self.%s did not evaluate to non-zero' % (v,))

        if failIfImportErrors:
            assert_(not self.importError)

        for n in self.names:
            assertEqual(self.startCtr[n], self.endCtr[n])


class RegistryBaseMixin(object):
    _suite = None

    # the following is a flag to the reporter.verify() method that gets reset to 
    # True after each testMethod. Most testMethods should not raise importErrors,
    # however, if a test needs to, and it is not an erroneous condition, the testMethod
    # should set this to False before the method returns
    failIfImportErrors = True

    # similar to the above attribute, this one checks to make sure
    # the reporter's setUp/tearDownReporter methods were called
    checkReporterSetup = True

    tci = property(lambda self: self.suite.children[0].testCaseInstance)
    tm = property(lambda self: self.suite.children[0].children[0])
    stdio = property(lambda self: self.tm.stderr + self.tm.stdout)

    def setUpClass(self):
        self.janitor = util._Janitor()

    def setUp(self):
        self.reporter = BogusReporter()

    def _getSuite(self, newSuite=False, benchmark=0):
        if self._suite is None or newSuite:
            self._suite = runner.TrialRoot(self.reporter, self.janitor, benchmark)
            self._suite._initLogging = bogus
            self._suite._setUpSigchldHandler = bogus
            self._suite._bail = bogus
        return self._suite
    def _setSuite(self, val):
        self._suite = val
    suite = property(_getSuite)

    def tearDown(self):
        self.reporter.verify(self.failIfImportErrors, self.checkReporterSetup)
        self.failIfImportErrors = True
        self._suite = None

    def getReporter(self):
        return self.reporter


REGEX_PATTERN_TYPE = type(re.compile(''))

def stringComparison(expect, output):
    """compares the list of strings in output to the list of objects in 
    expect. expect and output are not altered

    @param output: a list of strings, '' is ignored 
    @type output: list

    @param expect: a list of strings, None, or _sre.SRE_Pattern objects 
    (the object returned by re.compile()).
    
      - with string objects a simple == comparison is done
      - with regex objects, a match() is done and if there is no Match object
        returned, FailTest is raised
      - a None object causes a non blank string in output to be ignored

    @type expect: types.ListType
    """
    _expect, _output = expect[:], output[:]
    while 1:
        if not _output:
            return
        out = _output.pop(0)
        if out == '':
            continue
        else:
            if not _expect:
                return
            exp = _expect.pop(0)
            if exp is None:
                continue
            elif isinstance(exp, types.StringType):
                assertSubstring(exp, out)
            elif isinstance(exp, REGEX_PATTERN_TYPE):
                assert_(exp.match(out), "%r did not match string %r" % (exp.pattern, out))
            else:
                raise TypeError, "don't know what to do with object %r" % (exp,)
 
