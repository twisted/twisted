# -*- test-case-name: twisted.trial.test.test_trial -*-

#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Original Author: Jonathan Lange <jml@twistedmatrix.com>

#  B{What's going on here?}
#
#  I've been staring at this file for about 3 weeks straight, and it seems
#  like a good place to write down how all this stuff works.
#
#  The program flow goes like this:
#
#  The twisted.scripts.trial module parses command line options, creates a
#  TestSuite and passes it the _Janitor and Reporter objects. It then adds
#  the modules, classes, and methods that the user requested that the suite
#  search for test cases. Then the script calls .runTests() on the suite.
#
#  The suite goes through each argument and calls ITestRunner(obj) on each
#  object. There are adapters that are registered for ModuleType, ClassType
#  and MethodType, so each one of these adapters knows how to run their
#  tests, and provides a common interface to the suite.
#
#  The module runner goes through the module and searches for classes that
#  implement itrial.TestCaseFactory, does setUpModule, adapts that module's
#  classes with ITestRunner(), and calls .run() on them in sequence.
#
#  The method runner wraps the method, locates the method's class and
#  modules so that the setUp{Module, Class, } can be run for that test.
#
#  ------
#
#  A word about reporters...
#
#  All output is to be handled by the reporter class. Warnings, Errors, etc.
#  are all given to the reporter and it decides what the correct thing to do
#  is depending on the options given on the command line. This allows the
#  runner code to concentrate on testing logic. The reporter is also given
#  Test-related objects wherever possible, not strings. It is not the job of
#  the runner to know what string should be output, it is the reporter's job
#  to know how to make sense of the data
#
#  -------
#
#  The test framework considers any user-written code *dangerous*, and it
#  wraps it in a UserMethodWrapper before execution. This allows us to
#  handle the errors in a sane, consistent way. The wrapper will run the
#  user-code, catching errors, and then checking for logged errors, saving
#  it to IUserMethod.errors.
#
#  (more to follow)
#
from __future__ import generators


import os, glob, types, warnings, time, sys, cPickle as pickle, inspect
import fnmatch, random
from os.path import join as opj

from twisted.internet import defer, interfaces
from twisted.python import components, reflect, log, failure
from twisted.trial import itrial, util, unittest
from twisted.trial.itrial import ITestCaseFactory, IReporter, ITrialDebug
from twisted.trial.reporter import SKIP, EXPECTED_FAILURE, FAILURE, \
     ERROR, UNEXPECTED_SUCCESS, SUCCESS
import zope.interface as zi


MAGIC_ATTRS = ('skip', 'todo', 'timeout', 'suppress')

# --- Exceptions and Warnings ------------------------ 

class BrokenTestCaseWarning(Warning):
    """emitted as a warning when an exception occurs in one of
    setUp, tearDown, setUpClass, or tearDownClass"""

class Timed(object):
    zi.implements(itrial.ITimed)
    startTime = None
    endTime = None

def _dbgPA(msg):
    log.msg(iface=itrial.ITrialDebug, parseargs=msg)

