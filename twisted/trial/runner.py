# -*- test-case-name: twisted.test.trialtest1.TestSkipTestCase -*-
#
# -$*- test-case-name: buildbot.test.test_trial.TestRemoteReporter.testConnectToSlave -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Original Author: Jonathan Lange <jml@twistedmatrix.com>

#  B{What's going on here?}
#
#  I've been staring at this file for about 3 weeks straight, and it seems like a good place
#  to write down how all this stuff works.
#
#  The program flow goes like this:
#
#  The twisted.scripts.trial module parses command line options, creates a TestSuite and passes
#  it the Janitor and Reporter objects. It then adds the modules, classes, and methods
#  that the user requested that the suite search for test cases. Then the script calls .runTests()
#  on the suite.
#
#  The suite goes through each argument and calls ITestRunner(obj) on each object. There are adapters
#  that are registered for ModuleType, ClassType and MethodType, so each one of these adapters knows
#  how to run their tests, and provides a common interface to the suite.
#
#  The module runner goes through the module and searches for classes that implement
#  itrial.TestCaseFactory, does setUpModule, adapts that module's classes with ITestRunner(),
#  and calls .run() on them in sequence.
#
#  The method runner wraps the method, locates the method's class and modules so that
#  the setUp{Module, Class, } can be run for that test. 
#
#  ------
#
#  A word about reporters...
#
#  All output is to be handled by the reporter class. Warnings, Errors, etc. are all given
#  to the reporter and it decides what the correct thing to do is depending on the options
#  given on the command line. This allows the runner code to concentrate on testing logic.
#  The reporter is also given Test-related objects wherever possible, not strings. It is not
#  the job of the runner to know what string should be output, it is the reporter's job
#  to know how to make sense of the data
#
#  -------
#
#  The test framework considers any user-written code *dangerous*, and it wraps it in a
#  UserMethodWrapper before execution. This allows us to handle the errors in a sane,
#  consistent way. The wrapper will run the user-code, catching errors, and then checking
#  for logged errors, saving it to IUserMethod.errors. 
#
#  (more to follow)
#
from __future__ import generators


import os, glob, types, warnings, time, sys, gc, cPickle as pickle, signal
import os.path as osp, fnmatch, random
from os.path import join as opj

import doctest

from twisted.internet import defer
from twisted.python import components, reflect, log, context, failure, \
     util as tputil
from twisted.trial import itrial, util, unittest, registerAdapter, \
     adaptWithDefault
from twisted.trial.itrial import ITestCaseFactory, IReporter, \
     IPyUnitTCFactory, ITrialDebug
from twisted.trial.reporter import SKIP, EXPECTED_FAILURE, FAILURE, \
     ERROR, UNEXPECTED_SUCCESS, SUCCESS
import zope.interface as zi



# --- Exceptions and Warnings ------------------------ 

class BrokenTestCaseWarning(Warning):
    """emitted as a warning when an exception occurs in one of
    setUp, tearDown, setUpClass, or tearDownClass"""

class CouldNotImportWarning(Warning):
    pass

class TwistedPythonComponentsBugWarning(Warning):
    pass


# --- Some Adapters for 'magic' attributes ------------

class NewSkoolAdapter(object):
    def __init__(self, original):
        self.original = original

class TodoBase(NewSkoolAdapter):
    zi.implements(itrial.ITodo)
    types = msg = None

    def isExpected(self, fail):
        if self.types is None:
            return True
        for t in self.types:
            if fail.check(t):
                return True
        return False

    def __add__(self, other):
        return self.msg + other

class TupleTodo(TodoBase):
    def types(self):
        e = self.original[0]
        if isinstance(e, types.TupleType):
            return e
        elif e is None:
            return e
        else:
            return tuple([e])
    types = property(types)

    def msg(self):
        return self.original[1]
    msg = property(msg)

class StringTodo(TodoBase):
    def __init__(self, original):
        super(StringTodo, self).__init__(original)

        # XXX: How annoying should we *really* be?
        #
        #warnings.warn("the .todo attribute should now be a tuple of (ExpectedExceptionClass, message), "
        #              "see the twisted.trial.unittest docstring for info", stacklevel=2)

        self.types = None
        self.msg = original

