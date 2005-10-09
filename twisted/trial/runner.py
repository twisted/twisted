# -*- test-case-name: twisted.trial.test.test_trial -*-

#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Original Author: Jonathan Lange <jml@twistedmatrix.com>

from __future__ import generators


import os, glob, types, warnings, time, sys, inspect, imp
import fnmatch, random, inspect, doctest
from os.path import join as opj

from twisted.internet import defer, interfaces
from twisted.python import components, reflect, log, failure
from twisted.python.util import dsu
from twisted.trial import itrial, util, unittest
from twisted.trial.itrial import ITestCase, IReporter
import zope.interface as zi

pyunit = __import__('unittest')


def isPackage(module):
    """Given an object return True if the object looks like a package"""
    if not isinstance(module, types.ModuleType):
        return False
    basename = os.path.splitext(os.path.basename(module.__file__))[0]
    return basename == '__init__'

    
def isPackageDirectory(dirname):
    """Is the directory at path 'dirname' a Python package directory?
    Returns the name of the __init__ file (it may have a weird extension)
    if dirname is a package directory.  Otherwise, returns False"""
    for ext in zip(*imp.get_suffixes())[0]:
        initFile = '__init__' + ext
        if os.path.exists(os.path.join(dirname, initFile)):
            return initFile
    return False


def filenameToModule(fn):
    if not os.path.exists(fn):
        raise ValueError("%r doesn't exist" % (fn,))
    try:
        return reflect.namedAny(reflect.filenameToModuleName(fn))
    except (ValueError, AttributeError):
        # Couldn't find module.  The file 'fn' is not in PYTHONPATH
        pass
    return _importFromFile(fn)


def _importFromFile(fn, moduleName=None):
    fn = _resolveDirectory(fn)
    if not moduleName:
        moduleName = os.path.splitext(os.path.split(fn)[-1])[0]
    if moduleName in sys.modules:
        return sys.modules[moduleName]
    fd = open(fn, 'r')
    try:
        module = imp.load_source(moduleName, fn, fd)
    finally:
        fd.close()
    return module


def _resolveDirectory(fn):
    if os.path.isdir(fn):
        initFile = isPackageDirectory(fn)
        if initFile:
            fn = os.path.join(fn, initFile)
        else:
            raise ValueError('%r is not a package directory' % (fn,))
    return fn


class TestSuite(pyunit.TestSuite):
    def visit(self, visitor):
        for case in self._tests:
            case.visit(visitor)

    def __call__(self, result):
        return self.run(result)

    def run(self, result):
        # we implement this because Python 2.3 unittest defines this code
        # in __call__, whereas 2.4 defines the code in run.
        for test in self._tests:
            if result.shouldStop:
                break
            test(result)
        return result        


class DocTestSuite(TestSuite):
    def __init__(self, testModule):
        TestSuite.__init__(self)
        suite = doctest.DocTestSuite(testModule)
        for test in suite._tests: #yay encapsulation
            self.addTest(PyUnitTestCase(test))


class PyUnitTestCase(object):
    """This class decorates the pyunit.TestCase class, mainly to work around
    the differences between unittest in Python 2.3 and unittest in Python 2.4
    These differences are:
    - The way doctest unittests describe themselves
    - Where the implementation of TestCase.run is (used to be in __call__)

    It also implements visit, which we like.
    """
    
    def __init__(self, test):
        self._test = test
        test.id = self.id

    def id(self):
        return self._test.shortDescription()

    def __call__(self, results):
        return self._test(results)

    def visit(self, visitor):
        """Call visitor.visitCase(self)."""
        visitor.visitCase(self)

    def __getattr__(self, name):
        return getattr(self._test, name)