class TestSuite(Timed):
    """This is the main organizing object. The front-end script creates a
    TestSuite, and tells it what modules were requested on the command line.
    It also hands it a reporter. The TestSuite then takes all of the
    packages, modules, classes and methods, and adapts them to ITestRunner
    objects, which it then calls the runTests method on.
    """
    zi.implements(itrial.ITestSuite)
    moduleGlob = 'test_*.py'
    sortTests = 1
    debugger = False
    dryRun = False

    def __init__(self, reporter, janitor, benchmark=0):
        self.reporter = IReporter(reporter)
        self.janitor = itrial.IJanitor(janitor)
        

        # XXX NO NO NO NO NO NO NO NO NO NO GOD DAMNIT NO YOU CANNOT DO THIS
        # IT IS NOT ALLOWED DO NOT CALL WAIT() ANYWHERE EVER FOR ANY REASON
        # *EVER*
        util.wait(self.reporter.setUpReporter())



        self.benchmark = benchmark
        self.startTime, self.endTime = None, None
        self.numTests = 0
        self.couldNotImport = {}
        self.tests = []
        self.children = []
        if benchmark:
            self._registerBenchmarkAdapters()

    def _registerBenchmarkAdapters(self):
        from twisted import trial
        trial.benchmarking = True

    def addMethod(self, method):
        self.tests.append(method)

    def _getMethods(self):
        for runner in self.children:
            for meth in runner.children:
                yield meth
    methods = property(_getMethods)
        
    def addTestClass(self, testClass):
        if ITestCaseFactory.providedBy(testClass):
            self.tests.append(testClass)
        else:
            warnings.warn(("didn't add %s because it does not implement "
                           "ITestCaseFactory" % testClass))

    def addModule(self, module):
        if isinstance(module, types.StringType):
            _dbgPA("addModule: %r" % (module,))
            try:
                module = reflect.namedModule(module)
            except:
                self.couldNotImport[module] = failure.Failure()
                return

        if isinstance(module, types.ModuleType):
            _dbgPA("adding module: %r" % module)
            self.tests.append(module)
        
        if hasattr(module, '__doctests__'):
            vers = sys.version_info[0:2]
            if vers[0] >= 2 and vers[1] >= 3:
                runner = itrial.ITestRunner(getattr(module, '__doctests__'))
                self.tests.append(runner)
            else:
                warnings.warn(("trial's doctest support only works with "
                               "python 2.3 or later, not running doctests"))

    def addDoctest(self, obj):
        # XXX: this is a crap adaptation, ListType is adapted to 
        # ITestRunner by tdoctest.ModuleDocTestsRunner
        # it is crappy crap, awful dreadful crap
        self.tests.append(itrial.ITestRunner([obj]))

    def addPackage(self, package):
        modGlob = os.path.join(os.path.dirname(package.__file__),
                               self.moduleGlob)
        modules = map(reflect.filenameToModuleName, glob.glob(modGlob))
        for module in modules:
            self.addModule(module)

    def _packageRecurse(self, arg, dirname, names):

        # Only recurse into packages
        for ext in 'py', 'so', 'pyd', 'dll':
            if os.path.exists(os.path.join(dirname, os.extsep.join(('__init__', ext)))):
                break
        else:
            return

        testModuleNames = fnmatch.filter(names, self.moduleGlob)
        testModules = [ reflect.filenameToModuleName(opj(dirname, name))
                        for name in testModuleNames ]
        for module in testModules:
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

    ####
    # the root of the ParentAttributeMixin tree
    def getJanitor(self):
        return self.janitor

    def getReporter(self):
        return self.reporter

    def isDebuggingRun(self):
        return self.debugger
    
    def isDryRun(self):
        return self.dryRun
    ####

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

    def run(self, seed=None):
        self.startTime = time.time()
        tests = self.tests
        if self.sortTests:
            # XXX twisted.python.util.dsu(tests, str)
            tests.sort(lambda x, y: cmp(str(x), str(y)))
        
        self._initLogging()

        # Kick-start things
        from twisted.internet import reactor
        reactor.callLater(0, reactor.crash)
        reactor.run()

        # randomize tests if requested
        r = None
        if seed is not None:
            r = random.Random(seed)
            r.shuffle(tests)
            self.reporter.write('Running tests shuffled with seed %d' % seed)

        try:
            # this is where the test run starts
            # eventually, the suite should call reporter.startSuite() with
            # the predicted number of tests to be run
            try:
                for test in tests:
                    tr = itrial.ITestRunner(test)
                    self.children.append(tr)
                    tr.parent = self

                    try:
                        tr.runTests(randomize=(seed is not None))
                    except KeyboardInterrupt:
                        # KeyboardInterrupts are normal, not a bug in trial.
                        # Just stop the test run, and do the usual reporting.
                        raise
                    except:
                        # Any other exception is problem.  Report it.
                        f = failure.Failure()
                        annoyingBorder = "-!*@&" * 20
                        trialIsBroken = """
\tWHOOP! WHOOP! DANGER WILL ROBINSON! DANGER! WHOOP! WHOOP!
\tcaught exception in TestSuite! \n\n\t\tTRIAL IS BROKEN!\n\n
\t%s""" % ('\n\t'.join(f.getTraceback().split('\n')),)
                        print "\n%s\n%s\n\n%s\n" % \
                              (annoyingBorder, trialIsBroken, annoyingBorder)
            except KeyboardInterrupt:
                log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")

            for name, exc in self.couldNotImport.iteritems():
                # XXX: AFAICT this is only used by RemoteJellyReporter
                self.reporter.reportImportError(name, exc)

            if self.benchmark:
                pickle.dump(self.benchmarkStats, file("test.stats", 'wb'))
        finally:
            self.endTime = time.time()

        # hand the reporter the TestSuite to give it access to all information
        # from the test run
        self.reporter.endSuite(self)
        try:
            util.wait(self.reporter.tearDownReporter())
        except:
            t, v, tb = sys.exc_info()
            raise RuntimeError, "your reporter is broken %r" % \
                  (''.join(v),), tb
        self._bail()


