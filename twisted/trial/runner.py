# -*- test-case-name: twisted.trial.test.test_trial -*-

#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Original Author: Jonathan Lange <jml@twistedmatrix.com>

from __future__ import generators


import os, glob, types, warnings, time, sys, cPickle as pickle, inspect
import fnmatch, random, inspect
from os.path import join as opj

from twisted.internet import defer, interfaces
from twisted.python import components, reflect, log, failure
from twisted.trial import itrial, util, unittest
from twisted.trial.itrial import ITestCase, IReporter, ITrialDebug
from twisted.trial.reporter import SKIP, EXPECTED_FAILURE, FAILURE, \
     ERROR, UNEXPECTED_SUCCESS, SUCCESS
import zope.interface as zi


MAGIC_ATTRS = ('skip', 'todo', 'timeout', 'suppress')


def makeTestRunner(orig):
    from twisted import trial
    if trial.benchmarking:
        return BenchmarkCaseRunner(orig)
    else:
        return TestCaseRunner(orig)


class BrokenTestCaseWarning(Warning):
    """emitted as a warning when an exception occurs in one of
    setUp, tearDown, setUpClass, or tearDownClass"""

def _dbgPA(msg):
    log.msg(iface=itrial.ITrialDebug, parseargs=msg)

_reactorKickStarted = False
def _kickStartReactor():
    """Start the reactor if needed so that tests can be run."""
    global _reactorKickStarted
    if not _reactorKickStarted:
        # Kick-start things
        from twisted.internet import reactor
        reactor.callLater(0, reactor.crash)
        reactor.run()
        _reactorKickStarted = True


class TestSuite(object):
    """A TestCase container that implements both TestCase and TestSuite
    interfaces."""

    def countTestCases(self):
        """Return the number of tests in the TestSuite."""
        result = 0
        for case in self._getChildren():
            result += case.countTestCases()
        return result

    def _getChildren(self, randomize=False):
        if not len(self.children):
            self._populateChildren()
        if randomize:
            random.shuffle(self.children)
        return self.children

    def run(self):
        for child in self._getChildren():
            child.run()

    def addTest(self, test):
        self.children.append(test)

    def addTests(self, tests):
        for test in tests:
            self.addTest(test)


def isPackageDirectory(dirname):
    """Is the directory at path 'dirname' a Python package directory?"""
    for ext in 'py', 'so', 'pyd', 'dll':
        if os.path.exists(os.path.join(dirname,
                                       os.extsep.join(('__init__', ext)))):
            return True
    return False


def filenameToModule(fn):
    return reflect.namedModule(reflect.filenameToModuleName(fn))


def findTestClasses(module):
    """Given a module, return all trial Test classes"""
    def isclass(k):
        ## XXX -- work around. remove ASAP. 
        ## inspect.isclass checks for ClassType and then if __bases__
        ## is an attribute.
        ## t.conch.insults.text.CharacterAttributes has a (buggy?) __getattr__
        ## which returns objects for any given attribute.  Hence it has
        ## __bases__, hence, inspect.isclass believes instances to be classes.
        ## Remove this workaround and replace w/ inspect.isclass if
        ## CharacterAttributes is fixed.
        return isinstance(k, (types.ClassType, types.TypeType)) 
    classes = [val for name, val in inspect.getmembers(module, isclass)]
    return filter(ITestCase.implementedBy, classes)


MODULE_GLOB = 'test_*.py'

def findTestModules(package):
    modGlob = os.path.join(os.path.dirname(package.__file__), MODULE_GLOB)
    return map(filenameToModule, glob.glob(modGlob))