class TrialRoot(object):
    """This is the main organizing object. The front-end script creates a
    TrialRoot, handing it a reporter, and then calls run, passing it an
    already-created TestSuite.
    """

    def __init__(self, reporter):
        self.reporter = IReporter(reporter)
        self.startTime, self.endTime = None, None

    def _kickStopRunningStuff(self):
        self.endTime = time.time()
        # hand the reporter the TrialRoot to give it access to all information
        # from the test run
        self.reporter.endTrial(self)
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

    def run(self, suite):
        self._initLogging()
        self.setStartTime()
        # this is where the test run starts
        self.reporter.startTrial(suite.countTestCases())
        suite.run(self.reporter)
        self._kickStopRunningStuff()
        return suite

    def runningTime(self):
        return self.endTime - self.startTime


class ModuleSuite(TestSuite):
    def __init__(self, original):
        TestSuite.__init__(self)
        self.original = original

    def run(self, reporter):
        reporter.startModule(self.original)
        TestSuite.run(self, reporter)
        reporter.endModule(self.original)

    def visit(self, visitor):
        """Call visitor,visitModule(self) and visit all child tests."""
        visitor.visitModule(self)
        TestSuite.visit(self, visitor)
        visitor.visitModuleAfter(self)


class ClassSuite(TestSuite):
    """I run L{twisted.trial.unittest.TestCase} instances and provide
    the correct setUp/tearDownClass methods, method names, and values for
    'magic attributes'. If this TestCase defines an attribute, it is taken
    as the value, if not, we search the parent for the appropriate attribute
    and if we still find nothing, we set our attribute to None
    """
    methodPrefix = 'test'

    def __init__(self, original):
        pyunit.TestSuite.__init__(self)
        self.original = original
        self._testCase = self.original
        self._signalStateMgr = util.SignalStateManager()
        self._janitor = util._Janitor()

    _module = _tcInstance = None
    
    def __call__(self, reporter):
        return self.run(reporter)

    def testCaseInstance(self):
        # a property getter, called by subclasses
        return self.original._testCaseInstance
    testCaseInstance = property(testCaseInstance)

    def _setUpClass(self):
        if not hasattr(self.original, 'setUpClass'):
            return lambda : None
        setUp = self.testCaseInstance.setUpClass
        suppress = util.acquireAttribute(
            util.getPythonContainers(setUp), 'suppress', None)
        return util.UserMethodWrapper(setUp, suppress=suppress)

    def _tearDownClass(self):
        if not hasattr(self.original, 'tearDownClass'):
            return lambda : None
        tearDown = self.testCaseInstance.tearDownClass
        suppress = util.acquireAttribute(
            util.getPythonContainers(tearDown), 'suppress', None)
        return util.UserMethodWrapper(tearDown, suppress=suppress)

    def run(self, reporter):
        janitor = util._Janitor()
        if len(self._tests) == 0:
            return
        self.startTime = time.time()
        try:
            self._signalStateMgr.save()
            reporter.startClass(self._testCase)
            # --- setUpClass -----------------------------------------------
            setUpClass = self._setUpClass()
            try:
                if not getattr(self.original, 'skip', None):
                    setUpClass()
            except util.UserMethodError:
                for error in setUpClass.errors:
                    if error.check(unittest.SkipTest):
                        self.original.skip = error.value[0]
                        break                   # <--- skip the else: clause
                    elif error.check(KeyboardInterrupt):
                        reporter.shouldStop = True
                else:
                    reporter.upDownError(setUpClass)
                    for tm in self._tests:
                        for error in setUpClass.errors:
                            reporter.addError(tm, error)
                        reporter.startTest(tm)
                        reporter.stopTest(tm)
                    return

            # --- run methods ----------------------------------------------
            for testMethod in self._tests:
                testMethod.run(reporter)
                if reporter.shouldStop:
                    break

            # --- tearDownClass ---------------------------------------------
            tearDownClass = self._tearDownClass()
            try:
                if not getattr(self.original, 'skip', None):
                    tearDownClass()
            except util.UserMethodError:
                for error in tearDownClass.errors:
                    if error.check(KeyboardInterrupt):
                        reporter.shouldStop = True
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
        TestSuite.visit(self, visitor)
        visitor.visitClassAfter(self)


def name(thing):
    if hasattr(thing, '__name__'):
        return thing.__name__
    return thing.id()


