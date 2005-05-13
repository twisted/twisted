# -*- test-case-name: twisted.trial.test.test_doctest -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import warnings, time, random, types, re, traceback

from pprint import pformat
import os.path as osp

from twisted.trial import itrial, runner, doctest, unittest, adapters
from twisted.trial.reporter import DOUBLE_SEPARATOR, FAILURE, ERROR, SUCCESS
from twisted.python import reflect, failure, util as tputil, log

import zope.interface as zi

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO


class Proxy(object):
    pass

def bogus(*args, **kwargs):
    warnings.warn("bogus method called in tdoctest.py, not sure why")

class DocTestRunnerBase(runner.TestClassAndMethodBase, runner.ParentAttributeMixin):
    zi.implements(itrial.ITestRunner, itrial.IDocTestRunner)

    setUpClass = tearDownClass = setUpModule = bogus
    tearDownModule = testCaseInstance = bogus
    methodNames = methods = methodsWithStatus = None
    
    def runTests(self, randomize=False):
        raise NotImplementedError, "override in subclasses"


class _ExampleWrapper(tputil.FancyStrMixin, object, runner.StatusMixin):
    zi.implements(itrial.ITestMethod, itrial.IMethodInfo)
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


class DocTestFailure(failure.Failure):
    zi.implements(itrial.IFormattedFailure)

    doctestFailStr = ''

    def __str__(self):
        # yes, we're cheating a bit here
        # this gets set in report_failure or report_unexpected_exception
        return self.doctestFailStr
    
    __repr__ = __str__

class AnError(Exception):
    pass

# the implementation of the DocTestRunner is confusing in the fact
# that it must pretend to be both an ITestRunner and an ITestMethod.
# It has to pretend to be an ITestMethod because the doctest definition
# of a DocTestRunner, and of a DocTest itself is a collection of Examples
# which are a single executable line of Python code. This doesn't map
# well to our abstraction, it would be like making each line of a 
# unittest equivalent to a TestMethod. So instead we treat the 
# DocTestRunner as a kind of singleton runner that is adaptable to 
# ITestMethod for convenience (because it only runs one theoretical TestMethod)

# XXX: WARNING TO ALL
#
# the implemenation of the error reporting mechanism for doctests breaks
# all sorts of abstractions, and will probably give you Herpes if examined
# too closely, this will be fixed later
#
# the error reporting is handled by the adapter from DocTestRunner to
# ITestMethod, it creates DocTestFailure, which is an object that implements
# IFormattedFailure, therefore the reporter will (basically) do a 
# print str(f) on it. The creation of this error is not handled in the 
# report_failure or report_unexpected_exception methods because doctests
# are wacky when it comes to using pdb, and debugging this mess is enough
# of a pain as it is.


class _DTRToITM(object, runner.StatusMixin):
    """real adapter from DocTestRunner to ITestMethod"""
    zi.implements(itrial.IDocTestMethod)
    setUp = classmethod(bogus)
    tearDown = classmethod(bogus)
    method = todo = skip = timeout = suppress = None
    stderr = stdout = ''
    _failures = _errors = None

    hasTbs = property(lambda self: (self.errors or self.failures))

    def formatDoctestError(self):
        ret = [DOUBLE_SEPARATOR,
               '%s: %s (%s)\n' % (WORDS[self.status], self.name, adapters.trimFilename(self.filename, 4))]

        return "%s\n%s" % ('\n'.join(ret),
                           itrial.IFormattedFailure(self.errors + self.failures))


    def __init__(self, original):
        self.original = o = original
        self.runs = 0
        self.klass = "doctests have no class"
        self.module = "doctests have no module"
        # the originating module of this doctest
        self.module = reflect.filenameToModuleName(self.original._dtest.filename)

        self.filename = o._dtest.filename
        self.lineno = o._dtest.lineno
        self.docstr= "doctest, file: %s lineno: %s" % (osp.split(self.filename)[1], self.lineno)
        self.name = o._dtest.name
        self.fullname = repr(o._dtest)
        self._regex = re.compile(r'\S')

    def _getErrorfulDocstring(self, example):
        L = []
        foundStart = False
        docstring = self.original._dtest.docstring
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

    def failures(self):
        if self._failures is None:
            if self.original._dt_failures:
                f = DocTestFailure(unittest.FailTest)
                
                L = []
                for out, test, example, got in self.original._dt_failures:
                    L.extend(["docstring", "---------"])
                    L.extend(self._getErrorfulDocstring(example))
                    L.append('')
                    L.append("doctest error message:")
                    L.append("----------------------")
                    L.extend(self.original._checker.output_difference(
                                   example, got, self.original.optionflags).split('\n'))
                f.doctestFailStr = '\n'.join(L)
                self._failures = [f]
            else:
                self._failures = []
        return self._failures
    failures = property(failures)

    def errors(self):
        if self._errors is None:
            if self.original._dt_errors:
                L = []
                for out, test, example, exc_info in self.original._dt_errors:
                    L.append("docstring\n---------")
                    L.extend(self._getErrorfulDocstring(example))
                    L.append("\n")
                    L.extend(traceback.format_exception(*exc_info))
                    L.append('')
                
                # Since these adapters are persistent, we alter the original 
                # object, deleting its _dt_errors so that it's not keeping
                # exc_info tuples around for any longer than necessary
                del self.original._dt_errors

                f = DocTestFailure(AnError)
                f.doctestFailStr = '\n'.join(L)
                self._errors = [f]
            else:
                self._errors = []
        return self._errors
    errors = property(errors)