class TimeoutBase(NewSkoolAdapter, tputil.FancyStrMixin):
    showAttributes = ('duration', 'excArg', 'excClass') 
    duration = excArg = None
    excClass = defer.TimeoutError
    _defaultTimeout, _defaultExcArg = 4.0, "deferred timed out after %s sec"

    def __init__(self, original):
        super(TimeoutBase, self).__init__(original)
        if original is None:
            self.duration = self._defaultTimeout
            self.excArg = self._defaultExcArg % self.duration

    def __str__(self):
        return tputil.FancyStrMixin.__str__(self)
    __repr__ = __str__


class TupleTimeout(TimeoutBase):
    _excArg = None

    def __init__(self, original):
        super(TupleTimeout, self).__init__(original)
        self._set(*original)

    def _set(self, duration=None, excArg=None, excClass=None):
        for attr, param in [('duration', duration),
                            ('excClass', excClass),
                            ('excArg', excArg)]:
            if param is not None:
                setattr(self, attr, param)

    def _getExcArg(self):
        excArg = self._excArg
        if excArg is None:
            excArg = self._defaultExcArg % self.duration
        return excArg 

    def _setExcArg(self, val):
        self._excArg = val

    excArg = property(_getExcArg, _setExcArg)


class NumericTimeout(TimeoutBase):
    def __init__(self, original):
        self.duration = original 
        super(NumericTimeout, self).__init__(original)

class Timed(object):
    zi.implements(itrial.ITimed)
    startTime = None
    endTime = None

def _dbgPA(msg):
   log.msg(iface=itrial.ITrialDebug, parseargs=msg) 

