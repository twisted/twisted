# -*- test-case-name: twisted.trial.test.test_doctest -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import warnings, time, random, types, re, traceback

import os.path as osp

from twisted.trial import itrial, runner, doctest, adapters
from twisted.python import reflect, util as tputil

import zope.interface as zi


def bogus(*args, **kwargs):
    warnings.warn("bogus method called in tdoctest.py, not sure why")

class DocTestRunnerBase(runner.ClassSuite):
    zi.implements(itrial.ITestRunner, itrial.IDocTestRunner)

    setUpClass = tearDownClass = bogus
    testCaseInstance = bogus
    methodNames = methods = None
    
    def runTests(self, reporter, randomize=False):
        raise NotImplementedError, "override in subclasses"


class _ExampleWrapper(tputil.FancyStrMixin, object):
    zi.implements(itrial.ITestMethod)
    _parent = seqNum = None
    showAttributes = ('name', 'source', 'fullname', 'errors', 'failures')

    def __init__(self, original):
        self.original = original
        self.source = original.source

    def getParent(self):
        return self._parent
    def setParent(self, parent):
        self._parent = parent
    parent = property(getParent, setParent)


class ExampleToITestMethod(object):
    def __init__(self):
        self.adapters = {}

    def seqNum(self):
        return len(self.adapters)
    seqNum = property(seqNum)
    
    def __call__(self, original):
        a = self.adapters.setdefault(original, _ExampleWrapper(original))
        if a.seqNum == None:
            a.seqNum = self.seqNum
        return a


class AnError(Exception):
    pass


class DocTestRunner(DocTestRunnerBase, doctest.DocTestRunner):
    """i run a group of doctest examples as a unit
    things get a little funky with this as the DocTestRunner
    doubles as an ITestMethod object. we're going to conceptualize the
    Examples as an individual line from a unittest
    """
    todo = skip = timeout = suppress = None
    _dt_started = False

    zi.implements(itrial.IDocTestMethod)

    def __init__(self, original):
        DocTestRunnerBase.__init__(self, original)
        doctest.DocTestRunner.__init__(self)
        # I know this _dt_ nonsense is ugly, but it's to prevent naming conflicts
        # with the doctest.DocTestRunner's names
        self._dt_errors = []
        self._dt_failures = []
        self._dt_successes = []
        # the doctest.DocTest object
        self._dtest = original
        self._regex = re.compile(r'\S')
        self.fullName = self.filename = self._dtest.filename

    def id(self):
        return "%s:%s" % (self.fullName, self._dtest.name)

    def shortDescription(self):
        lineno = self._dtest.lineno
        return ("doctest, file: %s lineno: %s"
                % (osp.split(self.filename)[1], lineno))

    def getTodo(self):
        pass

    def getSkip(self):
        pass

    def getTimeout(self):
        pass

    def getSuppress(self):
        pass

    def _getErrorfulDocstring(self, example):
        L = []
        foundStart = False
        docstring = self._dtest.docstring
        for num, line in enumerate(docstring.split('\n')):
            if line.find('>>>') != -1:
                foundStart = True

            if foundStart:
                if num != example.lineno:
                    s = "    %s" % line[example.indent:]
                else:
                    s = "--> %s" % line[example.indent:]
                if self._regex.search(s):
                    L.append(s)
        return L

    def _formatFailure(self, out, test, example, got):
        L = []
        L.extend(["docstring", "---------"])
        L.extend(self._getErrorfulDocstring(example))
        L.append('')
        L.append("doctest error message:")
        L.append("----------------------")
        L.extend(self._checker.output_difference(
            example, got, self.optionflags).split('\n'))
        return '\n'.join(L)

    def _formatError(self, out, test, example, exc_info):
        L = []
        L.append("docstring\n---------")
        L.extend(self._getErrorfulDocstring(example))
        L.append("\n")
        L.extend(traceback.format_exception(*exc_info))
        L.append('')
        return '\n'.join(L)

    def _dt_done(self):
        numRan = (len(self._dt_errors) + len(self._dt_failures)
                  + len(self._dt_successes))
        return numRan >= len(self._dtest.examples)

    def report_start(self, out, test, example):
        if not self._dt_started:
            self._dt_reporter.startTest(self)
            self._dt_started = True
    
    def report_failure(self, out, test, example, got):
        self._dt_reporter.addFailure(self, self._formatFailure(out, test,
                                                               example, got))
        self._dt_reporter.endTest(self)

    def report_success(self, out, test, example, got):
        self._dt_successes.append(example)
        if self._dt_done():
            self._dt_reporter.endTest(self)

    def report_unexpected_exception(self, out, test, example, exc_info):
        self._dt_reporter.addError(self, self._formatError(out, test, example,
                                                           exc_info))
        self._dt_reporter.endTest(self)

    def countTestCases(self):
        return 1

    def runTests(self, reporter, randomize=None):
        # randomize argument is ignored
        self._dt_reporter = reporter
        doctest.DocTestRunner.run(self, self._dtest)

    def visit(self, visitor):
        visitor.visitCase(self)


class ModuleDocTestsRunner(DocTestRunnerBase):
    """I run the doctest.DocTests of objects found in a module's
    __doctests__ attribute
    """
    def __init__(self, original):
        """original is a sequence of fully-qualified python object names
        or python objects, it is the value of a module's __doctests__ attribute
        """
        super(ModuleDocTestsRunner, self).__init__(original)
        self._testCase = original

    def _populateChildren(self):
        dtf = doctest.DocTestFinder()
        for obj in self.original:
            if isinstance(obj, types.StringType):
                obj = reflect.namedAny(obj)
            for test in dtf.find(obj):
                runner = DocTestRunner(test)
                runner.parent = self
                self.children.append(runner)

    def countTestCases(self):
        """Return the number of test cases self.run() would run."""
        ret = 0
        for runner in self._getChildren():
            ret += runner.countTestCases()
        return ret

    def visit(self, visitor):
        visitor.visitModule(self)
        self._visitChildren(visitor)
        visitor.visitModuleAfter(self)

    def runTests(self, reporter, randomize=False):
        self.startTime = time.time()
        if randomize:
            random.shuffle(self._getChildren())
        for runner in self._getChildren():
            runner.runTests(reporter, randomize)
        # XXX -- there is no endTime? -- jml
