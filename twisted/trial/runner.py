# -*- test-case-name: twisted.trial.test.test_trial -*-

#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Original Author: Jonathan Lange <jml@twistedmatrix.com>

from __future__ import generators
import pdb
import os, glob, types, warnings, sys, inspect, imp
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


def samefile(filename1, filename2):
    # hacky implementation of os.path.samefile
    return os.path.abspath(filename1) == os.path.abspath(filename2)

def filenameToModule(fn):
    if not os.path.exists(fn):
        raise ValueError("%r doesn't exist" % (fn,))
    try:
        ret = reflect.namedAny(reflect.filenameToModuleName(fn))
    except (ValueError, AttributeError):
        # Couldn't find module.  The file 'fn' is not in PYTHONPATH
        return _importFromFile(fn)
    # ensure that the loaded module matches the file
    retFile = os.path.splitext(ret.__file__)[0] + '.py'
    # not all platforms (e.g. win32) have os.path.samefile
    same = getattr(os.path, 'samefile', samefile)
    if os.path.isfile(fn) and not same(fn, retFile):
        del sys.modules[ret.__name__]
        ret = _importFromFile(fn)
    return ret


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


def visit_suite(suite, visitor):
    for case in suite._tests:
        visit = getattr(case, 'visit', None)
        if visit is not None:
            case.visit(visitor)
        else:
            if isinstance(case, pyunit.TestCase):
                case = PyUnitTestCase(case)
                case.visit(visitor)
            elif isinstance(case, pyunit.TestSuite):
                visit_suite(case, visitor)
            else:
                # assert kindly
                case.visit(visitor)


class TestSuite(pyunit.TestSuite):
    visit = visit_suite

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


class TrialSuite(TestSuite):

    def _bail(self):
        from twisted.internet import reactor
        d = defer.Deferred()
        reactor.addSystemEventTrigger('after', 'shutdown', lambda: d.callback(None))
        reactor.fireSystemEvent('shutdown') # radix's suggestion
        treactor = interfaces.IReactorThreads(reactor, None)
        if treactor is not None:
            treactor.suggestThreadPoolSize(0)
        util.wait(d) # so that the shutdown event completes

    def run(self, result):
        try:
            result.startTrial(self.countTestCases())
            log.startKeepingErrors()
            TestSuite.run(self, result)
        finally:
            result.endTrial(self)
            self._bail()


class NamedSuite(object):
    def __init__(self, name, suite):
        self._name = name
        self._suite = suite

    def name(self):
        return self._name

    def __call__(self, reporter):
        return self.run(reporter)

    def __getattr__(self, name):
        return getattr(self._suite, name)

    def run(self, reporter):
        reporter.startSuite(self.name())
        self._suite.run(reporter)
        reporter.endSuite(self.name())
        
    def visit(self, visitor):
        visitor.visitSuite(self)
        self._suite.visit(visitor)
        visitor.visitSuiteAfter(self)


class ClassSuite(TestSuite):
    """I run L{twisted.trial.unittest.TestCase} instances and provide
    the correct setUp/tearDownClass methods.
    """
    methodPrefix = 'test'

    def __init__(self, original):
        pyunit.TestSuite.__init__(self)
        self.original = original
        self._signalStateMgr = util.SignalStateManager()
        self._janitor = util._Janitor()

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
        try:
            self._signalStateMgr.save()
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
        

def name(thing):
    if hasattr(thing, '__name__'):
        return thing.__name__
    return thing.id()


def isTestCase(obj):
    try:
        return ITestCase.implementedBy(obj)
    except TypeError:
        return False
    except AttributeError:
        # Working around a bug in zope.interface 3.1.0; this isn't the user's
        # fault, so we won't emit a warning.
        # See http://www.zope.org/Collectors/Zope3-dev/470.
        return False