class TestSuite(Timed):
    """This is the main organizing object. The front-end script creates a TestSuite, and
    tells it what modules were requested on the command line. It also hands it a reporter.
    The TestSuite then takes all of the packages, modules, classes and methods, and adapts
    them to ITestRunner objects, which it then calls the runTests method on.
    """
    zi.implements(itrial.ITestSuite)
    moduleGlob = 'test_*.py'
    sortTests = 1

    def __init__(self, reporter, janitor, benchmark=0, doctests=False):
        self.reporter = IReporter(reporter)
        self._janitor = itrial.IJanitor(janitor)
        util._wait(self.reporter.setUpReporter())
        self.benchmark = benchmark
        self.startTime, self.endTime = None, None
        self.numTests = 0
        self.couldNotImport = {}
        self.tests = []
        self.runners = []
        if benchmark:
            registerAdapter(None, itrial.ITestCaseFactory,
                            itrial.ITestRunner)
            registerAdapter(BenchmarkCaseRunner, itrial.ITestCaseFactory,
                            itrial.ITestRunner)
        self.doctests = doctests

    def addMethod(self, method):
        self.tests.append(method)

    def _getMethods(self):
        for runner in self.runners:
            for meth in runner.testMethods:
                yield meth
    methods = property(_getMethods)
        
    def addTestClass(self, testClass):
        if ITestCaseFactory.providedBy(testClass):
            self.tests.append(testClass)
        else:
            warnings.warn("didn't add %s because it does not implement ITestCaseFactory" % testClass)

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

            if hasattr(module, '__doctest__') and self.doctests:
                self.addDoctest(mod)

    def addPackage(self, package):
        modGlob = os.path.join(os.path.dirname(package.__file__),
                               self.moduleGlob)
        modules = map(reflect.filenameToModuleName, glob.glob(modGlob))
        for module in modules:
            self.addModule(module)

    def _packageRecurse(self, arg, dirname, names):
        testModuleNames = fnmatch.filter(names, self.moduleGlob)
        testModules = [ reflect.filenameToModuleName(opj(dirname, name))
                        for name in testModuleNames ]
        for module in testModules:
            self.addModule(module)

    def addPackageRecursive(self, package):
        packageDir = os.path.dirname(package.__file__)
        os.path.walk(packageDir, self._packageRecurse, None)

    def addDoctest(self, module):
        warnings.warn("doctest support is EXPERIMENTAL")
        if isinstance(module, types.StringType):
            try:
                mod = reflect.namedModule(module)
            except KeyboardInterrupt:
                log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
                raise
            except:
                self.couldNotImport[module] = failure.Failure()
                return
        elif isinstance(module, types.ModuleType):
            mod = module
        else:
            warning.warn("bug slyphon about doctest support being so crappy")
            return 

        self.tests.append(DocTestCase(mod))

    def _getBenchmarkStats(self):
        stat = {}
        for r in self.runners:
            for m in r.testMethods:
                stat.update(getattr(m, 'benchmarkStats', {}))
        return stat
    benchmarkStats = property(_getBenchmarkStats)

    def run(self, seed=None):
        self.startTime = time.time()
        tests = self.tests
        if self.sortTests:
            # XXX twisted.python.util.dsu(tests, str)
            tests.sort(lambda x,y: cmp(str(x), str(y)))

        log.startKeepingErrors()

        # randomize tests if requested
        # this should probably also call some kind of random method on the
        # test runners, to get *them* to run tests in a random order
        r = None
        if seed is not None:
            r = random.Random(seed)
            r.shuffle(tests)
            self.reporter.write('Running tests shuffled with seed %d' % seed)


        # set up SIGCHLD signal handler so that parents of spawned processes will be
        # notified when their child processes end
        from twisted.internet import reactor
        if hasattr(reactor, "_handleSigchld") and hasattr(signal, "SIGCHLD"):
            self.sigchldHandler = signal.signal(signal.SIGCHLD,
                                                reactor._handleSigchld)

        def _bail():
            from twisted.internet import reactor
            reactor.fireSystemEvent('shutdown') # radix's suggestion
            reactor.suggestThreadPoolSize(0)

        try:
            # this is where the test run starts
            # eventually, the suite should call reporter.startSuite() with
            # the predicted number of tests to be run
            for test in tests:
                tr = itrial.ITestRunner(test)
                self.runners.append(tr)

                try:
                    tr.runTests(self.reporter, self._janitor, randomize=(seed is not None))
                except KeyboardInterrupt:
                    log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
                    _bail()
                    raise
                except:
                    f = failure.Failure()
                    annoyingBorder = "-!*@&" * 20
                    trialIsBroken = """
\tWHOOP! WHOOP! DANGER WILL ROBINSON! DANGER! WHOOP! WHOOP!
\tcaught exception in TestSuite! \n\n\t\tTRIAL IS BROKEN!\n\n
\t%s""" % ('\n\t'.join(f.getTraceback().split('\n')),)
                    raise RuntimeError, "\n%s\n%s\n\n%s\n" % (annoyingBorder, trialIsBroken, annoyingBorder)

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
            util._wait(self.reporter.tearDownReporter())
        except:
            t, v, tb = sys.exc_info()
            raise RuntimeError, "your reporter is broken %r" % (''.join(v),), tb
        _bail()


class MethodInfoBase(Timed):
    def __init__(self, original):
        self.original = o = original
        self.name = o.__name__
        self.klass = itrial.IClass(original)
        self.module = itrial.IModule(original)
        self.fullName = "%s.%s.%s" % (self.module, self.klass.__name__, self.name)
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
   def __init__(self, original, janitor):
       super(UserMethodWrapper, self).__init__(original)
       self.janitor = janitor
       self.original = original
       self.errors = []

   def __call__(self, *a, **kw):
       self.startTime = time.time()
       try:
           try:
               r = self.original(*a, **kw)
               if isinstance(r, defer.Deferred):
                   util._wait(r, getattr(self.original, 'timeout', None))
           finally:
               self.endTime = time.time()
       except:
           self.errors.append(failure.Failure())
           try:
               self.janitor.do_logErrCheck()
           except util.LoggedErrors:
               self.errors.append(failure.Failure())
           raise UserMethodError


