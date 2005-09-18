# -*- test-case-name: twisted.trial.test.test_trial -*-

#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Original Author: Jonathan Lange <jml@twistedmatrix.com>

from __future__ import generators


import os, glob, types, warnings, time, sys, cPickle as pickle, inspect
import fnmatch, random, inspect, doctest
from os.path import join as opj

from twisted.internet import defer, interfaces
from twisted.python import components, reflect, log, failure
from twisted.python.util import dsu
from twisted.trial import itrial, util, unittest
from twisted.trial.itrial import ITestCase, IReporter, ITrialDebug
import zope.interface as zi

pyunit = __import__('unittest')


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


def isPackageDirectory(dirname):
    """Is the directory at path 'dirname' a Python package directory?"""
    for ext in 'py', 'so', 'pyd', 'dll':
        if os.path.exists(os.path.join(dirname,
                                       os.extsep.join(('__init__', ext)))):
            return True
        return False


def filenameToModule(fn):
    return reflect.namedModule(reflect.filenameToModuleName(fn))


class TestSuite(pyunit.TestSuite):
    def visit(self, visitor):
        for case in self._tests:
            case.visit(visitor)


class DocTestSuite(TestSuite):
    def __init__(self, testModule):
        TestSuite.__init__(self)
        suite = doctest.DocTestSuite(testModule)
        for test in suite._tests: #yay encapsulation
            self.addTest(PyUnitTestMethod(test))


class PyUnitTestMethod(object):
    zi.implements(itrial.ITestMethod)

    def __init__(self, test):
        self._test = test

    def __call__(self, result):
        return self.run(result)

    def countTestCases(self):
        return 1

    def id(self):
        return self._test.shortDescription()

    def shortDescription(self):
        return self._test.shortDescription()

    def getTodo(self):
        pass

    def getSkip(self):
        pass

    def getTimeout(self):
        pass

    def getSuppress(self):
        pass

    def run(self, reporter):
        return self._test.run(reporter)
        
    def visit(self, visitor):
        """Call visitor.visitCase(self)."""
        visitor.visitCase(self)


class TrialRoot(pyunit.TestSuite):
    """This is the main organizing object. The front-end script creates a
    TrialRoot, and tells it what modules were requested on the command line.
    It also hands it a reporter. The TrialRoot then takes all of the
    packages, modules, classes and methods, and adapts them to ITestRunner
    objects, which it then calls the run method on.
    """
    zi.implements(itrial.ITrialRoot)

    def __init__(self, reporter, benchmark=0, randomize=None):
        pyunit.TestSuite.__init__(self)
        self.reporter = IReporter(reporter)
        self.reporter.setUpReporter()
        self.loader = TestLoader(reporter)
        self.startTime, self.endTime = None, None
        self.benchmark = benchmark
        if benchmark:
            self.loader.classSuiteFactory = BenchmarkClassSuite
            self.loader.testMethodFactory = BenchmarkMethod
            self.loader.methodPrefix = 'benchmark'
        if randomize:
            randomer = random.Random()
            randomer.seed(randomize)
            self.loader.sorter = lambda x : randomer.random()
            self.reporter.write('Running tests shuffled with seed %d\n'
                                % randomize)

    def addMethod(self, method):
        self.addTest(self.loader.loadMethod(method))

    def addTestClass(self, testClass):
        self.addTest(self.loader.loadClass(testClass))

    def addModule(self, module):
        self.addTest(self.loader.loadModule(module))

    def addPackage(self, package):
        self.addTest(self.loader.loadPackage(package))

    def addPackageRecursive(self, package):
        self.addTest(self.loader.loadPackageRecursive(package))

    def addDoctests(self, doctests):
        for doctest in doctests:
            self.addDoctest(doctest)

    def addDoctest(self, doctest):
        self.addTest(self.loader.loadDoctests(doctest))

    def _getBenchmarkStats(self):
        # XXX -- This code assumes that there are two nested suites.
        # This assumption is not warranted in any fashion.  Probably replace
        # with a visitor pattern thing -- jml
        stat = {}
        for r in self._tests:
            for m in r._tests:
                stat.update(getattr(m, 'benchmarkStats', {}))
        return stat
    benchmarkStats = property(_getBenchmarkStats)

    def _kickStopRunningStuff(self):
        self.endTime = time.time()
        # hand the reporter the TrialRoot to give it access to all information
        # from the test run
        self.reporter.endTrial(self)
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

    def run(self):
        self._initLogging()
        self.setStartTime()
        # this is where the test run starts
        self.reporter.startTrial(self.countTestCases())
        for tr in self._tests:
            tr.run(self.reporter)
            if self.reporter.shouldStop:
                break
        if self.benchmark:
            pickle.dump(self.benchmarkStats, file("test.stats", 'wb'))
        self._kickStopRunningStuff()

    def visit(self, visitor):
        """Call visitor,visitSuite(self) and visit all child tests."""
        visitor.visitTrial(self)
        self._visitChildren(visitor)
        visitor.visitTrialAfter(self)

    def _visitChildren(self, visitor):
        """Visit all chilren of this test suite."""
        for case in self._tests:
            case.visit(visitor)

    def runningTime(self):
        return self.endTime - self.startTime