class TestLoader(object):
    methodPrefix = 'test'
    moduleGlob = 'test_*.py'

    def __init__(self):
        self.suiteFactory = TestSuite
        self.moduleSuiteFactory = ModuleSuite
        self.classSuiteFactory = ClassSuite
        self.sorter = name
        self._importErrors = []

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

    def addImportError(self, name, error):
        self._importErrors.append((name, error))

    def getImportErrors(self):
        return self._importErrors

    def clearImportErrors(self):
        self._importErrors = []

    def findByName(self, name):
        if os.path.exists(name):
            return filenameToModule(name)
        return reflect.namedAny(name)

    def loadModule(self, module):
        if not isinstance(module, types.ModuleType):
            raise TypeError("%r is not a module" % (module,))
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
        if not (isinstance(klass, type) or isinstance(klass, types.ClassType)):
            raise TypeError("%r is not a class" % (klass,))
        if not ITestCase.implementedBy(klass):
            raise ValueError("%r is not a test case" % (klass,))
        factory = self.classSuiteFactory
        names = reflect.prefixedMethodNames(klass, self.methodPrefix)
        tests = dsu([ klass(self.methodPrefix+name) for name in names ],
                    self.sorter)
        suite = factory(klass)
        suite.addTests(tests)
        return suite

    def loadMethod(self, method):
        if not isinstance(method, types.MethodType):
            raise TypeError("%r not a method" % (method,))
        suite = self.classSuiteFactory(method.im_class)
        suite.addTest(method.im_class(method.__name__))
        return suite

    def loadPackage(self, package, recurse=False):
        if not isPackage(package):
            raise TypeError("%r is not a package" % (package,))
        if recurse:
            return self.loadPackageRecursive(package)
        suite = self.suiteFactory()
        for module in dsu(self._findTestModules(package), self.sorter):
            suite.addTest(self.loadModule(module))
        return suite

    def _packageRecurse(self, suite, dirname, names):
        if not isPackageDirectory(dirname):
            names[:] = []
            return
        testModuleNames = fnmatch.filter(names, self.moduleGlob)
        modules = []
        for name in testModuleNames:
            try:
                modules.append(filenameToModule(opj(dirname, name)))
            except:
                # Importing a module can raise any kind of error. Get them all.
                self.addImportError(name, failure.Failure())
                continue
        for module in dsu(modules, self.sorter):
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

    def loadAnything(self, thing, recurse=False):
        if isinstance(thing, types.ModuleType):
            if isPackage(thing):
                return self.loadPackage(thing, recurse)
            return self.loadModule(thing)
        elif isinstance(thing, types.ClassType):
            return self.loadClass(thing)
        elif isinstance(thing, type):
            return self.loadClass(thing)
        elif isinstance(thing, types.MethodType):
            return self.loadMethod(thing)
        raise TypeError("No loader for %r. Unrecognized type" % (thing,))

    def loadByName(self, name, recurse=False):
        thing = self.findByName(name)
        return self.loadAnything(thing, recurse)


class SafeTestLoader(TestLoader):
    """A version of TestLoader that stores all import errors, rather than
    raising them.  When the method is supposed to return a suite and it can't
    return the right one due to error, we return an empty suite.
    """

    def _findTestModules(self, package):
        modGlob = os.path.join(os.path.dirname(package.__file__), self.moduleGlob)
        modules = []
        for filename in glob.glob(modGlob):
            try:
                modules.append(filenameToModule(filename))
            except:
                self.addImportError(filename, failure.Failure())
        return dsu(modules, self.sorter)
        
    def loadDoctests(self, module):
        try:
            return super(SafeTestLoader, self).loadDoctests(module)
        except:
            self.addImportError(str(module), failure.Failure())
            return self.suiteFactory()

    def loadByName(self, name, recurse=False):
        try:
            thing = self.findByName(name)
        except:
            self.addImportError(name, failure.Failure())
            return self.suiteFactory()
        return self.loadAnything(thing, recurse)