class TrialRoot(TestSuite):
    """This is the main organizing object. The front-end script creates a
    TrialRoot, and tells it what modules were requested on the command line.
    It also hands it a reporter. The TrialRoot then takes all of the
    packages, modules, classes and methods, and adapts them to ITestRunner
    objects, which it then calls the run method on.
    """
    zi.implements(itrial.ITrialRoot)
    debugger = False

    def __init__(self, reporter, janitor, benchmark=0):
        self.reporter = IReporter(reporter)
        self.janitor = janitor
        self.reporter.setUpReporter()
        self.benchmark = benchmark
        self.startTime, self.endTime = None, None
        self.numTests = 0
        self.children = []
        self.parent = self
        if benchmark:
            self._registerBenchmarkAdapters()

    def _registerBenchmarkAdapters(self):
        from twisted import trial
        trial.benchmarking = True

    def addTest(self, test):
        test.janitor = self.janitor
        test.debugger = self.debugger
        TestSuite.addTest(self, test)

    def addMethod(self, method):
        self.addTest(itrial.ITestRunner(method))

    def addTestClass(self, testClass):
        self.addTest(makeTestRunner(testClass))

    def addModule(self, module):
        self.addTest(TestModuleRunner(module))
        if hasattr(module, '__doctests__'):
            self.addDoctests(module.__doctests__)

    def addDoctests(self, obj):
        from twisted.trial import tdoctest
        self.addTest(tdoctest.ModuleDocTestsRunner(obj))
        
    def addPackage(self, package):
        for module in findTestModules(package):
            self.addModule(module)

    def _packageRecurse(self, arg, dirname, names):
        if not isPackageDirectory(dirname):
            names[:] = []
            return
        testModuleNames = fnmatch.filter(names, MODULE_GLOB)
        for name in testModuleNames:
            try:
                module = filenameToModule(opj(dirname, name))
            except ImportError:
                self.reporter.reportImportError(name, failure.Failure())
                continue
            self.addModule(module)

    def addPackageRecursive(self, package):
        packageDir = os.path.dirname(package.__file__)
        os.path.walk(packageDir, self._packageRecurse, None)

    def _getBenchmarkStats(self):
        stat = {}
        for r in self.children:
            for m in r.children:
                stat.update(getattr(m, 'benchmarkStats', {}))
        return stat
    benchmarkStats = property(_getBenchmarkStats)

    def _kickStopRunningStuff(self):
        self.endTime = time.time()
        # hand the reporter the TrialRoot to give it access to all information
        # from the test run
        self.reporter.endSuite(self)
        try:
            self.reporter.tearDownReporter()
        except:
            t, v, tb = sys.exc_info()
            raise RuntimeError, "your reporter is broken %r" % \
                  (''.join(v),), tb
        self._bail()

    def setStartTime(self):
        self.startTime = time.time()

    def _bail(self):
        from twisted.internet import reactor
        d = defer.Deferred()
        reactor.addSystemEventTrigger('after', 'shutdown', lambda: d.callback(None))
        reactor.fireSystemEvent('shutdown') # radix's suggestion
        treactor = interfaces.IReactorThreads(reactor, None)
        if treactor is not None:
            treactor.suggestThreadPoolSize(0)
        util.wait(d) # so that the shutdown event completes

    def _initLogging(self):
        log.startKeepingErrors()

    def run(self, randomize=None):
        self._initLogging()
        self.setStartTime()
        if randomize is not None:
            self.reporter.write('Running tests shuffled with seed %d' % randomize)
        # this is where the test run starts
        self.reporter.startSuite(self.countTestCases())
        for tr in self._getChildren(randomize):
            tr.run(self.reporter, (randomize is not None))
            if self.reporter.shouldStop:
                break
        if self.benchmark:
            pickle.dump(self.benchmarkStats, file("test.stats", 'wb'))
        self._kickStopRunningStuff()

    def _populateChildren(self):
        pass
    
    def visit(self, visitor):
        """Call visitor,visitSuite(self) and visit all child tests."""
        visitor.visitSuite(self)
        self._visitChildren(visitor)
        visitor.visitSuiteAfter(self)

    def _visitChildren(self, visitor):
        """Visit all chilren of this test suite."""
        for case in self._getChildren():
            case.visit(visitor)


class MethodInfoBase(object):
    zi.implements(itrial.IMethodInfo)
    def __init__(self, original):
        self.original = o = original
        self.name = o.__name__
        self.klass  = original.im_class
        self.module = reflect.namedModule(original.im_class.__module__)
        self.fullName = "%s.%s.%s" % (self.module.__name__, self.klass.__name__,
                                      self.name)
        self.docstr = (o.__doc__ or None)
        self.startTime = 0.0
        self.endTime = 0.0
        self.errors = []

    def runningTime(self):
        return self.endTime - self.startTime


