# -*- test-case-name: twisted.test.test_trial -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
 

"""
Twisted Test Framework

.todo attributes can either be set on the TestCase or on an individual
test* method, and indicate that the test is expected to fail. New tests
(for which the underlying functionality has not yet been added) should set
this flag while the code is being written. Once the feature is added and
the test starts to pass, the flag should be removed.

Tests of highly-unstable in-development code should consider using .skip
to turn off the tests until the code has reached a point where the success
rate is expected to be monotonically increasing.

"""

from __future__ import nested_scopes

# twisted imports
from twisted.python import reflect, log, failure, components
import twisted.python.util

import runner, util, reporter
from twisted.trial.util import deferredResult, deferredError

# system imports
import sys, os, glob, types, errno
try:
    import gc # not available in jython
    import cPickle as pickle
except ImportError:
    gc = None
    import pickle

class SkipTest(Exception):
    """Raise this (with a reason) to skip the current test. You may also set
    method.skip to a reason string to skip it, or set class.skip to skip the
    entire TestCase."""
    pass

class FailTest(AssertionError):
    """Raised to indicate the current test has failed to pass."""
    pass

# Set this to True if you want to disambiguate between test failures and
# other assertions.  If you are in the habit of using the "assert" statement
# in your tests, you probably want to leave this false.
ASSERTION_IS_ERROR = 0
if not ASSERTION_IS_ERROR:
    FAILING_EXCEPTION = AssertionError
else:
    FAILING_EXCEPTION = FailTest


class TestCase:

    expectedAssertions = None
    _assertions = 0
    
    def setUpClass(self):
        pass

    def tearDownClass(self):
        pass
    
    def setUp(self):
        self._assertions = 0
        self.expectedAssertions = None

    def tearDown(self):
        if self.expectedAssertions is not None:
            self.assertEquals(self._assertions, self.expectedAssertions,
                              "There were not enough assertions: "
                              "%s were run, %s were expected" %
                              (self._assertions, self.expectedAssertions))


    def fail(self, message=None):
        raise FailTest, message

    # make sure to increment self._assertions in any of these assertion methods!
    
    def failIf(self, condition, message=None):
        self._assertions += 1
        if condition:
            raise FailTest, message

    def failUnless(self, condition, message=None):
        self._assertions += 1
        if not condition:
            raise FailTest, message

    def failUnlessRaises(self, exception, f, *args, **kwargs):
        self._assertions += 1
        try:
            if not twisted.python.util.raises(exception, f, *args, **kwargs):
                raise FailTest, '%s not raised' % exception.__name__
        except FailTest, e:
            raise
        except:
            # import traceback; traceback.print_exc()
            raise FailTest, '%s raised instead of %s' % (sys.exc_info()[0],
                                                         exception.__name__)

    def failUnlessEqual(self, first, second, msg=None):
        self._assertions += 1
        if not first == second:
            raise FailTest, (msg or '%r != %r' % (first, second))

    def failUnlessIdentical(self, first, second, msg=None):
        self._assertions += 1
        if first is not second:
            raise FailTest, (msg or '%r is not %r' % (first, second))

    def failIfIdentical(self, first, second, msg=None):
        self._assertions += 1
        if first is second:
            raise FailTest, (msg or '%r is %r' % (first, second))

    def failIfEqual(self, first, second, msg=None):
        self._assertions += 1
        if not first != second:
            raise FailTest, (msg or '%r == %r' % (first, second))
    
    def failUnlessIn(self, containee, container, msg=None):
        self._assertions += 1
        if containee not in container:
            raise FailTest, (msg or "%r not in %r" % (containee, container))

    def failIfIn(self, containee, container, msg=None):
        self._assertions += 1
        if containee in container:
            raise FailTest, (msg or "%r in %r" % (containee, container))

    assertEqual = assertEquals = failUnlessEqual
    assertNotEqual = assertNotEquals = failIfEqual
    assertRaises = failUnlessRaises
    assert_ = failUnless
    failIfEquals = failIfEqual
    assertIdentical = failUnlessIdentical
    assertNotIdentical = failIfIdentical
    assertIn = failUnlessIn
    assertNotIn = failIfIn

    def assertApproximates(self, first, second, tolerance, msg=None):
        self._assertions += 1
        if abs(first - second) > tolerance:
            raise FailTest, (msg or "%s ~== %s" % (first, second))
    
    # mktemp helper to increment a counter
    def _mktGetCounter(self, base):
        if getattr(self, "_mktCounters", None) is None:
            self._mktCounters = {}
        if base not in self._mktCounters:
            self._mktCounters[base] = 2
            return 1
        n = self._mktCounters[base]
        self._mktCounters[base] += 1
        return n

    # Utility method for creating temporary names
    def mktemp(self):
        cls = self.__class__
        base = os.path.join(cls.__module__, cls.__name__, getattr(self, 'caseMethodName', 'class'))
        try:
            os.makedirs(base)
        except OSError, e:
            code = e[0]
            if code == errno.EEXIST:
                pass
            else:
                raise
        pid = os.getpid()
        while 1:
            num = self._mktGetCounter(base)
            name = os.path.join(base, "%s.%s" % (pid, num))
            if not os.path.exists(name):
                break
        return name

    def runReactor(self, timesOrSeconds, seconds=False):
        """
        I'll iterate the reactor for a while.
        
        You probably want to use expectedAssertions with this.
        
        @type timesOrSeconds: int
        @param timesOrSeconds: Either the number of iterations to run,
               or, if `seconds' is True, the number of seconds to run for.

        @type seconds: bool
        @param seconds: If this is True, `timesOrSeconds' will be
               interpreted as seconds, rather than iterations.
        """
        from twisted.internet import reactor

        if seconds:
            reactor.callLater(timesOrSeconds, reactor.crash)
            reactor.run()
            return

        for i in xrange(timesOrSeconds):
            reactor.iterate()
            