class UserMethodError(Exception):
    """indicates that the user method had an error, but raised after
    call is complete
    """

class UserMethodWrapper(object):
    def __init__(self, original, raiseOnErr=True, timeout=None, suppress=None):
        self.original = original
        self.timeout = timeout
        self.raiseOnErr = raiseOnErr
        self.errors = []
        self.suppress = suppress
        self.name = original.__name__

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
            self._runWithWarningFilters(run)
        except util.MultiError, e:
            for f in e.failures:
                self.errors.append(f)
        self.endTime = time.time()
        for e in self.errors:
            self.errorHook(e)
        if self.raiseOnErr and self.errors:
            raise UserMethodError

    def _runWithWarningFilters(self, f, *a, **kw):
        """calls warnings.filterwarnings(*item[0], **item[1]) 
        for each item in alist, then runs func f(*a, **kw) and 
        resets warnings.filters to original state at end
        """
        filters = warnings.filters[:]
        try:
            if self.suppress is not None:
                for args, kwargs in self.suppress:
                    warnings.filterwarnings(*args, **kwargs)
            return f(*a, **kw)
        finally:
            warnings.filters = filters[:]

    def errorHook(self, fail):
        pass


class TestRunnerBase(pyunit.TestSuite):
    zi.implements(itrial.ITestRunner)
    
    def __init__(self, original):
        pyunit.TestSuite.__init__(self)
        self.original = original

    def __call__(self, reporter):
        return self.run(reporter)

    def run(self, reporter):
        """Run all tests for this test runner, catching all exceptions.
        If a KeyboardInterrupt is caught set reporter.shouldStop."""
        _kickStartReactor()
        try:
            self.runTests(reporter)
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
        for case in self._tests:
            case.visit(visitor)


class ModuleSuite(TestRunnerBase):
    def runTests(self, reporter):
        reporter.startModule(self.original)
        for runner in self._tests:
            runner.runTests(reporter)
        reporter.endModule(self.original)

    def visit(self, visitor):
        """Call visitor,visitModule(self) and visit all child tests."""
        visitor.visitModule(self)
        self._visitChildren(visitor)
        visitor.visitModuleAfter(self)


class ClassSuite(TestRunnerBase):
    """I run L{twisted.trial.unittest.TestCase} instances and provide
    the correct setUp/tearDownClass methods, method names, and values for
    'magic attributes'. If this TestCase defines an attribute, it is taken
    as the value, if not, we search the parent for the appropriate attribute
    and if we still find nothing, we set our attribute to None
    """
    methodPrefix = 'test'

    def __init__(self, original):
        TestRunnerBase.__init__(self, original)
        self.original = original
        self._testCase = self.original
        self._signalStateMgr = util.SignalStateManager()
        self._janitor = util._Janitor()

    _module = _tcInstance = None
    
    def testCaseInstance(self):
        # a property getter, called by subclasses
        if not self._tcInstance:
            self._tcInstance = self._testCase()
        return self._tcInstance
    testCaseInstance = property(testCaseInstance)

    def _setUpClass(self):
        if not hasattr(self.testCaseInstance, 'setUpClass'):
            return lambda : None
        setUp = self.testCaseInstance.setUpClass
        suppress = acquireAttribute(
            getPythonContainers(setUp), 'suppress', None)
        return UserMethodWrapper(setUp, suppress=suppress)

    def _tearDownClass(self):
        if not hasattr(self.testCaseInstance, 'tearDownClass'):
            return lambda : None
        tearDown = self.testCaseInstance.tearDownClass
        suppress = acquireAttribute(
            getPythonContainers(tearDown), 'suppress', None)
        return UserMethodWrapper(tearDown, suppress=suppress)

    def runTests(self, reporter):
        janitor = util._Janitor()
        tci = self.testCaseInstance
        self.startTime = time.time()
        try:
            self._signalStateMgr.save()
            reporter.startClass(self._testCase)
            # --- setUpClass -----------------------------------------------
            setUpClass = self._setUpClass()
            try:
                if not getattr(tci, 'skip', None):
                    setUpClass()
            except UserMethodError:
                for error in setUpClass.errors:
                    if error.check(unittest.SkipTest):
                        self.original.skip = error.value[0]
                        break                   # <--- skip the else: clause
                    elif error.check(KeyboardInterrupt):
                        log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
                        error.raiseException()
                else:
                    reporter.upDownError(setUpClass)
                    for tm in self._tests:
                        for error in setUpClass.errors:
                            reporter.addError(tm, error)
                        reporter.startTest(tm)
                        reporter.endTest(tm)
                    return

            # --- run methods ----------------------------------------------
            for testMethod in self._tests:
                log.msg("--> %s <--" % (testMethod.id()))
                # suppression is handled by each testMethod
                testMethod.run(reporter, tci)

            # --- tearDownClass ---------------------------------------------
            tearDownClass = self._tearDownClass()
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
                janitor.postCaseCleanup()
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