class TestRunnerBase(Timed):
    zi.implements(itrial.ITestRunner)
    _tcInstance = None
    methodNames = setUpClass = tearDownClass = methodsWithStatus = testMethods = None
    testCaseInstance = lambda x: None
    skip = None
    
    def __init__(self, original):
        self.original = original
        self.methodsWithStatus = {}
        self.testMethods = []
        self.startTime, self.endTime = None, None
        self._signalStateMgr = util.SignalStateManager()

    def doCleanup(self, janitor):
        """do cleanup after the test run. check log for errors, do reactor cleanup, and restore
        signals to the state they were in before the test ran
        """
        return janitor.postCaseCleanup()


def _bogusCallable(ignore=None):
    pass

class TestModuleRunner(TestRunnerBase):
    _tClasses = _mnames = None
    def __init__(self, original):
        super(TestModuleRunner, self).__init__(original)
        self.module = self.original
        self.setUpModule = getattr(self.original, 'setUpModule', _bogusCallable)
        self.tearDownModule = getattr(self.original, 'tearDownModule', _bogusCallable)
        self.moudleName = itrial.IModuleName(self.original)
        self.skip = getattr(self.original, 'skip', None)
        self.todo = getattr(self.original, 'todo', None)
        self.timeout = getattr(self.original, 'timeout', None)

        self.setUpClass = _bogusCallable
        self.tearDownClass = _bogusCallable
        self.runners = []

    def methodNames(self):
        if self._mnames is None:
            self._mnames = [mn for tc in self._testCases for mn in tc.methodNames]
        return self._mnames
    methodNames = property(methodNames)

    def _testClasses(self):
        if self._tClasses is None:
            self._tClasses = []
            mod = self.original
            if hasattr(mod, '__tests__'):
                objects = mod.__tests__
            else:
                names = dir(mod)
                objects = [getattr(mod, name) for name in names]

            for obj in objects:
                if isinstance(obj, (components.MetaInterface, zi.Interface)):
                    continue
                elif ITestCaseFactory.providedBy(obj):
                    self._tClasses.append(obj)
        return self._tClasses

    def runTests(self, reporter, janitor, randomize=False):
        reporter.startModule(self.original)

        # add setUpModule handling
        tests = self._testClasses()
        if randomize:
            random.shuffle(tests)
        for testClass in tests:
            tc = itrial.ITestRunner(testClass)
            self.runners.append(tc)
            tc.runTests(reporter, janitor, randomize)
            for k, v in tc.methodsWithStatus.iteritems():
                self.methodsWithStatus.setdefault(k, []).extend(v)

        # add tearDownModule handling

        reporter.endModule(self.original)



