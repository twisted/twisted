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
import sys, os, glob, types
try:
    import gc # not available in jython
except ImportError:
    gc = None


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
    def setUpClass(self):
        pass

    def tearDownClass(self):
        pass
    
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def fail(self, message=None):
        raise FailTest, message

    def failIf(self, condition, message=None):
        if condition:
            raise FailTest, message

    def failUnless(self, condition, message=None):
        if not condition:
            raise FailTest, message

    def failUnlessRaises(self, exception, f, *args, **kwargs):
        try:
            if not twisted.python.util.raises(exception, f, *args, **kwargs):
                raise FailTest, '%s not raised' % exception.__name__
        except:
            # import traceback; traceback.print_exc()
            raise FailTest, '%s raised instead of %s' % (sys.exc_info()[0],
                                                         exception.__name__)

    def failUnlessEqual(self, first, second, msg=None):
        if not first == second:
            raise FailTest, (msg or '%r != %r' % (first, second))

    def failUnlessIdentical(self, first, second, msg=None):
        if first is not second:
            raise FailTest, (msg or '%r is not %r' % (first, second))

    def failIfEqual(self, first, second, msg=None):
        if not first != second:
            raise FailTest, (msg or '%r == %r' % (first, second))

    assertEqual = assertEquals = failUnlessEqual
    assertNotEqual = assertNotEquals = failIfEqual
    assertRaises = failUnlessRaises
    assert_ = failUnless
    failIfEquals = failIfEqual
    assertIdentical = failUnlessIdentical

    def assertApproximates(self, first, second, tolerance, msg=None):
        if abs(first - second) > tolerance:
            raise FailTest, (msg or "%s ~== %s" % (first, second))


# components.registerAdapter(runner.TestClassRunner, TestCase, runner.ITestRunner)

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
    methodPrefix = 'test'
    moduleGlob = 'test_*.py'

    def __init__(self):
        self.numTests = 0
        self.couldNotImport = {}
        self.tests = []

    def addMethod(self, method):
        """Add a single method of a test case class to this test suite.
        """
        testAdapter = runner.SingletonRunner(method)
        self.tests.append(testAdapter)
        self.numTests += testAdapter.numTests()

    def addTestClass(self, testClass):
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
        names = dir(module)
        for name in names:
            obj = getattr(module, name)
            if type(obj) is types.ClassType and util.isTestClass(obj):
                self.addTestClass(obj)

    def addPackage(self, package):
        if type(package) is types.StringType:
            try:
                package = reflect.namedModule(package)
            except ImportError, e:
                self.couldNotImport[package] = e
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
                self.couldNotImport[package] = e
                return
        packageDir = os.path.dirname(package.__file__)
        os.path.walk(packageDir, self._packageRecurse, None)

    def run(self, output, seed = None):
        output.start(self.numTests)
        tests = self.tests
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

        output.stop()