class UserMethodError(Exception):
    """indicates that the user method had an error, but raised after
    call is complete
    """

class UserMethodWrapper(MethodInfoBase):
    def __init__(self, original, janitor, raiseOnErr=True, timeout=None,
                 suppress=None):
        super(UserMethodWrapper, self).__init__(original)
        self.janitor = janitor
        self.original = original
        self.timeout = timeout
        self.errors = []
        self.raiseOnErr = raiseOnErr
        self.suppress = suppress

    def __call__(self, *a, **kw):
        timeout = getattr(self, 'timeout', None)
        if timeout is None:
            timeout = getattr(self.original, 'timeout', util.DEFAULT_TIMEOUT)
        self.startTime = time.time()
        def run():
            return util.wait(
                defer.maybeDeferred(self.original, *a, **kw),
                timeout, useWaitError=True)
        try:
            _runWithWarningFilters(self.suppress, run)
        except util.MultiError, e:
            for f in e.failures:
                self.errors.append(f)
        self.endTime = time.time()
        for e in self.errors:
            self.errorHook(e)
        if self.raiseOnErr and self.errors:
            raise UserMethodError

    def errorHook(self, fail):
        pass


class TestRunnerBase(TestSuite):
    zi.implements(itrial.ITestRunner)
    _tcInstance = None
    methodNames = setUpClass =estSuitorDownClast = methodsWithStatus = None
    children = parent = None
    testCaseInstance = lambda self: None
    skip = None
    
    def __init__(self, original):
        self.original = original
        self.methodsWithStatus = {}
        self.children = []
        self.startTime, self.endTime = None, None
        self._signalStateMgr = util.SignalStateManager()

    def doCleanup(self):
        """do cleanup after the test run. check log for errors, do reactor
        cleanup, and restore signals to the state they were in before the
        test ran
        """
        return self.janitor.postCaseCleanup()

    def run(self, reporter, randomize):
        """Run all tests for this test runner, catching all exceptions.
        If a KeyboardInterrupt is caught set reporter.shouldStop."""
        _kickStartReactor()
        try:
            self.runTests(reporter, randomize=randomize)
        except KeyboardInterrupt:
            # KeyboardInterrupts are normal, not a bug in trial.
            # Just stop the test run, and do the usual reporting.
            log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
            reporter.shouldStop = True
        except:
            # Any other exception is problem.  Report it.
            f = failure.Failure()
            annoyingBorder = "-!*@&" * 20
            trialIsBroken = """
\tWHOOP! WHOOP! DANGER WILL ROBINSON! DANGER! WHOOP! WHOOP!
\tcaught exception in TrialRoot! \n\n\t\tTRIAL IS BROKEN!\n\n
\t%s""" % ('\n\t'.join(f.getTraceback().split('\n')),)
            print "\n%s\n%s\n\n%s\n" % \
                  (annoyingBorder, trialIsBroken, annoyingBorder)

    def _visitChildren(self, visitor):
        """Visit all chilren of this test suite."""
        for case in self._getChildren():
            case.visit(visitor)


def _runWithWarningFilters(filterlist, f, *a, **kw):
    """calls warnings.filterwarnings(*item[0], **item[1]) 
    for each item in alist, then runs func f(*a, **kw) and 
    resets warnings.filters to original state at end
    """
    filters = warnings.filters[:]
    try:
        if filterlist is not None:
            for args, kwargs in filterlist:
                warnings.filterwarnings(*args, **kwargs)
        return f(*a, **kw)
    finally:
        warnings.filters = filters[:]


def _bogusCallable(ignore=None):
    pass


