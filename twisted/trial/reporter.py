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

from twisted.python import reflect, failure, log, util as tputil
from twisted.python.compat import adict
from twisted.internet import defer
from twisted.trial import itrial, util
import zope.interface as zi

#******************************************************************************
# turn this off if you're having trouble with traceback printouts or some such

HIDE_TRIAL_INTERNALS = True

#******************************************************************************

# test results, passed as resultType to Reporter.endTest()
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
DIRTY_REACTOR_POLICY_WARN = "This failure will cause all methods in your class to be reported as ERRORs in the summary"
UNCLEAN_REACTOR_WARN = "REACTOR UNCLEAN! traceback(s) follow: "

PASSED, FAILED = "PASSED", "FAILED"

methNameWarnMsg = adict(setUpClass = SET_UP_CLASS_WARN,
                        setUp = SET_UP_WARN,
                        tearDown = TEAR_DOWN_WARN,
                        tearDownClass = TEAR_DOWN_CLASS_WARN)

# ----------------------------------------------------------------------------

def formatImportError(name, error):
    """format an import error for report in the summary section of output

    @param name: The name of the module which could not be imported
    @param error: The exception which occurred on import
    
    @rtype: str
    """
    ret = [DOUBLE_SEPARATOR, '\nIMPORT ERROR:\n\n']
    if isinstance(error, failure.Failure):
        what = itrial.IFormattedFailure(error)
    elif type(error) == types.TupleType:
        what = error.args[0]
    else:
        what = "%s\n" % error
    ret.append("Could not import %s: \n%s\n" % (name, what))
    return ''.join(ret)


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

class TestStatsBase(object):
    zi.implements(itrial.ITestStats)

    importErrors = None
    
    def __init__(self, original):
        #print "original: %r" % (original,)
        self.original = original

    def _collect(self):
        raise NotImplementedError, "should be overridden in subclasses"

    def get_skips(self):
        return self._collect(SKIP)

    def get_errors(self):
        return self._collect(ERROR)

    def get_failures(self):
        return self._collect(FAILURE)

    def get_expectedFailures(self):
        return self._collect(EXPECTED_FAILURE)

    def get_unexpectedSuccesses(self):
        return self._collect(UNEXPECTED_SUCCESS)

    def get_successes(self):
        return self._collect(SUCCESS)

    def runningTime(self):
        o = self.original
        return o.endTime - o.startTime
    runningTime = property(runningTime)


class TestStats(TestStatsBase):
    # this adapter is used for both TestSuite and TestModule objects
    importErrors = property(lambda self: getattr(self.original,
                                                 'couldNotImport', {}).items())

    def _collect(self, status):
        meths = []
        for r in self.original.children:
            meths.extend(r.methodsWithStatus.get(status, []))
        return meths

    def numTests(self):
        n = 0
        for r in self.original.children:
            ts = itrial.ITestStats(r)
            n += ts.numTests()
        return n

    def allPassed(self):
        for r in self.original.children:
            if not itrial.ITestStats(r).allPassed:
                return False
        if getattr(self.original, 'couldNotImport', False):
            return False
        return True
    allPassed = property(allPassed)

class TestCaseStats(TestStatsBase):
    def _collect(self, status):
        """return a list of all TestMethods with status"""
        return self.original.methodsWithStatus.get(status, [])

    def numTests(self):
        n = len(self.original.children)
        return n

    def allPassed(self):
        for status in (ERROR, FAILURE):
            if status in self.original.methodsWithStatus:
                return False
        return True
    allPassed = property(allPassed)

class DocTestRunnerStats(TestCaseStats):
    def numTests(self):
        """DocTestRunners are singleton runners"""
        return 1


class BrokenTestCaseWarning(Warning):
    """emitted as a warning when an exception occurs in one of
    setUp, tearDown, setUpClass, or tearDownClass"""