class TestLoader(object):
    methodPrefix = 'test'
    moduleGlob = 'test_*.py'

    def __init__(self):
        self.suiteFactory = TestSuite
        self.classSuiteFactory = ClassSuite
        self.sorter = name
        self._importErrors = []

    def _findTestClasses(self, module):
        """Given a module, return all trial Test classes"""
        classes = []
        for name, val in inspect.getmembers(module):
            if isTestCase(val):
                classes.append(val)
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
        suite = self.suiteFactory()
        for testClass in self._findTestClasses(module):
            suite.addTest(self.loadClass(testClass))
        if not hasattr(module, '__doctests__'):
            return NamedSuite(module.__name__, suite)
        docSuite = self.suiteFactory()
        if sys.version_info[:2] <= (2, 2):
            warnings.warn("trial's doctest support only works with "
                          "python 2.3 or later, not running doctests")
        else:
            for doctest in module.__doctests__:
                docSuite.addTest(self.loadDoctests(doctest))
        modSuite = self.suiteFactory()
        modSuite.addTests([suite, docSuite])
        return NamedSuite(module.__name__, modSuite)

    def loadClass(self, klass):
        if not (isinstance(klass, type) or isinstance(klass, types.ClassType)):
            raise TypeError("%r is not a class" % (klass,))
        if not isTestCase(klass):
            raise ValueError("%r is not a test case" % (klass,))
        factory = self.classSuiteFactory
        names = reflect.prefixedMethodNames(klass, self.methodPrefix)
        tests = dsu([ klass(self.methodPrefix+name) for name in names ],
                    self.sorter)
        suite = factory(klass)
        suite.addTests(tests)
        return NamedSuite(klass.__name__, suite)

    def loadMethod(self, method):
        if not isinstance(method, types.MethodType):
            raise TypeError("%r not a method" % (method,))
        suite = self.classSuiteFactory(method.im_class)
        suite.addTest(method.im_class(method.__name__))
        return NamedSuite(method.im_class.__name__, suite)

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
        suite = self.suiteFactory()
        for packageDir in package.__path__:
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


class DryRunVisitor(unittest.TestVisitor):

    def __init__(self, reporter):
        self.reporter = reporter
        
    def visitSuite(self, testSuite):
        self.reporter.startSuite(testSuite.name())

    def visitSuiteAfter(self, testSuite):
        self.reporter.endSuite(testSuite.name())

    def visitCase(self, testCase):
        self.reporter.startTest(testCase)
        self.reporter.stopTest(testCase)


class TrialRunner(object):
    """A specialised runner that the trial front end uses."""

    def _getDebugger(self):
        dbg = pdb.Pdb()
        try:
            import readline
        except ImportError:
            print "readline module not available"
            hasattr(sys, 'exc_clear') and sys.exc_clear()
        origdir = self._config['_origdir']
        for path in (os.path.join(origdir, '.pdbrc'),
                     os.path.join(origdir, 'pdbrc')):
            if os.path.exists(path):
                try:
                    rcFile = file(path, 'r')
                except IOError:
                    hasattr(sys, 'exc_clear') and sys.exc_clear()
                else:
                    dbg.rcLines.extend(rcFile.readlines())
        return dbg
    
    def _getResult(self):
        return self._config._reporter
        
    def __init__(self, config):
        self._config = config
        self._root = None

    def run(self, test):
        """Run the test or suite and return a result object."""
        # we do not create our reporter here, which is unlike pyunits
        # textrunner, however, as we have specified the interface 
        # reporter must honour, its fine.
        result = self._getResult()
        # decorate the suite with reactor cleanup and log starting
        # This should move out of the runner and be presumed to be 
        # present
        suite = TrialSuite([test])
        if self._config['dry-run']:
            result.startTrial(suite)
            suite.visit(DryRunVisitor(result))
            result.endTrial(suite)
        elif self._config['debug']:
            # open question - should this be self.debug() instead.
            debugger = self._getDebugger()
            debugger.runcall(suite.run, result)
        else:
            suite.run(result)
        return result