class TestModuleRunner(TestRunnerBase):
    _tClasses = _mnames = None
    def __init__(self, original):
        super(TestModuleRunner, self).__init__(original)
        self.module = self.original
        self.skip = getattr(self.original, 'skip', None)
        self.todo = getattr(self.original, 'todo', None)
        self.timeout = getattr(self.original, 'timeout', None)
        self.children = []

    def runTests(self, reporter, randomize=False):
        reporter.startModule(self.original)
        for runner in self._getChildren(randomize):
            runner.runTests(reporter, randomize)
            for k, v in runner.methodsWithStatus.iteritems():
                self.methodsWithStatus.setdefault(k, []).extend(v)
        reporter.endModule(self.original)

    def _populateChildren(self):
        for testClass in findTestClasses(self.original):
            runner = makeTestRunner(testClass)
            runner.janitor = self.janitor
            runner.debugger = self.debugger
            self.addTest(runner)

    def visit(self, visitor):
        """Call visitor,visitModule(self) and visit all child tests."""
        visitor.visitModule(self)
        self._visitChildren(visitor)
        visitor.visitModuleAfter(self)


class TestClassAndMethodBase(TestRunnerBase):
    """base class for *Runner classes providing the testCaseInstance, running
    the appropriate prefixed-methods as tests
    """
    _module = _tcInstance = None
    
    def testCaseInstance(self):
        # a property getter, called by subclasses
        if not self._tcInstance:
            self._tcInstance = self._testCase()
        return self._tcInstance
    testCaseInstance = property(testCaseInstance)

    def module(self):
        if self._module is None:
            self._module = reflect.namedAny(self._testCase.__module__)
        return self._module
    module = property(module)

    def _populateChildren(self):
        for mname in self.methodNames:
            m = getattr(self._testCase, mname)
            tm = itrial.ITestMethod(m, None)
            if tm == None:
                continue
            tm.parent = self
            self.children.append(tm)

    def recordMethodStatus(self, testMethod):
        self.methodsWithStatus.setdefault(testMethod.status,
                                          []).append(testMethod)

    def runTests(self, reporter, randomize=False):
        janitor = self.janitor
        tci = self.testCaseInstance
        self.startTime = time.time()
        try:
            self._signalStateMgr.save()
            reporter.startClass(self._testCase)
            # --- setUpClass -----------------------------------------------
            setUpClass = UserMethodWrapper(self.setUpClass, janitor,
                                           suppress=self.suppress)
            try:
                if not getattr(tci, 'skip', None):
                    setUpClass()
            except UserMethodError:
                for error in setUpClass.errors:
                    if error.check(unittest.SkipTest):
                        self.skip = error.value[0]
                        break                   # <--- skip the else: clause
                    elif error.check(KeyboardInterrupt):
                        log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
                        error.raiseException()
                else:
                    reporter.upDownError(setUpClass)
                    for tm in self._getChildren():
                        tm.errors.extend(setUpClass.errors)
                        reporter.startTest(tm)
                        self.recordMethodStatus(tm)
                        reporter.endTest(tm)
                    return

            # --- run methods ----------------------------------------------
            for testMethod in self._getChildren(randomize):
                log.msg("--> %s.%s.%s <--" % (testMethod.module.__name__,
                                              testMethod.klass.__name__,
                                              testMethod.name))
                # suppression is handled by each testMethod
                testMethod.run(reporter, tci)
                self.recordMethodStatus(testMethod)

            # --- tearDownClass ---------------------------------------------
            tearDownClass = UserMethodWrapper(self.tearDownClass, janitor,
                                   suppress=self.suppress)
            try:
                if not getattr(tci, 'skip', None):
                    tearDownClass()
            except UserMethodError:
                for error in tearDownClass.errors:
                    if error.check(KeyboardInterrupt):
                        log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
                        error.raiseException()
                else:
                    reporter.upDownError(tearDownClass)
        finally:
            try:
                self.doCleanup()
            except util.MultiError, e:
                reporter.cleanupErrors(e.failures)
            self._signalStateMgr.restore()
            reporter.endClass(self._testCase)
            self.endTime = time.time()
        
    def visit(self, visitor):
        """Call visitor,visitClass(self) and visit all child tests."""
        visitor.visitClass(self)
        self._visitChildren(visitor)
        visitor.visitClassAfter(self)


