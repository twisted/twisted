# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Original Author: Jonathan Lange <jml@twistedmatrix.com>

from __future__ import generators

import sys, types
import warnings

from twisted.python import reflect, failure, log
from twisted.python.compat import adict
from twisted.internet import defer
from twisted.trial import itrial, util
import zope.interface as zi

#******************************************************************************
# turn this off if you're having trouble with traceback printouts or some such

HIDE_TRIAL_INTERNALS = True

#******************************************************************************

STATUSES = (SKIP, EXPECTED_FAILURE, FAILURE,
            ERROR, UNEXPECTED_SUCCESS, SUCCESS) = ("skips", "expectedFailures",
                                                   "failures", "errors",
                                                   "unexpectedSuccesses",
                                                   "successes")
WORDS = {SKIP: '[SKIPPED]',
         EXPECTED_FAILURE: '[TODO]',
         FAILURE: '[FAIL]', ERROR: '[ERROR]',
         UNEXPECTED_SUCCESS: '[SUCCESS!?!]',
         SUCCESS: '[OK]'}

LETTERS = {SKIP: 'S', EXPECTED_FAILURE: 'T',
           FAILURE: 'F', ERROR: 'E',
           UNEXPECTED_SUCCESS: '!', SUCCESS: '.'}

SEPARATOR = '-' * 79
DOUBLE_SEPARATOR = '=' * 79

_basefmt = "caught exception in %s, your TestCase is broken\n\n"
SET_UP_CLASS_WARN = _basefmt % 'setUpClass'
SET_UP_WARN = _basefmt % 'setUp'
TEAR_DOWN_WARN = _basefmt % 'tearDown'
TEAR_DOWN_CLASS_WARN = _basefmt % 'tearDownClass'
DIRTY_REACTOR_POLICY_WARN = ("This failure will cause all methods in your class"
                             " to be reported as ERRORs in the summary")
UNCLEAN_REACTOR_WARN = "REACTOR UNCLEAN! traceback(s) follow: "

PASSED, FAILED = "PASSED", "FAILED"

methNameWarnMsg = adict(setUpClass = SET_UP_CLASS_WARN,
                        setUp = SET_UP_WARN,
                        tearDown = TEAR_DOWN_WARN,
                        tearDownClass = TEAR_DOWN_CLASS_WARN)

# ----------------------------------------------------------------------------

def makeLoggingMethod(name, f):
    def loggingMethod(*a, **kw):
        print "%s.%s(*%r, **%r)" % (name, f.func_name, a, kw)
        return f(*a, **kw)
    return loggingMethod


class MethodCallLoggingType(type):
    def __new__(cls, name, bases, attrs):
        for (k, v) in attrs.items():
            if isinstance(v, types.FunctionType):
                attrs[k] = makeLoggingMethod(name, v)
        return super(MethodCallLoggingType, cls).__new__(cls, name, bases,
                                                         attrs)

def runningTime(testCase):
    return testCase.endTime - testCase.startTime


class BrokenTestCaseWarning(Warning):
    """emitted as a warning when an exception occurs in one of
    setUp, tearDown, setUpClass, or tearDownClass"""