class MethodInfoBase(Timed):
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
    zi.implements(itrial.IUserMethod, itrial.IMethodInfo)
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
#:        except:
#:            self.errors.append(failure.Failure())

        self.endTime = time.time()
        
        for e in self.errors:
            self.errorHook(e)

        if self.raiseOnErr and self.errors:
            raise UserMethodError

    def errorHook(self, fail):
        pass


class ParentAttributeMixin:
    """a mixin to allow decendents of this class to call up 
    their parents to get a value. the default usage stops at the
    TestSuite (as it is the trunk of all of this), but any class along the
    way may return a different value.
    """
    def getJanitor(self):
        return self.parent.getJanitor()

    def getReporter(self):
        return self.parent.getReporter()

    def isDebuggingRun(self):
        return self.parent.isDebuggingRun()

    def isDryRun(self):
        return self.parent.isDryRun()


class TestRunnerBase(Timed, ParentAttributeMixin):
    zi.implements(itrial.ITestRunner)
    _tcInstance = None
    methodNames = setUpClass = tearDownClass = methodsWithStatus = None
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
        return self.getJanitor().postCaseCleanup()

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
        self.setUpModule = getattr(self.original, 'setUpModule',
                                   _bogusCallable)
        self.tearDownModule = getattr(self.original, 'tearDownModule',
                                      _bogusCallable)
        self.skip = getattr(self.original, 'skip', None)
        self.todo = getattr(self.original, 'todo', None)
        self.timeout = getattr(self.original, 'timeout', None)

        self.setUpClass = _bogusCallable
        self.tearDownClass = _bogusCallable
        self.children = []

    def methodNames(self):
        if self._mnames is None:
            self._mnames = [mn for tc in self._testCases
                            for mn in tc.methodNames]
        return self._mnames
    methodNames = property(methodNames)

    def _testClasses(self):
        if self._tClasses is None:
            self._tClasses = []
            mod = self.original
            if hasattr(mod, '__tests__'):
                warnings.warn(("to allow for compatibility with python2.4's "
                               "doctest module, please use a __unittests__ "
                               "module attribute instead of __tests__"),
                               DeprecationWarning)
                objects = mod.__tests__
            elif hasattr(mod, '__unittests__'):
                objects = mod.__unittests__
            else:
                names = dir(mod)
                objects = [getattr(mod, name) for name in names]

            for obj in objects:
                if isinstance(obj, (components.MetaInterface, zi.Interface)):
                    continue
                try:
                    if ITestCaseFactory.providedBy(obj):
                        self._tClasses.append(obj)
                except AttributeError:
                    # if someone (looking in exarkun's direction)
                    # messes around with __getattr__ in a particularly funky
                    # way, it's possible to mess up zi's providedBy()
                    pass

        return self._tClasses


    def runTests(self, randomize=False):
        reporter = self.getReporter()
        reporter.startModule(self.original)

        # add setUpModule handling
        tests = self._testClasses()
        if randomize:
            random.shuffle(tests)

        for testClass in tests:
            runner = itrial.ITestRunner(testClass)
            self.children.append(runner)

