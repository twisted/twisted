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
    
    def __init__(self):
        super(BogusReporter, self).__init__(StringIO(), 'default', None, False)

    out = property(lambda self:self.stream.getvalue())

    def upDownError(self, method, warn=True, printStatus=True):
        super(BogusReporter, self).upDownError(method, False, printStatus)
        self.udeMethod = method

    def reportImportError(self, name, exc):
        self.importError = (name, exc)

    def cleanupErrors(self, errs):
        self.cleanerrs = errs


class RegistryBaseMixin(object):
    _suite = None

    def setUpClass(self):
        self.janitor = util._Janitor()

    def setUp(self):
        self.reporter = BogusReporter()

    def _getSuite(self, newSuite=False):
        if self._suite is None or newSuite:
            self._suite = runner.TrialRoot(self.reporter)
            self._suite._initLogging = bogus
            self._suite._setUpSigchldHandler = bogus
            self._suite._bail = bogus
        return self._suite
    def _setSuite(self, val):
        self._suite = val
    suite = property(_getSuite, _setSuite)

    def tearDown(self):
        self._suite = None

    def getReporter(self):
        return self.reporter

    def stringComparison(self, expect, output):
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
        REGEX_PATTERN_TYPE = type(re.compile(''))
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
                    self.assertSubstring(exp, out)
                elif isinstance(exp, REGEX_PATTERN_TYPE):
                    self.failUnless(exp.match(out), "%r did not match string %r" % (exp.pattern, out))
                else:
                    raise TypeError, "don't know what to do with object %r" % (exp,)