class Reporter(object):
    zi.implements(itrial.IReporter)
    debugger = None

    def __init__(self, stream=sys.stdout, tbformat='default', args=None,
                 realtime=False):
        self.stream = stream
        self.tbformat = tbformat
        self.args = args
        self.realtime = realtime
        self.shouldStop = False
        self.couldNotImport = []
        self.failures = []
        self.errors = []
        self.results = {}
        for status in STATUSES:
            self.results[status] = []
        super(Reporter, self).__init__(stream, tbformat, args, realtime)

    def setUpReporter(self):
        pass

    def tearDownReporter(self):
        pass

    def startTest(self, method):
        pass

    def reportImportError(self, name, exc):
        self.couldNotImport.append((name, exc))

    def addFailure(self, test, failure):
        self.failures.append((test, failure))

    def addError(self, test, error):
        self.errors.append((test, error))

    def _getFailures(self, forTest):
        return [ failure for (test, failure) in self.failures if test == forTest ]

    def _getErrors(self, forTest):
        return [ error for (test, error) in self.errors if test == forTest ]

    def wasSuccessful(self):
        return len(self.errors) == len(self.failures) == 0

    def getStatus(self, method):
        failures = self._getFailures(method)
        errors = self._getErrors(method)
        if method.getTodo() is not None and (failures or errors):
            for f in failures + errors:
                if not itrial.ITodo(method.getTodo()).isExpected(f):
                    return ERROR
                return EXPECTED_FAILURE
        elif method.getSkip() is not None:
            return SKIP
        elif errors:
            return ERROR
        elif failures:
            return FAILURE
        elif method.getTodo():
            return UNEXPECTED_SUCCESS
        else:
            return SUCCESS

    def write(self, format, *args):
        s = str(format)
        assert isinstance(s, type(''))
        if args:
            self.stream.write(s % args)
        else:
            self.stream.write(s)
        self.stream.flush()

    def startModule(self, name):
        pass

    def startClass(self, klass):
        pass

    def endModule(self, module):
        pass

    def endClass(self, klass):
        pass

    def emitWarning(self, message, category=UserWarning, stacklevel=0):
        warnings.warn(message, category, stacklevel - 1)
        
    def upDownError(self, userMeth, warn=True, printStatus=True):
        if warn:
            minfo = itrial.IMethodInfo(userMeth)
            tbStr = '\n'.join([e.getTraceback() for e in userMeth.errors]) 
            log.msg(tbStr)
            msg = "%s%s" % (methNameWarnMsg[minfo.name], tbStr)
            warnings.warn(msg, BrokenTestCaseWarning, stacklevel=2)

    def cleanupErrors(self, errs):
        warnings.warn("%s\n%s" % (UNCLEAN_REACTOR_WARN,
                                  '\n'.join(map(self._formatFailureTraceback,
                                                errs))),
                      BrokenTestCaseWarning)

    def endTest(self, method):
        method = itrial.ITestMethod(method)
        self.results[self.getStatus(method)].append(method)
        if self.realtime:
            for err in self._getErrors(method) + self._getFailures(method):
                err.printTraceback(self.stream)

    def _formatFailureTraceback(self, fail):
        # Short term hack
        if isinstance(fail, str):
            return fail 
        detailLevel = self.tbformat
        result = fail.getTraceback(detail=detailLevel, elideFrameworkCode=True)
        if detailLevel == 'default':
            # Apparently trial's tests doen't like the 'Traceback:' line.
            result = '\n'.join(result.split('\n')[1:])
        return result

    def _formatImportError(self, name, error):
        """format an import error for report in the summary section of output

        @param name: The name of the module which could not be imported
        @param error: The exception which occurred on import
        
        @rtype: str
        """
        ret = [DOUBLE_SEPARATOR, '\nIMPORT ERROR:\n\n']
        if isinstance(error, failure.Failure):
            what = self._formatFailureTraceback(error)
        elif type(error) == types.TupleType:
            what = error.args[0]
        else:
            what = "%s\n" % error
        ret.append("Could not import %s: \n%s\n" % (name, what))
        return ''.join(ret)

    def _formatFailedTest(self, name, status, failures, skipMsg=None,
                          todoMsg=None):
        ret = [DOUBLE_SEPARATOR, '%s: %s\n' % (WORDS[status], name)]
        if skipMsg:
            ret.append(self._formatFailureTraceback(skipMsg) + '\n')
        if todoMsg:
            ret.append(todoMsg + '\n')
        if status not in (SUCCESS, SKIP, UNEXPECTED_SUCCESS):
            ret.extend(map(self._formatFailureTraceback, failures))
        return '\n'.join(ret)

    def _reportStatus(self, tsuite):
        summaries = []
        for stat in STATUSES:
            num = len(self.results[stat])
            if num:
                summaries.append('%s=%d' % (stat, num))
        summary = (summaries and ' ('+', '.join(summaries)+')') or ''
        if self.results[FAILURE] or self.results[ERROR]:
            status = FAILED
        else:
            status = PASSED
        self.write("%s%s\n", status, summary)

    def _reportFailures(self):
        # XXX - why isn't this one loop?? - jml
        for meth in self.results[SKIP]:
            self.write(self._formatFailedTest(
                meth.fullName, SKIP,
                self._getErrors(meth) + self._getFailures(meth),
                meth.getSkip(),
                itrial.ITodo(meth.getTodo()).msg))
        for status in [EXPECTED_FAILURE, FAILURE, ERROR]:
            for meth in self.results[status]:
                self.write(self._formatFailedTest(
                    meth.fullName, status,
                    self._getErrors(meth) + self._getFailures(meth),
                    meth.getSkip(),
                    itrial.ITodo(meth.getTodo()).msg))
        for name, error in self.couldNotImport:
            self.write(self._formatImportError(name, error))

    def startSuite(self, count):
        """Inform the user how many tests are being run."""

    def endSuite(self, suite):
        self.write("\n")
        self._reportFailures()
        self.write("%s\n" % SEPARATOR)
        self.write('Ran %d tests in %.3fs\n', suite.countTestCases(),
                   runningTime(suite))
        self.write('\n')
        self._reportStatus(suite)