class TestClassAndMethodBase(TestRunnerBase):
    _module = _tcInstance = None
    
    def testCaseInstance(self):
        # a property getter, called by subclasses
        if not self._tcInstance:
            self._tcInstance = self._testCase() 
        return self._tcInstance
    testCaseInstance = property(testCaseInstance)

    def module(self):
        if self._module is None:
            self._module = reflect.namedAny(self.testCases[0].__module__)
        return self._module
    module = property(module)

    def setUpModule(self):
        return getattr(self.module, 'setUpModule', _bogusCallable)
    setUpModule = property(setUpModule)    

    def tearDownModule(self):
        return getattr(self.module, 'tearDownModule', _bogusCallable)
    tearDownModule = property(tearDownModule)    

    def _applyClassAttrs(self, testMethod):
        # if this class has a .skip, .todo, or attribute, that
        # attribute's value is applied to all of the class' methods
        # if the method already has one of these attributes, the method
        # attribute's value takes precedence
        #
        for attr in ('skip', 'todo', 'timeout'):
            v = getattr(self, attr, None)
            if v is not None and getattr(testMethod, attr, None) is None: 
                setattr(testMethod, attr, v)


    def runTests(self, reporter, janitor, randomize=False):
        def _apply(f):
            for mname in self.methodNames:
                m = getattr(self._testCase, mname)
                tm = adaptWithDefault(itrial.ITestMethod, m, default=None)
                if tm == None:
                    continue

                self.testMethods.append(tm)
                f(tm)
                reporter.startTest(tm) 
                self.methodsWithStatus.setdefault(tm.status, []).append(tm)
                reporter.endTest(tm)   
        

        tci = self.testCaseInstance
        self.startTime = time.time()

        try:
            self._signalStateMgr.save()

            reporter.startClass(self._testCase.__name__) # fix! this sucks!

            # --- setUpClass ------------------------------------------------------

            um = UserMethodWrapper(self.setUpClass, janitor)
            try:
                um()
            except UserMethodError:
                for error in um.errors:
                    if error.check(unittest.SkipTest):
                        self.skip = error.value[0]
                        break                              # <--- skip the else: clause
                    elif error.check(KeyboardInterrupt):
                        log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
                        um.error.raiseException()
                else:
                    reporter.upDownError(um)
                    def _setUpClassError(tm):
                        tm.errors.extend(um.errors) 
                    return _apply(_setUpClassError) # and we're done

            # --- run methods -------------------------------------------------------
            methodNames = self.methodNames
            if randomize:
                random.shuffle(methodNames)
            for mname in methodNames:
                m = getattr(self._testCase, mname)

                testMethod = adaptWithDefault(itrial.ITestMethod, m, default=None)
                if testMethod == None:
                    continue

                log.msg("--> %s.%s.%s <--" % (testMethod.module.__name__,
                                              testMethod.klass.__name__,
                                              testMethod.name))
                self.testMethods.append(testMethod)

                self._applyClassAttrs(testMethod)
                
             
                testMethod.run(tci, reporter, janitor)
                self.methodsWithStatus.setdefault(testMethod.status, []).append(testMethod)

            # --- tearDownClass ------------------------------------------------------

            um = UserMethodWrapper(self.tearDownClass, janitor)
            try:
                um()
            except UserMethodError:
                for error in um.errors:
                    if error.check(KeyboardInterrupt):
                        log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
                        error.raiseException()
                else:
                    reporter.upDownError(um)

        finally:
            errs = self.doCleanup(janitor)
            if errs:
                reporter.cleanupErrors(errs)
            self._signalStateMgr.restore()
            reporter.endClass(self._testCase.__name__) # fix! this sucks!
            self.endTime = time.time()
        

class TestCaseRunner(TestClassAndMethodBase):
    """I run L{twisted.trial.unittest.TestCase} instances"""
    methodPrefix = 'test'
    def __init__(self, original):
        super(TestCaseRunner, self).__init__(original)
        self.original = original
        self._testCase = self.original

        self.setUpClass = getattr(self.testCaseInstance, 'setUpClass', _bogusCallable)
        self.tearDownClass = getattr(self.testCaseInstance, 'tearDownClass', _bogusCallable)

        self.methodNames = [name for name in dir(self.testCaseInstance)
                            if name.startswith(self.methodPrefix)]
        self.skip = getattr(self.original, 'skip', None)
        self.todo = getattr(self.original, 'todo', None)
        self.timeout = getattr(self.original, 'timeout', None)


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

        self.skip = getattr(self.original, 'skip', None)
        self.todo = getattr(self.original, 'todo', None)
        self.timeout = getattr(self.original, 'timeout', None)

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
    def runTests(self, reporter, janitor, randomize=False):
        # need to hook up randomize for Benchmark test cases
        registerAdapter(None, types.MethodType, itrial.ITestMethod)
        registerAdapter(BenchmarkMethod, types.MethodType, itrial.ITestMethod)
        try:
            super(BenchmarkCaseRunner, self).runTests(reporter, janitor)
        finally:
            registerAdapter(None, types.MethodType, itrial.ITestMethod)
            registerAdapter(TestMethod, types.MethodType, itrial.ITestMethod)
        