class _DTRToITMFactory(adapters.PersistentAdapterFactory):
    """a registry for persistent adapters of DocTestRunner to ITestMethod"""
    adapter = _DTRToITM

DocTestRunnerToITestMethod = _DTRToITMFactory()


class DocTestRunner(DocTestRunnerBase, doctest.DocTestRunner):
    """i run a group of doctest examples as a unit
    things get a little funky with this as the DocTestRunner
    doubles as an ITestMethod object. we're going to conceptualize the
    Examples as an individual line from a unittest
    """
    todo = skip = timeout = suppress = None
    _dt_started = False

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
       
    _dt_reporter = property(lambda self: self.getReporter())

    def getMethodsWithStatus(self):
        # XXX: This is very very cheezy
        itm = itrial.ITestMethod(self)
        return {itm.status: [itm]}

    methodsWithStatus = property(getMethodsWithStatus, lambda self, v: None)

    def _dt_done(self):
        numRan = (len(self._dt_errors)
                  + len(self._dt_failures)
                  + len(self._dt_successes))
        return numRan == len(self._dtest.examples)
    _dt_done = property(_dt_done)

    def report_start(self, out, test, example):
        if not self._dt_started:
            self._dt_reporter.startTest(self)
            self._dt_started = True
    
    def report_failure(self, out, test, example, got):
        # XXX: let's have a big hand for python's lack of traceback
        # object constructor
        self._dt_failures.append((out,test,example,got))
        if self._dt_done:
            self._dt_reporter.endTest(self)

    def report_success(self, out, test, example, got):
        self._dt_successes.append(example)
        if self._dt_done:
            self._dt_reporter.endTest(self)

    def report_unexpected_exception(self, out, test, example, exc_info):
        self._dt_errors.append((out, test, example, exc_info))
        if self._dt_done:
            self._dt_reporter.endTest(self)

    def runTests(self, randomize=None):
        # randiomize argument is ignored 
        doctest.DocTestRunner.run(self, self._dtest)


class ModuleDocTestsRunner(DocTestRunnerBase):
    """I run the doctest.DocTests of objects found in a module's
    __doctests__ attribute
    """
    def __init__(self, original):
        """original is a sequence of fully-qualified python object names
        or python objects, it is the value of a module's __doctests__ attribute
        """
        super(ModuleDocTestsRunner, self).__init__(original)

    def runTests(self, randomize=False):
        # randomize is ignored for now
        self.startTime = time.time()

        reporter = self.getReporter()
        dtf = doctest.DocTestFinder()
        tests = []
        for obj in self.original:
            if isinstance(obj, types.StringType):
                obj = reflect.namedAny(obj)
            tests.extend(dtf.find(obj))
        
        if randomize:
            random.shuffle(tests)

        for test in tests:
            runner = itrial.ITestRunner(test, None)
            if runner == None:
                continue
            runner.parent = self
            self.children.append(runner)
            runner.runTests(randomize)

            for k, v in runner.methodsWithStatus.iteritems():
                self.methodsWithStatus.setdefault(k, []).extend(v)