class BenchmarkClassSuite(ClassSuite):
    """I run benchmarking tests"""
    methodPrefix = 'benchmark'
        

def getPythonContainers(meth):
    """Walk up the Python tree from method 'meth', finding its class, its module
    and all containing packages."""
    containers = []
    containers.append(meth.im_class)
    moduleName = meth.im_class.__module__
    while moduleName is not None:
        module = sys.modules.get(moduleName, None)
        if module is None:
            module = __import__(moduleName)
        containers.append(module)
        moduleName = getattr(module, '__module__', None)
    return containers


_DEFAULT = object()
def acquireAttribute(objects, attr, default=_DEFAULT):
    """Go through the list 'objects' sequentially until we find one which has
    attribute 'attr', then return the value of that attribute.  If not found,
    return 'default' if set, otherwise, raise AttributeError. """
    for obj in objects:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    if default is not _DEFAULT:
        return default
    raise AttributeError('attribute %r not found in %r' % (attr, objects))


class TestMethod(object):
    zi.implements(itrial.ITestMethod)
    parent = None

    def __init__(self, original):
        self.original = original
        self._setUp = original.im_class.setUp
        self._tearDown = original.im_class.tearDown
        self._signalStateMgr = util.SignalStateManager()
        self._parents = [original] + getPythonContainers(original)

    def countTestCases(self):
        return 1

    def getSkip(self):
        return acquireAttribute([self] + self._parents, 'skip', None)

    def getTodo(self):
        return acquireAttribute(self._parents, 'todo', None)
    
    def getSuppress(self):
        return acquireAttribute(self._parents, 'suppress', None)

    def getTimeout(self):
        return acquireAttribute(self._parents, 'timeout', None)

    def runningTime(self):
        return self.endTime - self.startTime

    def id(self):
        k = self.original.im_class
        return '%s.%s.%s' % (k.__module__, k.__name__, self.original.__name__)

    def shortDescription(self):
        doc = getattr(self.original, '__doc__', None)
        if doc is not None:
            return doc.lstrip().split('\n', 1)[0]
        return self.original.__name__

    def _eb(self, f, reporter):
        log.msg(f.printTraceback())
        if f.check(util.DirtyReactorWarning):
            reporter.cleanupErrors(f)
        elif f.check(unittest.FAILING_EXCEPTION,
                   unittest.FailTest):
            reporter.addFailure(self, f)
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
            self.skip = reason
        else:
            reporter.addError(self, f)

    def run(self, reporter, testCaseInstance):
        self.testCaseInstance = tci = testCaseInstance
        self.startTime = time.time()
        self._signalStateMgr.save()
        janitor = util._Janitor()
        if self.getSkip(): # don't run test methods that are marked as .skip
            reporter.startTest(self)
            reporter.endTest(self)
            return
        try:
            # capture all a TestMethod run's log events (warner's request)
            observer = util._TrialLogObserver().install()
            
            # Record the name of the running test on the TestCase instance
            tci._trial_caseMethodName = self.original.func_name

            # Run the setUp method
            setUp = UserMethodWrapper(self._setUp, suppress=self.getSuppress())
            try:
                setUp(tci)
            except UserMethodError:
                for error in setUp.errors:
                    if error.check(KeyboardInterrupt):
                        error.raiseException()
                    self._eb(error, reporter)
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
                orig = UserMethodWrapper(self.original,
                                         raiseOnErr=False,
                                         timeout=self.getTimeout(),
                                         suppress=self.getSuppress())
                orig.errorHook = lambda x : self._eb(x, reporter)
                orig(tci)
            finally:
                self.endTime = time.time()
                # Run the tearDown method
                um = UserMethodWrapper(self._tearDown,
                                       suppress=self.getSuppress())
                try:
                    um(tci)
                except UserMethodError:
                    for error in um.errors:
                        self._eb(error, reporter)
                    else:
                        reporter.upDownError(um, warn=False)
        finally:
            observer.remove()
            try:
                janitor.postMethodCleanup()
            except util.MultiError, e:
                for f in e.failures:
                    self._eb(f, reporter)
            reporter.endTest(self)
            self._signalStateMgr.restore()

    def visit(self, visitor):
        """Call visitor.visitCase(self)."""
        visitor.visitCase(self)