class TestMethod(MethodInfoBase):
    zi.implements(itrial.ITestMethod, itrial.IMethodInfo)
    _status = None

    def __init__(self, original):
        super(TestMethod, self).__init__(original)
        self.todo = getattr(self.original, 'todo', None)

        self.setUp = self.klass.setUp
        self.tearDown = self.klass.tearDown

        self.timeout = getattr(self.original, 'timeout', None)

        self.runs = 0
        self.failures = []
        self.stdout = ''
        self.stderr = ''
        self.logevents = []

        self._skipReason = None  
        self._signalStateMgr = util.SignalStateManager()

    def _checkTodo(self):
        # returns EXPECTED_FAILURE for now if ITodo.types is None for backwards compatiblity
        # but as of twisted 2.1, will return FAILURE or ERROR as appropriate
        #
        # TODO: This is a bit simplistic for right now, it makes sure all errors and/or failures
        #       are of the type(s) specified in ITodo.types, else it returns EXPECTED_FAILURE. This
        #       should probably allow for more complex specifications. Perhaps I will define a 
        #       Todo object that will allow for greater flexibility/complexity.
        # 
        for f in util.iterchain(self.failures, self.errors):
            if not itrial.ITodo(self.todo).isExpected(f):
                return ERROR
        return EXPECTED_FAILURE

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
        
    def _getSkip(self):
        return (getattr(self.original, 'skip', None) or self._skipReason)
    def _setSkip(self, value):
        self._skipReason = value
    skip = property(_getSkip, _setSkip)

    
    def hasTbs(self):
        return self.errors or self.failures
    hasTbs = property(hasTbs)

    def _eb(self, f):
        log.msg(f.printTraceback())
        if f.check(unittest.FAILING_EXCEPTION,
                   unittest.FailTest):
                   #doctest.DocTestTestFailure):
            self.failures.append(f)
        elif f.check(KeyboardInterrupt):
            log.msg(iface=ITrialDebug, kbd="KEYBOARD INTERRUPT")
        elif f.check(unittest.SkipTest):
            if len(f.value.args) > 1:
                reason = f.value.args[0] 
            else:
                warnings.warn(("Do not raise unittest.SkipTest with no arguments! "
                               "Give a reason for skipping tests!"), stacklevel=2)
                reason = str(f)
            self._skipReason = reason
        else:
            self.errors.append(f)


    def run(self, testCaseInstance, reporter, janitor):
        self.testCaseInstance = tci = testCaseInstance
        self.runs += 1
        self.startTime = time.time()
        self._signalStateMgr.save()

        try:
            # don't run test methods that are marked as .skip
            #
            if self.skip:
                # wheeee!
                reporter.startTest(self)
                reporter.endTest(self)
                return

            f = None
            try:
                # capture all a TestMethod run's log events (warner's request)
                observer = util.TrialLogObserver().install()

                um = UserMethodWrapper(self.setUp, janitor)
                try:
                    um(tci)
                except UserMethodError:
                    for error in um.errors:
                        if error.check(KeyboardInterrupt):
                            error.raiseException()
                        self._eb(error)
                    else:
                        reporter.upDownError(um)
                        return
                 
                reporter.startTest(self) 

                try:
                    sys.stdout = util.StdioProxy(sys.stdout)
                    sys.stderr = util.StdioProxy(sys.stderr)

                    um = UserMethodWrapper(self.original, janitor)

                    try:
                        um(tci)
                    except UserMethodError:
                        for error in um.errors:
                            if error.check(KeyboardInterrupt):
                                error.raiseException()
                            self._eb(error)
                finally:
                    self.endTime = time.time()
                    reporter.endTest(self)

                    self.stdout = sys.stdout.getvalue()
                    self.stderr = sys.stderr.getvalue()
                    sys.stdout = sys.stdout.original
                    sys.stderr = sys.stderr.original

                    um = UserMethodWrapper(self.tearDown, janitor)
                    try:
                        um(tci)
                    except UserMethodError:
                        for error in um.errors:
                            if error.check(KeyboardInterrupt):
                                error.raiseException()
                        else:
                            reporter.upDownError(um)
            finally:
                observer.remove()
                self.logevents = observer.events

        finally:
            errs = self.doCleanup(janitor)
            if errs:
                reporter.cleanupErrors(errs)
            self._signalStateMgr.restore()


    def doCleanup(self, janitor):
        """do cleanup after the test run. check log for errors, do reactor cleanup
        """
        errs = janitor.postMethodCleanup()
        for f in errs:
            if f.check(unittest.FailTest):
                self.failures.append(f)
            else:
                self.errors.append(f)
        return errs