class Tester:
    """I contain all the supporting machinery for running a single test method.
    """
    
    def __init__(self, testClass, testCase, method, runner):
        # If the test has the todo flag set, then our failures and errors are
        # expected.
        self.todo = getattr(method, "todo", getattr(testCase, "todo", None))
        self.skip = getattr(method, "skip", getattr(testCase, "skip", None))
        if self.todo:
            self.failure = reporter.EXPECTED_FAILURE
            self.error = reporter.EXPECTED_FAILURE
        else:
            self.failure = reporter.FAILURE
            self.error = reporter.ERROR
        self.failures = []
        self.runs = 0
        self.testClass = testClass
        self.testCase = testCase
        self.method = method
        self.runner = runner

    def _runPhase(self, stage, *args, **kwargs):
        """I run a single phase of the testing process. My job is to give
        meaning to exceptions raised during the phase. I attach the results to
        the instance member failures.
        """
        try:
            stage(*args, **kwargs)
        except FAILING_EXCEPTION:
            self.failures.append((self.failure, sys.exc_info()))
        except KeyboardInterrupt:
            raise
        except SkipTest, r:
            reason = None
            if len(r.args) > 0:
                reason = r.args[0]
            else:
                reason = sys.exc_info()
            self.failures.append((reporter.SKIP, reason))
        except:
            self.failures.append((self.error, sys.exc_info()))

    def _main(self):
        """I actually to the setUp and run the test. I only make sense inside
        _runPhase.
        """
        if self.skip:
            raise SkipTest, self.skip
        self.testCase.setUp()
        self.runner(self.method)

    def setUp_and_test(self): self._runPhase(self._main)
    def tearDown(self): self._runPhase(self.testCase.tearDown)

    def cleanUp(self):
        """I clean up after the test is run. This includes making sure there
        are no pending calls lying around, garbage collecting and flushing
        errors.

        This is all to ensure that any errors caused by this tests are caught
        by this test.
        """
        self._runPhase(util.reactorCleanUp)
        if gc: gc.collect()
        for e in log.flushErrors():
            self.failures.append((self.error, e))

    def run(self): 
        """I run a single test. I go through the process of setUp, test,
        tearDown and clean up for a single test method. I store my results
        in the class and return self.getResult().

        @raise KeyboardInterrupt: If someone hits Ctrl-C
        """
        self.runs += 1
        self.testCase.caseMethodName = self.method.__name__
        self.setUp_and_test()
        self.tearDown()
        self.cleanUp()
        return self.getResult()

    def getResult(self):
        """I return a tuple containing the first result obtained from the test.
        If the test was successful, this is also the only result.
        """
        if self.runs > 0:
            if not self.failures:
                if self.todo: self.failures.append((reporter.UNEXPECTED_SUCCESS, self.todo))
                else: self.failures.append((reporter.SUCCESS,))
            return self.failures[0]
        else:
            raise ValueError, "Test has not been run yet, no results to get"
        