class TestCaseRunner(TestClassAndMethodBase):
    """I run L{twisted.trial.unittest.TestCase} instances and provide
    the correct setUp/tearDownClass methods, method names, and values for
    'magic attributes'. If this TestCase defines an attribute, it is taken
    as the value, if not, we search the parent for the appropriate attribute
    and if we still find nothing, we set our attribute to None
    """
    methodPrefix = 'test'
    def __init__(self, original):
        super(TestCaseRunner, self).__init__(original)
        self.original = original
        self._testCase = self.original

        self.setUpClass = getattr(self.testCaseInstance, 'setUpClass',
                                  _bogusCallable)
        self.tearDownClass = getattr(self.testCaseInstance, 'tearDownClass',
                                     _bogusCallable)

        self.methodNames = [name for name in dir(self.testCaseInstance)
                            if name.startswith(self.methodPrefix)]

        for attr in MAGIC_ATTRS:
            objs = self.original, self.module
            setattr(self, attr, util._selectAttr(attr, *objs))


class TestCaseMethodRunner(TestClassAndMethodBase):
    """I run single test methods"""
    # formerly known as SingletonRunner
    def __init__(self, original):
        super(TestCaseMethodRunner, self).__init__(original)
        self.original = o = original
        self._testCase = o.im_class
        self.methodNames = [o.__name__]
        self.setUpClass = self.testCaseInstance.setUpClass
        self.tearDownClass = self.testCaseInstance.tearDownClass

        for attr in MAGIC_ATTRS:
            objs = [self.original, self._testCase,
                    inspect.getmodule(self._testCase)]
            setattr(self, attr, util._selectAttr(attr, *objs))
        

class PyUnitTestCaseRunner(TestClassAndMethodBase):
    """I run python stdlib TestCases"""
    def __init__(self, original):
        original.__init__ = lambda _: None
        super(PyUnitTestCaseRunner, self).__init__(original)

    testCaseInstance = property(TestClassAndMethodBase.testCaseInstance)


class BenchmarkCaseRunner(TestCaseRunner):
    """I run benchmarking tests"""
    methodPrefix = 'benchmark'
        

class StatusMixin:
    _status = None
    def _getStatus(self):
        if self._status is None:
            if self.todo is not None and (self.failures or self.errors):
                self._status = self._checkTodo()
            elif self.skip is not None:
                self._status = SKIP
            elif self.errors:
                self._status = ERROR
            elif self.failures:
                self._status = FAILURE
            elif self.todo:
                self._status = UNEXPECTED_SUCCESS
            else:
                self._status = SUCCESS
        return self._status
    status = property(_getStatus)