class Reporter(object):
    zi.implements(itrial.IReporter)
    debugger = None

    def __init__(self, stream=sys.stdout, tbformat='plain', args=None,
                 realtime=False):
        self.stream = stream
        self.tbformat = tbformat
        self.args = args
        self.realtime = realtime
        super(Reporter, self).__init__(stream, tbformat, args, realtime)

    def setUpReporter(self):
        return defer.succeed(None)

    def tearDownReporter(self):
        return defer.succeed(None)

    def startTest(self, method):
        pass

    def reportImportError(self, name, exc):
        pass

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
            tbStr = '\n'.join([e.getTraceback() for e in userMeth.errors]) # if not e.check(unittest.SkipTest)])
            log.msg(tbStr)
            msg = "%s%s" % (methNameWarnMsg[minfo.name], tbStr)
            warnings.warn(msg, BrokenTestCaseWarning, stacklevel=2)

    def cleanupErrors(self, errs):
        warnings.warn("%s\n%s" % (UNCLEAN_REACTOR_WARN,
                                  itrial.IFormattedFailure(errs)),
                      BrokenTestCaseWarning)

    def endTest(self, method):
        method = itrial.ITestMethod(method)
        if self.realtime:
            for err in util.iterchain(method.errors, method.failures):
                err.printTraceback(sys.stdout)

    def _reportStatus(self, tsuite):
        tstats = itrial.ITestStats(tsuite)
        summaries = []
        for stat in STATUSES:
            num = len(getattr(tstats, "get_%s" % stat)())
            if num:
                summaries.append('%s=%d' % (stat, num))

        summary = (summaries and ' ('+', '.join(summaries)+')') or ''

        if tstats.get_failures() or tstats.get_errors():
            status = FAILED
        else:
            status = PASSED
        self.write("%s%s\n", status, summary)

    def _reportFailures(self, tstats):
        for meth in getattr(tstats, "get_%s" % SKIP)():
            self.write(meth.formatError())

        for status in [EXPECTED_FAILURE, FAILURE, ERROR]:
            for meth in getattr(tstats, "get_%s" % status)():
                if meth.hasTbs:
                    self.write(meth.formatError())

        for name, error in tstats.importErrors:
            self.write(formatImportError(name, error))

    def endSuite(self, suite):
        tstats = itrial.ITestStats(suite)
        self.write("\n")
        self._reportFailures(tstats)

        self.write("%s\n" % SEPARATOR)
        self.write('Ran %d tests in %.3fs\n', tstats.numTests(),
                   tstats.runningTime)
        self.write('\n')
        self._reportStatus(suite)


class MinimalReporter(Reporter):
    def endSuite(self, suite):
        tstats = itrial.ITestStats(suite)
        t = (tstats.runningTime, tstats.numTests(), tstats.numTests(),
             # XXX: expectedTests == runTests
             len(tstats.importErrors), len(tstats.get_errors()),
             len(tstats.get_failures()), len(tstats.get_skips()))
        self.stream.write(' '.join(map(str,t))+'\n')


class TextReporter(Reporter):
    def __init__(self, stream=sys.stdout, tbformat='plain', args=None,
                 realtime=False):
        super(TextReporter, self).__init__(stream, tbformat, args, realtime)
        self.seenModules, self.seenClasses = {}, {}

    def endTest(self, method):
        self.write(LETTERS.get(itrial.ITestMethod(method).status, '?'))
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
        self.write("%s\n" % WORDS.get(itrial.ITestMethod(method).status,
                                      "[??]"))

class TimingTextReporter(VerboseTextReporter):
    def endTest(self, method):
        self.write("%s" % WORDS.get(method.status, "[??]") + " "
                   + "(%.03f secs)\n" % method.runningTime())


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

    def __init__(self, stream=sys.stdout, tbformat='plain', args=None,
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
        self.endLine(*self._getText(tm.status))

    def color(self, text, color):
        return '%s%s;1m%s%s0m' % ('\x1b[', color, text, '\x1b[')

    def endLine(self, message, color):
        spaces = ' ' * (self.columns - len(self.currentLine) - len(message))
        super(TreeReporter, self).write(spaces)
        super(TreeReporter, self).write("%s\n" % (self.color(message, color),))