class TestSuite:
    moduleGlob = 'test_*.py'
    sortTests = 1

    def __init__(self, benchmark=0):
        self.benchmark = benchmark
        self.numTests = 0
        self.couldNotImport = {}
        self.tests = []
        if benchmark:
            self.stats = {}
        
    def addMethod(self, method):
        """Add a single method of a test case class to this test suite.
        """
        if self.benchmark:
            testAdapter = runner.PerformanceSingletonRunner(method, self.stats)
        else:
            testAdapter = runner.SingletonRunner(method)
            
        self.tests.append(testAdapter)
        self.numTests += testAdapter.numTests()

    def addTestClass(self, testClass):
        if self.benchmark:
            testAdapter = runner.PerformanceTestClassRunner(testClass, self.stats)
        else:
            testAdapter = runner.TestClassRunner(testClass)
            
        self.tests.append(testAdapter)
        self.numTests += testAdapter.numTests()

    def addModule(self, module):
        if type(module) is types.StringType:
            try:
                module = reflect.namedModule(module)
            except:
                self.couldNotImport[module] = failure.Failure()
                return
        if hasattr(module, '__tests__'):
            objects = module.__tests__
        else:
            names = dir(module)
            objects = [getattr(module, name) for name in names]
        
        for obj in objects:
            if ((issubclass(type(obj), types.ClassType) 
                    or issubclass(type(obj), type(object))) 
                    and util.isTestClass(obj)):
                self.addTestClass(obj)

    def addPackage(self, package):
        if type(package) is types.StringType:
            try:
                package = reflect.namedModule(package)
            except ImportError, e:
                self.couldNotImport[package] = failure.Failure()
                return
        modGlob = os.path.join(os.path.dirname(package.__file__),
                               self.moduleGlob)
        modules = map(reflect.filenameToModuleName, glob.glob(modGlob))
        for module in modules:
            self.addModule(module)

    def _packageRecurse(self, arg, dirname, names):
        import fnmatch
        OPJ = os.path.join
        testModuleNames = fnmatch.filter(names, self.moduleGlob)
        testModules = [ reflect.filenameToModuleName(OPJ(dirname, name))
                        for name in testModuleNames ]
        for module in testModules:
            self.addModule(module)

    def addPackageRecursive(self, package):
        if type(package) is types.StringType:
            try:
                package = reflect.namedModule(package)
            except ImportError, e:
                self.couldNotImport[package] = failure.Failure()
                return
        packageDir = os.path.dirname(package.__file__)
        os.path.walk(packageDir, self._packageRecurse, None)

    def run(self, output, seed = None):
        output.start(self.numTests)
        tests = self.tests
        if self.sortTests:
            tests.sort(lambda x,y: cmp(str(x), str(y)))

        log.startKeepingErrors()
        r = None
        if seed is not None:
            import random
            r = random.Random(seed)
            r.shuffle(tests)
            output.writeln('Running tests shuffled with seed %d' % seed)

        for test in tests:
            test.runTests(output)
        
        for name, exc in self.couldNotImport.items():
            output.reportImportError(name, exc)

        if self.benchmark:
            pickle.dump(self.stats, open("test.stats", 'wb'))

        output.stop()