class TestMethod(MethodInfoBase, StatusMixin):
    zi.implements(itrial.ITestMethod, itrial.IMethodInfo)
    parent = None

    def __init__(self, original):
        super(TestMethod, self).__init__(original)

        self.setUp = self.klass.setUp
        self.tearDown = self.klass.tearDown

        self.runs = 0
        self.failures = []
        self.stdout = ''
        self.stderr = ''
        self.logevents = []

        self._skipReason = None  
        self._signalStateMgr = util.SignalStateManager()

    def _checkTodo(self):
        # returns EXPECTED_FAILURE for now if ITodo.types is None for
        # backwards compatiblity but as of twisted 2.1, will return FAILURE
        # or ERROR as appropriate
        #
        # TODO: This is a bit simplistic for right now, it makes sure all
        # errors and/or failures are of the type(s) specified in
        # ITodo.types, else it returns EXPECTED_FAILURE. This should
        # probably allow for more complex specifications. Perhaps I will
        # define a Todo object that will allow for greater
        # flexibility/complexity.

        for f in self.failures + self.errors:
            if not itrial.ITodo(self.todo).isExpected(f):
                return ERROR
        return EXPECTED_FAILURE
        
    def countTestCases(self):
        return 1

    def _getSkip(self):
        return (getattr(self.original, 'skip', None) \
                or self._skipReason or self.parent.skip)
    def _setSkip(self, value):
        self._skipReason = value
    skip = property(_getSkip, _setSkip)

    def todo(self):
        return util._selectAttr('todo', self.original, self.parent)
    todo = property(todo)
    
    def suppress(self):
        return util._selectAttr('suppress', self.original, self.parent)
    suppress = property(suppress)

    def timeout(self):
        if hasattr(self.original, 'timeout'):
            return self.original.timeout
        else:
            return getattr(self.parent, 'timeout', util.DEFAULT_TIMEOUT)
    timeout = property(timeout)

    def hasTbs(self):
        return self.errors or self.failures
    hasTbs = property(hasTbs)

    def _eb(self, f):
        log.msg(f.printTraceback())
        if f.check(util.DirtyReactorWarning):
            # This will eventually become an error, but for now
            # we delegate the responsibility of warning the user
            # to the reporter so that we can test for this
            self.getReporter().cleanupErrors(f)
        elif f.check(unittest.FAILING_EXCEPTION,
                   unittest.FailTest):
            self.failures.append(f)
        elif f.check(KeyboardInterrupt):
            log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
        elif f.check(unittest.SkipTest):
            if len(f.value.args) > 0:
                reason = f.value.args[0]
            else:
                warnings.warn(("Do not raise unittest.SkipTest with no "
                               "arguments! "
                               "Give a reason for skipping tests!"),
                              stacklevel=2)
                reason = f
            self._skipReason = reason
        else:
            self.errors.append(f)


    def run(self, reporter, testCaseInstance):
        self.testCaseInstance = tci = testCaseInstance
        self.runs += 1
        self.startTime = time.time()
        self._signalStateMgr.save()
        janitor = self.parent.janitor
        if self.skip: # don't run test methods that are marked as .skip
            reporter.startTest(self)
            reporter.endTest(self)
            return
        try:
            # capture all a TestMethod run's log events (warner's request)
            observer = util._TrialLogObserver().install()
            
            # Record the name of the running test on the TestCase instance
            tci._trial_caseMethodName = self.original.func_name

            # Run the setUp method
            setUp = UserMethodWrapper(self.setUp, janitor,
                                      suppress=self.suppress)
            try:
                setUp(tci)
            except UserMethodError:
                for error in setUp.errors:
                    if error.check(KeyboardInterrupt):
                        error.raiseException()
                    self._eb(error)
                else:
                    # give the reporter the illusion that the test has 
                    # run normally but don't actually run the test if 
                    # setUp is broken
                    reporter.startTest(self)
                    reporter.upDownError(setUp, warn=False,
                                         printStatus=False)
                    return
                 
            # Run the test method
            reporter.startTest(self)
            try:
                if not self.parent.debugger:
                    sys.stdout = util._StdioProxy(sys.stdout)
                    sys.stderr = util._StdioProxy(sys.stderr)
                orig = UserMethodWrapper(self.original, janitor,
                                         raiseOnErr=False,
                                         timeout=self.timeout,
                                         suppress=self.suppress)
                orig.errorHook = self._eb
                orig(tci)

            finally:
                self.endTime = time.time()

                if not self.parent.debugger:
                    self.stdout = sys.stdout.getvalue()
                    self.stderr = sys.stderr.getvalue()
                    sys.stdout = sys.stdout.original
                    sys.stderr = sys.stderr.original

                # Run the tearDown method
                um = UserMethodWrapper(self.tearDown, janitor,
                                       suppress=self.suppress)
                try:
                    um(tci)
                except UserMethodError:
                    for error in um.errors:
                        self._eb(error)
                    else:
                        reporter.upDownError(um, warn=False)
        finally:
            observer.remove()
            self.logevents = observer.events
            self.doCleanup()
            reporter.endTest(self)
            self._signalStateMgr.restore()

    def doCleanup(self):
        """do cleanup after the test run. check log for errors, do reactor
        cleanup
        """
        try:
            self.parent.janitor.postMethodCleanup()
        except util.MultiError, e:
            for f in e.failures:
                self._eb(f)
            return e.failures
            
    def visit(self, visitor):
        """Call visitor.visitCase(self)."""
        visitor.visitCase(self)


class BenchmarkMethod(TestMethod):
    def __init__(self, original):
        super(BenchmarkMethod, self).__init__(original)
        self.benchmarkStats = {}

    def run(self, reporter, testCaseInstance):
        # WHY IS THIS MONKEY PATCH HERE?
        def _recordStat(datum):
            self.benchmarkStats[self.fullName] = datum
        testCaseInstance.recordStat = _recordStat
        self.original(testCaseInstance)
        