class BenchmarkMethod(TestMethod):
    def __init__(self, original):
        TestMethod.__init__(self, original)
        self.benchmarkStats = {}

    def run(self, reporter, testCaseInstance):
        # WHY IS THIS MONKEY PATCH HERE?
        def _recordStat(datum):
            self.benchmarkStats[self.id()] = datum
        testCaseInstance.recordStat = _recordStat
        self.original(testCaseInstance)
        

class TestLoader(object):
    methodPrefix = 'test'
    moduleGlob = 'test_*.py'

    def __init__(self, reporter):
        self.reporter = reporter
        self.suiteFactory = TestSuite
        self.moduleSuiteFactory = ModuleSuite
        self.classSuiteFactory = ClassSuite
        self.testMethodFactory = TestMethod
        self.sorter = lambda x : x.__name__

    def _findTestClasses(self, module):
        """Given a module, return all trial Test classes"""
        classes = []
        for name, val in inspect.getmembers(module):
            try:
                if ITestCase.implementedBy(val):
                    classes.append(val)
            except TypeError:
                # val is not a class / type, and therefore not a test class
                pass
        return dsu(classes, self.sorter)

    def _findTestModules(self, package):
        modGlob = os.path.join(os.path.dirname(package.__file__), self.moduleGlob)
        return dsu(map(filenameToModule, glob.glob(modGlob)), self.sorter)

    def loadModule(self, module):
        suite = self.moduleSuiteFactory(module)
        for testClass in self._findTestClasses(module):
            suite.addTest(self.loadClass(testClass))
        if not hasattr(module, '__doctests__'):
            return suite
        docSuite = self.suiteFactory()
        if sys.version_info[:2] <= (2, 2):
            warnings.warn("trial's doctest support only works with "
                          "python 2.3 or later, not running doctests")
        else:
            for doctest in module.__doctests__:
                docSuite.addTest(self.loadDoctests(doctest))
        modSuite = self.suiteFactory()
        modSuite.addTests([suite, docSuite])
        return modSuite

    def loadClass(self, klass):
        if issubclass(klass, pyunit.TestCase):
            klass.__init__ = lambda _: None
        factory = self.classSuiteFactory
        instance = klass()
        methods = dsu([ getattr(klass, name) for name in dir(instance)
                        if name.startswith(self.methodPrefix)
                        and callable(getattr(instance, name)) ],
                      self.sorter)
        suite = factory(klass)
        for method in methods:
            suite.addTest(self.loadTestMethod(method))
        return suite

    def loadMethod(self, method):
        suite = self.classSuiteFactory(method.im_class)
        suite.addTest(self.loadTestMethod(method))
        return suite

    def loadTestMethod(self, method):
        return self.testMethodFactory(method)

    def loadPackage(self, package):
        suite = self.suiteFactory()
        for module in self._findTestModules(package):
            suite.addTest(self.loadModule(module))
        return suite

    def _packageRecurse(self, suite, dirname, names):
        if not isPackageDirectory(dirname):
            names[:] = []
            return
        testModuleNames = fnmatch.filter(names, self.moduleGlob)
        for name in testModuleNames:
            try:
                module = filenameToModule(opj(dirname, name))
            except ImportError:
                self.reporter.reportImportError(name, failure.Failure())
                continue
            suite.addTest(self.loadModule(module))

    def loadPackageRecursive(self, package):
        packageDir = os.path.dirname(package.__file__)
        suite = self.suiteFactory()
        os.path.walk(packageDir, self._packageRecurse, suite)
        return suite

    def loadDoctests(self, module):
        if sys.version_info[:2] <= (2, 2):
            warnings.warn("trial's doctest support only works with "
                          "python 2.3 or later, not running doctests")
            return
        if isinstance(module, str):
            module = reflect.namedAny(module)
        if not inspect.ismodule(module):
            warnings.warn("trial only supports doctesting modules")
            return
        return DocTestSuite(module)
