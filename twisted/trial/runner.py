# -*- test-case-name: twisted.trial.test.test_runner -*-

#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Original Author: Jonathan Lange <jml@twistedmatrix.com>

from __future__ import generators
import pdb, shutil
import os, glob, types, warnings, sys, inspect, imp
import fnmatch, random, inspect, doctest, time
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
        from twisted.internet import reactor, utils
        d = defer.Deferred()
        reactor.addSystemEventTrigger('after', 'shutdown', lambda: d.callback(None))
        reactor.fireSystemEvent('shutdown') # radix's suggestion
        treactor = interfaces.IReactorThreads(reactor, None)
        if treactor is not None:
            treactor.suggestThreadPoolSize(0)
        # As long as TestCase does crap stuff with the reactor we need to 
        # manually shutdown the reactor here, and that requires util.wait
        # :(
        # so that the shutdown event completes
        utils.suppressWarnings(lambda: util.wait(d), 
                               (['ignore', 'Do NOT use wait.*'], {}))

    def run(self, result):
        try:
            log.startKeepingErrors()
            TestSuite.run(self, result)
        finally:
            self._bail()


def name(thing):
    if isinstance(thing, str):
        return thing
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


class ErrorHolder(object):
    def __init__(self, description, error):
        self.description = description
        self.error = error

    def id(self):
        return self.description

    def shortDescription(self):
        return self.description

    def __repr__(self):
        return "<ErrorHolder description=%r error=%r>" % (self.description,
                                                          self.error)

    def run(self, result):
        result.addError(self, self.error)

    def __call__(self, result):
        return self.run(result)

    def countTestCases(self):
        return 0


class TestLoader(object):
    methodPrefix = 'test'
    moduleGlob = 'test_*.py'

    def __init__(self):
        self.suiteFactory = TestSuite
        self.sorter = name
        self._importErrors = []

    def sort(self, xs):
        return dsu(xs, self.sorter)

    def _findTestClasses(self, module):
        """Given a module, return all trial Test classes"""
        classes = []
        for name, val in inspect.getmembers(module):
            if isTestCase(val):
                classes.append(val)
        return self.sort(classes)

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
            return suite
        docSuite = self.suiteFactory()
        for doctest in module.__doctests__:
            docSuite.addTest(self.loadDoctests(doctest))
        return self.suiteFactory([suite, docSuite])
    loadTestsFromModule = loadModule

    def loadClass(self, klass):
        if not (isinstance(klass, type) or isinstance(klass, types.ClassType)):
            raise TypeError("%r is not a class" % (klass,))
        if not isTestCase(klass):
            raise ValueError("%r is not a test case" % (klass,))
        names = self.getTestCaseNames(klass)
        tests = self.sort([ klass(self.methodPrefix+name) for name in names ])
        return self.suiteFactory(tests)
    loadTestsFromTestCase = loadClass

    def getTestCaseNames(self, klass):
        return reflect.prefixedMethodNames(klass, self.methodPrefix)

    def loadMethod(self, method):
        if not isinstance(method, types.MethodType):
            raise TypeError("%r not a method" % (method,))
        return method.im_class(method.__name__)

    def _findTestModules(self, package):
        modGlob = os.path.join(os.path.dirname(package.__file__),
                               self.moduleGlob)
        return [ reflect.filenameToModuleName(filename)
                 for filename in glob.glob(modGlob) ]
        
    def loadPackage(self, package, recurse=False):
        if not isPackage(package):
            raise TypeError("%r is not a package" % (package,))
        if recurse:
            return self.loadPackageRecursive(package)
        suite = self.suiteFactory()
        for moduleName in self.sort(self._findTestModules(package)):
            suite.addTest(self.loadByName(moduleName))
        return suite

    def _packageRecurse(self, suite, dirname, names):
        if not isPackageDirectory(dirname):
            names[:] = []
            return
        moduleNames = [reflect.filenameToModuleName(opj(dirname, filename))
                       for filename in fnmatch.filter(names, self.moduleGlob)]
        for moduleName in self.sort(moduleNames):
            suite.addTest(self.loadByName(moduleName))

    def loadPackageRecursive(self, package):
        packageDir = os.path.dirname(package.__file__)
        suite = self.suiteFactory()
        os.path.walk(packageDir, self._packageRecurse, suite)
        return suite

    def loadDoctests(self, module):
        if isinstance(module, str):
            try:
                module = reflect.namedAny(module)
            except:
                return ErrorHolder(module, failure.Failure())
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
        try:
            thing = self.findByName(name)
        except:
            return ErrorHolder(name, failure.Failure())
        return self.loadAnything(thing, recurse)
    loadTestsFromName = loadByName

    def loadTestsFromNames(self, names, module=None):
        suites = []
        for name in names:
            suites.append(self.loadTestsFromName(name, module))
        return self.suiteClass(suite)


