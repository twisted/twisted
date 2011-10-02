# -*- test-case-name: twisted.trial.test.test_runner -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A miscellany of code used to run Trial tests.

Maintainer: Jonathan Lange
"""

__all__ = [
    'suiteVisit', 'TestSuite',

    'DestructiveTestSuite', 'DocTestCase', 'DryRunVisitor',
    'ErrorHolder', 'LoggedSuite', 'PyUnitTestCase',
    'TestHolder', 'TestLoader', 'TrialRunner', 'TrialSuite',

    'filenameToModule', 'isPackage', 'isPackageDirectory', 'isTestCase',
    'name', 'samefile', 'NOT_IN_TEST',
    ]

import pdb
import os, types, warnings, sys, inspect, imp
import doctest, time

from twisted.python import reflect, log, failure, modules, filepath
from twisted.python.compat import set

from twisted.internet import defer
from twisted.trial import util, unittest
from twisted.trial.itrial import ITestCase
from twisted.trial.reporter import UncleanWarningsReporterWrapper

# These are imported so that they remain in the public API for t.trial.runner
from twisted.trial.unittest import suiteVisit, TestSuite

from zope.interface import implements

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
    """
    A hacky implementation of C{os.path.samefile}. Used by L{filenameToModule}
    when the platform doesn't provide C{os.path.samefile}. Do not use this.
    """
    return os.path.abspath(filename1) == os.path.abspath(filename2)


def filenameToModule(fn):
    """
    Given a filename, do whatever possible to return a module object matching
    that file.

    If the file in question is a module in Python path, properly import and
    return that module. Otherwise, load the source manually.

    @param fn: A filename.
    @return: A module object.
    @raise ValueError: If C{fn} does not exist.
    """
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


def _getMethodNameInClass(method):
    """
    Find the attribute name on the method's class which refers to the method.

    For some methods, notably decorators which have not had __name__ set correctly:

    getattr(method.im_class, method.__name__) != method
    """
    if getattr(method.im_class, method.__name__, object()) != method:
        for alias in dir(method.im_class):
            if getattr(method.im_class, alias, object()) == method:
                return alias
    return method.__name__


class DestructiveTestSuite(TestSuite):
    """
    A test suite which remove the tests once run, to minimize memory usage.
    """

    def run(self, result):
        """
        Almost the same as L{TestSuite.run}, but with C{self._tests} being
        empty at the end.
        """
        while self._tests:
            if result.shouldStop:
                break
            test = self._tests.pop(0)
            test(result)
        return result



# When an error occurs outside of any test, the user will see this string
# in place of a test's name.
NOT_IN_TEST = "<not in test>"



class LoggedSuite(TestSuite):
    """
    Any errors logged in this suite will be reported to the L{TestResult}
    object.
    """

    def run(self, result):
        """
        Run the suite, storing all errors in C{result}. If an error is logged
        while no tests are running, then it will be added as an error to
        C{result}.

        @param result: A L{TestResult} object.
        """
        observer = unittest._logObserver
        observer._add()
        super(LoggedSuite, self).run(result)
        observer._remove()
        for error in observer.getErrors():
            result.addError(TestHolder(NOT_IN_TEST), error)
        observer.flushErrors()



class PyUnitTestCase(object):
    """
    DEPRECATED in Twisted 8.0.

    This class decorates the pyunit.TestCase class, mainly to work around the
    differences between unittest in Python 2.3, 2.4, and 2.5. These
    differences are::

        - The way doctest unittests describe themselves
        - Where the implementation of TestCase.run is (used to be in __call__)
        - Where the test method name is kept (mangled-private or non-mangled
          private variable)

    It also implements visit, which we like.
    """

    def __init__(self, test):
        warnings.warn("Deprecated in Twisted 8.0.",
                      category=DeprecationWarning)
        self._test = test
        test.id = self.id

    def id(self):
        cls = self._test.__class__
        tmn = getattr(self._test, '_TestCase__testMethodName', None)
        if tmn is None:
            # python2.5's 'unittest' module is more sensible; but different.
            tmn = self._test._testMethodName
        return (cls.__module__ + '.' + cls.__name__ + '.' +
                tmn)

    def __repr__(self):
        return 'PyUnitTestCase<%r>'%(self.id(),)

    def __call__(self, results):
        return self._test(results)


    def visit(self, visitor):
        """
        Call the given visitor with the original, standard library, test case
        that C{self} wraps. See L{unittest.TestCase.visit}.

        Deprecated in Twisted 8.0.
        """
        warnings.warn("Test visitors deprecated in Twisted 8.0",
                      category=DeprecationWarning)
        visitor(self._test)


    def __getattr__(self, name):
        return getattr(self._test, name)



class DocTestCase(PyUnitTestCase):
    """
    DEPRECATED in Twisted 8.0.
    """

    def id(self):
        """
        In Python 2.4, doctests have correct id() behaviour. In Python 2.3,
        id() returns 'runit'.

        Here we override id() so that at least it will always contain the
        fully qualified Python name of the doctest.
        """
        return self._test.shortDescription()


class TrialSuite(TestSuite):
    """
    Suite to wrap around every single test in a C{trial} run. Used internally
    by Trial to set up things necessary for Trial tests to work, regardless of
    what context they are run in.
    """

    def __init__(self, tests=()):
        suite = LoggedSuite(tests)
        super(TrialSuite, self).__init__([suite])


    def _bail(self):
        from twisted.internet import reactor
        d = defer.Deferred()
        reactor.addSystemEventTrigger('after', 'shutdown',
                                      lambda: d.callback(None))
        reactor.fireSystemEvent('shutdown') # radix's suggestion
        # As long as TestCase does crap stuff with the reactor we need to
        # manually shutdown the reactor here, and that requires util.wait
        # :(
        # so that the shutdown event completes
        unittest.TestCase('mktemp')._wait(d)

    def run(self, result):
        try:
            TestSuite.run(self, result)
        finally:
            self._bail()


def name(thing):
    """
    @param thing: an object from modules (instance of PythonModule,
        PythonAttribute), a TestCase subclass, or an instance of a TestCase.
    """
    if isTestCase(thing):
        # TestCase subclass
        theName = reflect.qual(thing)
    else:
        # thing from trial, or thing from modules.
        # this monstrosity exists so that modules' objects do not have to
        # implement id(). -jml
        try:
            theName = thing.id()
        except AttributeError:
            theName = thing.name
    return theName


def isTestCase(obj):
    """
    @return: C{True} if C{obj} is a class that contains test cases, C{False}
        otherwise. Used to find all the tests in a module.
    """
    try:
        return issubclass(obj, pyunit.TestCase)
    except TypeError:
        return False



class TestHolder(object):
    """
    Placeholder for a L{TestCase} inside a reporter. As far as a L{TestResult}
    is concerned, this looks exactly like a unit test.
    """

    implements(ITestCase)

    failureException = None

    def __init__(self, description):
        """
        @param description: A string to be displayed L{TestResult}.
        """
        self.description = description


    def __call__(self, result):
        return self.run(result)


    def id(self):
        return self.description


    def countTestCases(self):
        return 0


    def run(self, result):
        """
        This test is just a placeholder. Run the test successfully.

        @param result: The C{TestResult} to store the results in.
        @type result: L{twisted.trial.itrial.ITestResult}.
        """
        result.startTest(self)
        result.addSuccess(self)
        result.stopTest(self)


    def shortDescription(self):
        return self.description



class ErrorHolder(TestHolder):
    """
    Used to insert arbitrary errors into a test suite run. Provides enough
    methods to look like a C{TestCase}, however, when it is run, it simply adds
    an error to the C{TestResult}. The most common use-case is for when a
    module fails to import.
    """

    def __init__(self, description, error):
        """
        @param description: A string used by C{TestResult}s to identify this
        error. Generally, this is the name of a module that failed to import.

        @param error: The error to be added to the result. Can be an `exc_info`
        tuple or a L{twisted.python.failure.Failure}.
        """
        super(ErrorHolder, self).__init__(description)
        self.error = util.excInfoOrFailureToExcInfo(error)


    def __repr__(self):
        return "<ErrorHolder description=%r error=%s%s>" % (
            # Format the exception type and arguments explicitly, as exception
            # objects do not have nice looking string formats on Python 2.4.
            self.description, self.error[0].__name__, self.error[1].args)


    def run(self, result):
        """
        Run the test, reporting the error.

        @param result: The C{TestResult} to store the results in.
        @type result: L{twisted.trial.itrial.ITestResult}.
        """
        result.startTest(self)
        result.addError(self, self.error)
        result.stopTest(self)


    def visit(self, visitor):
        """
        See L{unittest.TestCase.visit}.
        """
        visitor(self)



class TestLoader(object):
    """
    I find tests inside function, modules, files -- whatever -- then return
    them wrapped inside a Test (either a L{TestSuite} or a L{TestCase}).

    @ivar methodPrefix: A string prefix. C{TestLoader} will assume that all the
    methods in a class that begin with C{methodPrefix} are test cases.

    @ivar modulePrefix: A string prefix. Every module in a package that begins
    with C{modulePrefix} is considered a module full of tests.

    @ivar forceGarbageCollection: A flag applied to each C{TestCase} loaded.
    See L{unittest.TestCase} for more information.

    @ivar sorter: A key function used to sort C{TestCase}s, test classes,
    modules and packages.

    @ivar suiteFactory: A callable which is passed a list of tests (which
    themselves may be suites of tests). Must return a test suite.
    """

    methodPrefix = 'test'
    modulePrefix = 'test_'

    def __init__(self):
        self.suiteFactory = TestSuite
        self.sorter = name
        self._importErrors = []

    def sort(self, xs):
        """
        Sort the given things using L{sorter}.

        @param xs: A list of test cases, class or modules.
        """
        return sorted(xs, key=self.sorter)

    def findTestClasses(self, module):
        """Given a module, return all Trial test classes"""
        classes = []
        for name, val in inspect.getmembers(module):
            if isTestCase(val):
                classes.append(val)
        return self.sort(classes)

    def findByName(self, name):
        """
        Return a Python object given a string describing it.

        @param name: a string which may be either a filename or a
        fully-qualified Python name.

        @return: If C{name} is a filename, return the module. If C{name} is a
        fully-qualified Python name, return the object it refers to.
        """
        if os.path.exists(name):
            return filenameToModule(name)
        return reflect.namedAny(name)

    def loadModule(self, module):
        """
        Return a test suite with all the tests from a module.

        Included are TestCase subclasses and doctests listed in the module's
        __doctests__ module. If that's not good for you, put a function named
        either C{testSuite} or C{test_suite} in your module that returns a
        TestSuite, and I'll use the results of that instead.

        If C{testSuite} and C{test_suite} are both present, then I'll use
        C{testSuite}.
        """
        ## XXX - should I add an optional parameter to disable the check for
        ## a custom suite.
        ## OR, should I add another method
        if not isinstance(module, types.ModuleType):
            raise TypeError("%r is not a module" % (module,))
        if hasattr(module, 'testSuite'):
            return module.testSuite()
        elif hasattr(module, 'test_suite'):
            return module.test_suite()
        suite = self.suiteFactory()
        for testClass in self.findTestClasses(module):
            suite.addTest(self.loadClass(testClass))
        if not hasattr(module, '__doctests__'):
            return suite
        docSuite = self.suiteFactory()
        for doctest in module.__doctests__:
            docSuite.addTest(self.loadDoctests(doctest))
        return self.suiteFactory([suite, docSuite])
    loadTestsFromModule = loadModule

    def loadClass(self, klass):
        """
        Given a class which contains test cases, return a sorted list of
        C{TestCase} instances.
        """
        if not (isinstance(klass, type) or isinstance(klass, types.ClassType)):
            raise TypeError("%r is not a class" % (klass,))
        if not isTestCase(klass):
            raise ValueError("%r is not a test case" % (klass,))
        names = self.getTestCaseNames(klass)
        tests = self.sort([self._makeCase(klass, self.methodPrefix+name)
                           for name in names])
        return self.suiteFactory(tests)
    loadTestsFromTestCase = loadClass

    def getTestCaseNames(self, klass):
        """
        Given a class that contains C{TestCase}s, return a list of names of
        methods that probably contain tests.
        """
        return reflect.prefixedMethodNames(klass, self.methodPrefix)

    def loadMethod(self, method):
        """
        Given a method of a C{TestCase} that represents a test, return a
        C{TestCase} instance for that test.
        """
        if not isinstance(method, types.MethodType):
            raise TypeError("%r not a method" % (method,))
        return self._makeCase(method.im_class, _getMethodNameInClass(method))

    def _makeCase(self, klass, methodName):
        return klass(methodName)

    def loadPackage(self, package, recurse=False):
        """
        Load tests from a module object representing a package, and return a
        TestSuite containing those tests.

        Tests are only loaded from modules whose name begins with 'test_'
        (or whatever C{modulePrefix} is set to).

        @param package: a types.ModuleType object (or reasonable facsimilie
        obtained by importing) which may contain tests.

        @param recurse: A boolean.  If True, inspect modules within packages
        within the given package (and so on), otherwise, only inspect modules
        in the package itself.

        @raise: TypeError if 'package' is not a package.

        @return: a TestSuite created with my suiteFactory, containing all the
        tests.
        """
        if not isPackage(package):
            raise TypeError("%r is not a package" % (package,))
        pkgobj = modules.getModule(package.__name__)
        if recurse:
            discovery = pkgobj.walkModules()
        else:
            discovery = pkgobj.iterModules()
        discovered = []
        for disco in discovery:
            if disco.name.split(".")[-1].startswith(self.modulePrefix):
                discovered.append(disco)
        suite = self.suiteFactory()
        for modinfo in self.sort(discovered):
            try:
                module = modinfo.load()
            except:
                thingToAdd = ErrorHolder(modinfo.name, failure.Failure())
            else:
                thingToAdd = self.loadModule(module)
            suite.addTest(thingToAdd)
        return suite

    def loadDoctests(self, module):
        """
        Return a suite of tests for all the doctests defined in C{module}.

        @param module: A module object or a module name.
        """
        if isinstance(module, str):
            try:
                module = reflect.namedAny(module)
            except:
                return ErrorHolder(module, failure.Failure())
        if not inspect.ismodule(module):
            warnings.warn("trial only supports doctesting modules")
            return
        extraArgs = {}
        if sys.version_info > (2, 4):
            # Work around Python issue2604: DocTestCase.tearDown clobbers globs
            def saveGlobals(test):
                """
                Save C{test.globs} and replace it with a copy so that if
                necessary, the original will be available for the next test
                run.
                """
                test._savedGlobals = getattr(test, '_savedGlobals', test.globs)
                test.globs = test._savedGlobals.copy()
            extraArgs['setUp'] = saveGlobals
        return doctest.DocTestSuite(module, **extraArgs)

    def loadAnything(self, thing, recurse=False):
        """
        Given a Python object, return whatever tests that are in it. Whatever
        'in' might mean.

        @param thing: A Python object. A module, method, class or package.
        @param recurse: Whether or not to look in subpackages of packages.
        Defaults to False.

        @return: A C{TestCase} or C{TestSuite}.
        """
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
        """
        Given a string representing a Python object, return whatever tests
        are in that object.

        If C{name} is somehow inaccessible (e.g. the module can't be imported,
        there is no Python object with that name etc) then return an
        L{ErrorHolder}.

        @param name: The fully-qualified name of a Python object.
        """
        try:
            thing = self.findByName(name)
        except:
            return ErrorHolder(name, failure.Failure())
        return self.loadAnything(thing, recurse)
    loadTestsFromName = loadByName

    def loadByNames(self, names, recurse=False):
        """
        Construct a TestSuite containing all the tests found in 'names', where
        names is a list of fully qualified python names and/or filenames. The
        suite returned will have no duplicate tests, even if the same object
        is named twice.
        """
        things = []
        errors = []
        for name in names:
            try:
                things.append(self.findByName(name))
            except:
                errors.append(ErrorHolder(name, failure.Failure()))
        suites = [self.loadAnything(thing, recurse)
                  for thing in self._uniqueTests(things)]
        suites.extend(errors)
        return self.suiteFactory(suites)


    def _uniqueTests(self, things):
        """
        Gather unique suite objects from loaded things. This will guarantee
        uniqueness of inherited methods on TestCases which would otherwise hash
        to same value and collapse to one test unexpectedly if using simpler
        means: e.g. set().
        """
        entries = []
        for thing in things:
            if isinstance(thing, types.MethodType):
                entries.append((thing, thing.im_class))
            else:
                entries.append((thing,))
        return [entry[0] for entry in set(entries)]



class DryRunVisitor(object):
    """
    A visitor that makes a reporter think that every test visited has run
    successfully.
    """

    def __init__(self, reporter):
        """
        @param reporter: A C{TestResult} object.
        """
        self.reporter = reporter


    def markSuccessful(self, testCase):
        """
        Convince the reporter that this test has been run successfully.
        """
        self.reporter.startTest(testCase)
        self.reporter.addSuccess(testCase)
        self.reporter.stopTest(testCase)



class TrialRunner(object):
    """
    A specialised runner that the trial front end uses.
    """

    DEBUG = 'debug'
    DRY_RUN = 'dry-run'

    def _getDebugger(self):
        dbg = pdb.Pdb()
        try:
            import readline
        except ImportError:
            print "readline module not available"
            sys.exc_clear()
        for path in ('.pdbrc', 'pdbrc'):
            if os.path.exists(path):
                try:
                    rcFile = file(path, 'r')
                except IOError:
                    sys.exc_clear()
                else:
                    dbg.rcLines.extend(rcFile.readlines())
        return dbg


    def _setUpTestdir(self):
        self._tearDownLogFile()
        currentDir = os.getcwd()
        base = filepath.FilePath(self.workingDirectory)
        testdir, self._testDirLock = util._unusedTestDirectory(base)
        os.chdir(testdir.path)
        return currentDir


    def _tearDownTestdir(self, oldDir):
        os.chdir(oldDir)
        self._testDirLock.unlock()


    _log = log
    def _makeResult(self):
        reporter = self.reporterFactory(self.stream, self.tbformat,
                                        self.rterrors, self._log)
        if self.uncleanWarnings:
            reporter = UncleanWarningsReporterWrapper(reporter)
        return reporter

    def __init__(self, reporterFactory,
                 mode=None,
                 logfile='test.log',
                 stream=sys.stdout,
                 profile=False,
                 tracebackFormat='default',
                 realTimeErrors=False,
                 uncleanWarnings=False,
                 workingDirectory=None,
                 forceGarbageCollection=False):
        self.reporterFactory = reporterFactory
        self.logfile = logfile
        self.mode = mode
        self.stream = stream
        self.tbformat = tracebackFormat
        self.rterrors = realTimeErrors
        self.uncleanWarnings = uncleanWarnings
        self._result = None
        self.workingDirectory = workingDirectory or '_trial_temp'
        self._logFileObserver = None
        self._logFileObject = None
        self._forceGarbageCollection = forceGarbageCollection
        if profile:
            self.run = util.profiled(self.run, 'profile.data')

    def _tearDownLogFile(self):
        if self._logFileObserver is not None:
            log.removeObserver(self._logFileObserver.emit)
            self._logFileObserver = None
        if self._logFileObject is not None:
            self._logFileObject.close()
            self._logFileObject = None

    def _setUpLogFile(self):
        self._tearDownLogFile()
        if self.logfile == '-':
            logFile = sys.stdout
        else:
            logFile = file(self.logfile, 'a')
        self._logFileObject = logFile
        self._logFileObserver = log.FileLogObserver(logFile)
        log.startLoggingWithObserver(self._logFileObserver.emit, 0)


    def run(self, test):
        """
        Run the test or suite and return a result object.
        """
        test = unittest.decorate(test, ITestCase)
        if self._forceGarbageCollection:
            test = unittest.decorate(
                test, unittest._ForceGarbageCollectionDecorator)
        return self._runWithoutDecoration(test)


    def _runWithoutDecoration(self, test):
        """
        Private helper that runs the given test but doesn't decorate it.
        """
        result = self._makeResult()
        # decorate the suite with reactor cleanup and log starting
        # This should move out of the runner and be presumed to be
        # present
        suite = TrialSuite([test])
        startTime = time.time()
        if self.mode == self.DRY_RUN:
            for single in unittest._iterateTests(suite):
                result.startTest(single)
                result.addSuccess(single)
                result.stopTest(single)
        else:
            if self.mode == self.DEBUG:
                # open question - should this be self.debug() instead.
                debugger = self._getDebugger()
                run = lambda: debugger.runcall(suite.run, result)
            else:
                run = lambda: suite.run(result)

            oldDir = self._setUpTestdir()
            try:
                self._setUpLogFile()
                run()
            finally:
                self._tearDownLogFile()
                self._tearDownTestdir(oldDir)

        endTime = time.time()
        done = getattr(result, 'done', None)
        if done is None:
            warnings.warn(
                "%s should implement done() but doesn't. Falling back to "
                "printErrors() and friends." % reflect.qual(result.__class__),
                category=DeprecationWarning, stacklevel=3)
            result.printErrors()
            result.writeln(result.separator)
            result.writeln('Ran %d tests in %.3fs', result.testsRun,
                           endTime - startTime)
            result.write('\n')
            result.printSummary()
        else:
            result.done()
        return result


    def runUntilFailure(self, test):
        """
        Repeatedly run C{test} until it fails.
        """
        count = 0
        while True:
            count += 1
            self.stream.write("Test Pass %d\n" % (count,))
            if count == 1:
                result = self.run(test)
            else:
                result = self._runWithoutDecoration(test)
            if result.testsRun == 0:
                break
            if not result.wasSuccessful():
                break
        return result