class BenchmarkMethod(TestMethod):
    def __init__(self, original):
        super(BenchmarkMethod, self).__init__(original)
        self.benchmarkStats = {}

    def run(self, testCaseInstance, janitor, reporter):
        # WHY IS THIS MONKEY PATCH HERE?
        testCaseInstance.recordStat = lambda datum: self.benchmarkStats.__setitem__(itrial.IFQMethodName(self.original), datum)
        self.original(testCaseInstance)
        

# ----------------------------------------------------------------------------
# **WARNING** Doctest support code **WARNING**
#
# (some nasty shit follows)

def bogus(n=None):
    pass

# XXX: This is a horrid hack to avoid rewriting most of runner.py

class Proxy(object):
    def __init__(self, method):
        self.method = method

    def __call__(self, *a):
        self.method(*a)


class DocTestMethod(TestMethod):
    zi.implements(itrial.ITestMethod)
    def __init__(self, module, name, doc, filename, lineno):
        self._module, self._name, self._doc, self._filename, self._lineno = module, name, doc, filename, lineno

        def _orig(ignore=None):
            tester = Tester(self._module)
            _utest(tester, self._name, self._doc, self._filename, self._lineno)

        proxy = Proxy(_orig)

        proxy.__name__ = self._name
        proxy.im_class = DocTestMethod
        proxy.__module__ = self._module
        proxy.__doc__ = self._doc

        super(DocTestMethod, self).__init__(proxy)

        self.fullname = "doctest %s of file %s at lineno %s" % (name, filename, lineno)
        print self.fullname

    def bogus(*a):
        pass
    setUp = classmethod(bogus)
    tearDown = classmethod(bogus)

    todo = skip = None
    status = property(TestMethod._getStatus)
    hasTbs = property(TestMethod.hasTbs)


class DocTestCase(object):
    zi.classProvides(itrial.ITestCaseFactory)
    def __init__(self, module):
        from doctest import _normalize_module, _find_tests
        self.setUp = self.tearDown = self.setUpClass = self.tearDownClass = bogus
        module = _normalize_module(module)
        tests = _find_tests(module)

        if not tests:
            raise ValueError(module, 'has no tests')

        for name, doc, filename, lineno in tests:
            if not filename:
                filename = module.__file__
                if filename.endswith(".pyc"):
                    filename = filename[:-1]
                elif filename.endswith(".pyo"):
                    filename = filename[:-1]

            tmname = 'test_%s' % (name.replace('.', '_'),)
            dtm = DocTestMethod(module, name, doc, filename, lineno)

            # XXX: YES I AM A TERRIBLE PERSON!
            self.__dict__[tmname] = dtm

    def __call__(self):
        return None
               
# (end nasty shit)
# ----------------------------------------------------------------------------

def runTest(method):
    # utility function, used by test_trial to more closely emulate the usual
    # testing process. This matches the same check in util.extract_tb that
    # matches SingletonRunner.runTest and TestClassRunner.runTest .
    method()




## class PerformanceTestClassRunner(TestClassRunner):
##     methodPrefixes = ('benchmark',)
##     def runTest(self, method):
##         assert method.__name__ in self.methodNames
##         fullName = "%s.%s" % (method.im_class, method.im_func.__name__)
##         method.im_self.recordStat = lambda datum: self.stats.__setitem__(fullName,datum)
##         method()



## class PerformanceSingletonRunner(SingletonRunner):
##     def __init__(self, methodName, stats):
##         SingletonRunner.__init__(self, methodName)
##         self.stats = stats

##     def runTest(self, method):
##         assert method.__name__ == self.methodName
##         fullName = "%s.%s" % (method.im_class, method.im_func.__name__)
##         method.im_self.recordStat = lambda datum: self.stats.__setitem__(fullName, datum)
##         method()