#:        if hasattr(self.module, '__doctests__'):
#:            vers = sys.version_info[0:2]
#:            if vers[0] >= 2 and vers[1] >= 3:
#:                runner = itrial.ITestRunner(getattr(self.module, '__doctests__'))
#:                self.children.append(runner)
#:            else:
#:                warnings.warn(("trial's doctest support only works with "
#:                               "python 2.3 or later, not running doctests"))

        for runner in self.children:
            runner.parent = self.parent
            runner.runTests(randomize)

            for k, v in runner.methodsWithStatus.iteritems():
                self.methodsWithStatus.setdefault(k, []).extend(v)

        # add tearDownModule handling
        reporter.endModule(self.original)



class TestClassAndMethodBase(TestRunnerBase):
    """base class for *Runner classes providing the testCaseInstance, finding
    the appropriate setUpModule, tearDownModule classes, and running the
    appropriate prefixed-methods as tests
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

    def setUpModule(self):
        return getattr(self.module, 'setUpModule', _bogusCallable)
    setUpModule = property(setUpModule)

    def tearDownModule(self):
        return getattr(self.module, 'tearDownModule', _bogusCallable)
    tearDownModule = property(tearDownModule)

    def _apply(self, f):                  # XXX: need to rename this
        for mname in self.methodNames:
            m = getattr(self._testCase, mname)
            tm = itrial.ITestMethod(m, None)
            if tm == None:
                continue

            tm.parent = self
            self.children.append(tm)
            f(tm)

    def runTests(self, randomize=False):
        reporter = self.getReporter()
        janitor = self.getJanitor()

        
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
                        def _setUpSkipTests(tm):
                            tm.skip = self.skip
                        break                   # <--- skip the else: clause
                    elif error.check(KeyboardInterrupt):
                        log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
                        error.raiseException()
                else:
                    reporter.upDownError(setUpClass)
                    def _setUpClassError(tm):
                        tm.errors.extend(setUpClass.errors)
                        reporter.startTest(tm)
                        self.methodsWithStatus.setdefault(tm.status,
                                                          []).append(tm)
                        reporter.endTest(tm)
                    return self._apply(_setUpClassError) # and we're done

            # --- run methods ----------------------------------------------

            if randomize:
                random.shuffle(self.methodNames)

            def _runTestMethod(testMethod):
                log.msg("--> %s.%s.%s <--" % (testMethod.module.__name__,
                                              testMethod.klass.__name__,
                                              testMethod.name))

                # suppression is handled by each testMethod
                
                if not self.isDryRun():
                    testMethod.run(tci)
                self.methodsWithStatus.setdefault(testMethod.status,
                                                  []).append(testMethod)

            self._apply(_runTestMethod)

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
        

    # TODO: for 2.1
    # this needs a custom runTests to handle setUpModule/tearDownModule


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


class TestMethod(MethodInfoBase, ParentAttributeMixin, StatusMixin):
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
            return getattr(self.original, 'timeout')
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


    def run(self, testCaseInstance):
        self.testCaseInstance = tci = testCaseInstance
        self.runs += 1
        self.startTime = time.time()
        self._signalStateMgr.save()
        janitor = self.parent.getJanitor()
        reporter = self.parent.getReporter()

        try:
            # don't run test methods that are marked as .skip
            #
            if self.skip:
                # wheeee!
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
                    if not self.isDebuggingRun():
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

                    if not self.isDebuggingRun():
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

        finally:
            self._signalStateMgr.restore()

    def doCleanup(self):
        """do cleanup after the test run. check log for errors, do reactor
        cleanup
        """
        try:
            self.getJanitor().postMethodCleanup()
        except util.MultiError, e:
            for f in e.failures:
                self._eb(f)
            return e.failures
            


class BenchmarkMethod(TestMethod):
    def __init__(self, original):
        super(BenchmarkMethod, self).__init__(original)
        self.benchmarkStats = {}

    def run(self, testCaseInstance):
        # WHY IS THIS MONKEY PATCH HERE?
        def _recordStat(datum):
            self.benchmarkStats[self.fullName] = datum
        testCaseInstance.recordStat = _recordStat
        self.original(testCaseInstance)
        