class DryRunVisitor(unittest.TestVisitor):

    def __init__(self, reporter):
        self.reporter = reporter
        
    def visitSuite(self, testSuite):
        self.reporter.startSuite(testSuite.name())

    def visitSuiteAfter(self, testSuite):
        self.reporter.endSuite(testSuite.name())

    def visitCase(self, testCase):
        self.reporter.startTest(testCase)
        self.reporter.addSuccess(testCase)
        self.reporter.stopTest(testCase)


class TrialRunner(object):
    """A specialised runner that the trial front end uses."""

    DEBUG = 'debug'
    DRY_RUN = 'dry-run'

    def _getDebugger(self):
        dbg = pdb.Pdb()
        try:
            import readline
        except ImportError:
            print "readline module not available"
            hasattr(sys, 'exc_clear') and sys.exc_clear()
        for path in ('.pdbrc', 'pdbrc'):
            if os.path.exists(path):
                try:
                    rcFile = file(path, 'r')
                except IOError:
                    hasattr(sys, 'exc_clear') and sys.exc_clear()
                else:
                    dbg.rcLines.extend(rcFile.readlines())
        return dbg
    
    def _setUpTestdir(self):
        currentDir = os.getcwd()
        testdir = os.path.normpath(os.path.abspath(self.workingDirectory))
        if os.path.exists(testdir):
           try:
               shutil.rmtree(testdir)
           except OSError, e:
               print ("could not remove %r, caught OSError [Errno %s]: %s"
                      % (testdir, e.errno,e.strerror))
               try:
                   os.rename(testdir,
                             os.path.abspath("_trial_temp_old%s"
                                             % random.randint(0, 99999999)))
               except OSError, e:
                   print ("could not rename path, caught OSError [Errno %s]: %s"
                          % (e.errno,e.strerror))
                   raise
        os.mkdir(testdir)
        os.chdir(testdir)
        return currentDir

    def _makeResult(self):
        return self.reporterFactory(self.stream, self.tbformat, self.rterrors)
        
    def __init__(self, reporterFactory,
                 mode=None,
                 logfile='test.log',
                 stream=sys.stdout,
                 profile=False,
                 tracebackFormat='default',
                 realTimeErrors=False,
                 workingDirectory=None):
        self.reporterFactory = reporterFactory
        self.logfile = logfile
        self.mode = mode
        self.stream = stream
        self.tbformat = tracebackFormat
        self.rterrors = realTimeErrors
        self._result = None
        self.workingDirectory = workingDirectory or '_trial_temp'
        if profile:
            self.run = util.profiled(self.run, 'profile.data')

    def _setUpLogging(self):
        def seeWarnings(x):
           if x.has_key('warning'):
               print
               print x['format'] % x
        log.addObserver(seeWarnings)
        if self.logfile == '-':
           logFileObj = sys.stdout
        else:
           logFileObj = file(self.logfile, 'a')
        log.startLogging(logFileObj, 0)

    def run(self, test):
        """Run the test or suite and return a result object."""
        result = self._makeResult()
        # decorate the suite with reactor cleanup and log starting
        # This should move out of the runner and be presumed to be 
        # present
        suite = TrialSuite([test])
        startTime = time.time()
        result.write("Running %d tests.\n", suite.countTestCases())
        if self.mode == self.DRY_RUN:
            suite.visit(DryRunVisitor(result))
        elif self.mode == self.DEBUG:
            # open question - should this be self.debug() instead.
            debugger = self._getDebugger()
            oldDir = self._setUpTestdir()
            self._setUpLogging()
            debugger.runcall(suite.run, result)
            os.chdir(oldDir)
        else:
            oldDir = self._setUpTestdir()
            self._setUpLogging()
            suite.run(result)
            os.chdir(oldDir)
        endTime = time.time()
        result.printErrors()
        result.writeln(result.separator)
        result.writeln('Ran %d tests in %.3fs', result.testsRun,
                       endTime - startTime)
        result.write('\n')
        result.printSummary()
        return result

    def runUntilFailure(self, test):
        count = 0
        while True:
            count += 1
            self.stream.write("Test Pass %d\n" % (count,))
            result = self.run(test)
            if result.testsRun == 0:
                break
            if not result.wasSuccessful():
                break
        return result
    