class MinimalReporter(Reporter):
    def endSuite(self, suite):
        numTests = suite.countTestCases()
        t = (runningTime(suite), numTests, numTests,
             len(self.couldNotImport), len(self.results[ERROR]),
             len(self.results[FAILURE]), len(self.results[SKIP]))
        self.stream.write(' '.join(map(str,t))+'\n')


class TextReporter(Reporter):
    def __init__(self, stream=sys.stdout, tbformat='default', args=None,
                 realtime=False):
        super(TextReporter, self).__init__(stream, tbformat, args, realtime)
        self.seenModules, self.seenClasses = {}, {}

    def endTest(self, method):
        method = itrial.ITestMethod(method)
        self.write(LETTERS.get(self.getStatus(method), '?'))
        super(TextReporter, self).endTest(method)


class VerboseTextReporter(TextReporter):
    # This is actually the bwverbose option
    def startTest(self, method):
        tm = itrial.ITestMethod(method)
        # XXX this is a crap workaround for doctests,
        # there should be a better solution.
        try:
            klass = reflect.qual(tm.klass)
        except AttributeError: # not a real class
            klass = str(tm.klass)
        self.write('%s (%s) ... ', tm.name, klass)
        super(VerboseTextReporter, self).startTest(method)
        
    def endTest(self, method):
        method = itrial.ITestMethod(method)
        self.write("%s\n" % WORDS.get(self.getStatus(method), "[??]"))


class TimingTextReporter(VerboseTextReporter):
    def endTest(self, method):
        self.write("%s" % WORDS.get(self.getStatus(method), "[??]") + " "
                   + "(%.03f secs)\n" % runningTime(method))


class TreeReporter(VerboseTextReporter):
    #__metaclass__ = MethodCallLoggingType
    currentLine = ''
    columns = 79

    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37

    def __init__(self, stream=sys.stdout, tbformat='default', args=None,
                 realtime=False):
        super(TreeReporter, self).__init__(stream, tbformat, args, realtime)
        self.words = {SKIP: ('[SKIPPED]', self.BLUE),
                      EXPECTED_FAILURE: ('[TODO]', self.BLUE),
                      FAILURE: ('[FAIL]', self.RED),
                      ERROR: ('[ERROR]', self.RED),
                      UNEXPECTED_SUCCESS: ('[SUCCESS!?!]', self.RED),
                      SUCCESS: ('[OK]', self.GREEN)}

    def _getText(self, status):
        return self.words.get(status, ('[??]', self.BLUE))

    def write(self, format, *args):
        if args:
            format = format % args
        self.currentLine = format
        super(TreeReporter, self).write(self.currentLine)

    def startModule(self, module):
        modName = module.__name__
        if modName not in self.seenModules:
            self.seenModules[modName] = 1
            self.write('  %s\n' % modName)

    def startClass(self, klass):
        clsName = klass.__name__
        qualifiedClsName = reflect.qual(klass)
        if qualifiedClsName not in self.seenClasses:
            self.seenClasses[qualifiedClsName] = 1
            self.write('    %s\n' % clsName)

    def startSuite(self, count):
        """Inform the user how many tests are being run."""
        self.write("Running %d tests.\n", count)

    def cleanupErrors(self, errs):
        self.write(self.color('    cleanup errors', self.RED))
        self.endLine(*self._getText(ERROR))
        super(TreeReporter, self).cleanupErrors(errs)

    def upDownError(self, method, warn=True, printStatus=True):
        m = itrial.IMethodInfo(method)
        self.write(self.color("  %s" % m.name, self.RED))
        if printStatus:
            self.endLine(*self._getText(ERROR))
        super(TreeReporter, self).upDownError(method, warn, printStatus)
        
    def startTest(self, method):
        tm = itrial.ITestMethod(method)
        if tm.docstr:
            # inspect trims whitespace on the left; the lstrip here is
            # for those odd folks who start docstrings with a blank line.
            what = tm.docstr.lstrip().split('\n', 1)[0]
        else:
            what = tm.name
        self.write('      %s ... ', what)

    def endTest(self, method):
        Reporter.endTest(self, method)
        tm = itrial.ITestMethod(method)
        self.endLine(*self._getText(self.getStatus(tm)))

    def color(self, text, color):
        return '%s%s;1m%s%s0m' % ('\x1b[', color, text, '\x1b[')

    def endLine(self, message, color):
        spaces = ' ' * (self.columns - len(self.currentLine) - len(message))
        super(TreeReporter, self).write(spaces)
        super(TreeReporter, self).write("%s\n" % (self.color(message, color),))
