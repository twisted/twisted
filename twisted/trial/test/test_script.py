# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import gc
import StringIO, sys, types

from twisted.trial import unittest
from twisted.trial.runner import (
    TrialRunner, TestSuite, DestructiveTestSuite, TestLoader)
from twisted.trial._dist.disttrial import DistTrialRunner
from twisted.scripts import trial
from twisted.python import util
from twisted.python.compat import set
from twisted.python.usage import UsageError
from twisted.python.filepath import FilePath

from twisted.trial.test.test_loader import testNames

pyunit = __import__('unittest')


def sibpath(filename):
    """
    For finding files in twisted/trial/test
    """
    return util.sibpath(__file__, filename)



class ForceGarbageCollection(unittest.SynchronousTestCase):
    """
    Tests for the --force-gc option.
    """

    def setUp(self):
        self.config = trial.Options()
        self.log = []
        self.patch(gc, 'collect', self.collect)
        test = pyunit.FunctionTestCase(self.simpleTest)
        self.test = TestSuite([test, test])


    def simpleTest(self):
        """
        A simple test method that records that it was run.
        """
        self.log.append('test')


    def collect(self):
        """
        A replacement for gc.collect that logs calls to itself.
        """
        self.log.append('collect')


    def makeRunner(self):
        """
        Return a L{TrialRunner} object that is safe to use in tests.
        """
        runner = trial._makeRunner(self.config)
        runner.stream = StringIO.StringIO()
        return runner


    def test_forceGc(self):
        """
        Passing the --force-gc option to the trial script forces the garbage
        collector to run before and after each test.
        """
        self.config['force-gc'] = True
        self.config.postOptions()
        runner = self.makeRunner()
        runner.run(self.test)
        self.assertEqual(self.log, ['collect', 'test', 'collect',
                                    'collect', 'test', 'collect'])


    def test_unforceGc(self):
        """
        By default, no garbage collection is forced.
        """
        self.config.postOptions()
        runner = self.makeRunner()
        runner.run(self.test)
        self.assertEqual(self.log, ['test', 'test'])



class TestSuiteUsed(unittest.SynchronousTestCase):
    """
    Check the category of tests suite used by the loader.
    """

    def setUp(self):
        """
        Create a trial configuration object.
        """
        self.config = trial.Options()


    def test_defaultSuite(self):
        """
        By default, the loader should use L{DestructiveTestSuite}
        """
        loader = trial._getLoader(self.config)
        self.assertEqual(loader.suiteFactory, DestructiveTestSuite)


    def test_untilFailureSuite(self):
        """
        The C{until-failure} configuration uses the L{TestSuite} to keep
        instances alive across runs.
        """
        self.config['until-failure'] = True
        loader = trial._getLoader(self.config)
        self.assertEqual(loader.suiteFactory, TestSuite)



class TestModuleTest(unittest.SynchronousTestCase):
    def setUp(self):
        self.config = trial.Options()

    def tearDown(self):
        self.config = None

    def test_testNames(self):
        """
        Check that the testNames helper method accurately collects the
        names of tests in suite.
        """
        self.assertEqual(testNames(self), [self.id()])

    def assertSuitesEqual(self, test1, names):
        loader = TestLoader()
        names1 = testNames(test1)
        names2 = testNames(TestSuite(map(loader.loadByName, names)))
        names1.sort()
        names2.sort()
        self.assertEqual(names1, names2)

    def test_baseState(self):
        self.assertEqual(0, len(self.config['tests']))

    def test_testmoduleOnModule(self):
        """
        Check that --testmodule loads a suite which contains the tests
        referred to in test-case-name inside its parameter.
        """
        self.config.opt_testmodule(sibpath('moduletest.py'))
        self.assertSuitesEqual(trial._getSuite(self.config),
                               ['twisted.trial.test.test_test_visitor'])

    def test_testmoduleTwice(self):
        """
        When the same module is specified with two --testmodule flags, it
        should only appear once in the suite.
        """
        self.config.opt_testmodule(sibpath('moduletest.py'))
        self.config.opt_testmodule(sibpath('moduletest.py'))
        self.assertSuitesEqual(trial._getSuite(self.config),
                               ['twisted.trial.test.test_test_visitor'])

    def test_testmoduleOnSourceAndTarget(self):
        """
        If --testmodule is specified twice, once for module A and once for
        a module which refers to module A, then make sure module A is only
        added once.
        """
        self.config.opt_testmodule(sibpath('moduletest.py'))
        self.config.opt_testmodule(sibpath('test_test_visitor.py'))
        self.assertSuitesEqual(trial._getSuite(self.config),
                               ['twisted.trial.test.test_test_visitor'])

    def test_testmoduleOnSelfModule(self):
        """
        When given a module that refers to *itself* in the test-case-name
        variable, check that --testmodule only adds the tests once.
        """
        self.config.opt_testmodule(sibpath('moduleself.py'))
        self.assertSuitesEqual(trial._getSuite(self.config),
                               ['twisted.trial.test.moduleself'])

    def test_testmoduleOnScript(self):
        """
        Check that --testmodule loads tests referred to in test-case-name
        buffer variables.
        """
        self.config.opt_testmodule(sibpath('scripttest.py'))
        self.assertSuitesEqual(trial._getSuite(self.config),
                               ['twisted.trial.test.test_test_visitor',
                                'twisted.trial.test.test_class'])

    def test_testmoduleOnNonexistentFile(self):
        """
        Check that --testmodule displays a meaningful error message when
        passed a non-existent filename.
        """
        buffy = StringIO.StringIO()
        stderr, sys.stderr = sys.stderr, buffy
        filename = 'test_thisbetternoteverexist.py'
        try:
            self.config.opt_testmodule(filename)
            self.assertEqual(0, len(self.config['tests']))
            self.assertEqual("File %r doesn't exist\n" % (filename,),
                                 buffy.getvalue())
        finally:
            sys.stderr = stderr

    def test_testmoduleOnEmptyVars(self):
        """
        Check that --testmodule adds no tests to the suite for modules
        which lack test-case-name buffer variables.
        """
        self.config.opt_testmodule(sibpath('novars.py'))
        self.assertEqual(0, len(self.config['tests']))

    def test_testmoduleOnModuleName(self):
        """
        Check that --testmodule does *not* support module names as arguments
        and that it displays a meaningful error message.
        """
        buffy = StringIO.StringIO()
        stderr, sys.stderr = sys.stderr, buffy
        moduleName = 'twisted.trial.test.test_script'
        try:
            self.config.opt_testmodule(moduleName)
            self.assertEqual(0, len(self.config['tests']))
            self.assertEqual("File %r doesn't exist\n" % (moduleName,),
                                 buffy.getvalue())
        finally:
            sys.stderr = stderr

    def test_parseLocalVariable(self):
        declaration = '-*- test-case-name: twisted.trial.test.test_tests -*-'
        localVars = trial._parseLocalVariables(declaration)
        self.assertEqual({'test-case-name':
                              'twisted.trial.test.test_tests'},
                             localVars)

    def test_trailingSemicolon(self):
        declaration = '-*- test-case-name: twisted.trial.test.test_tests; -*-'
        localVars = trial._parseLocalVariables(declaration)
        self.assertEqual({'test-case-name':
                              'twisted.trial.test.test_tests'},
                             localVars)

    def test_parseLocalVariables(self):
        declaration = ('-*- test-case-name: twisted.trial.test.test_tests; '
                       'foo: bar -*-')
        localVars = trial._parseLocalVariables(declaration)
        self.assertEqual({'test-case-name':
                              'twisted.trial.test.test_tests',
                              'foo': 'bar'},
                             localVars)

    def test_surroundingGuff(self):
        declaration = ('## -*- test-case-name: '
                       'twisted.trial.test.test_tests -*- #')
        localVars = trial._parseLocalVariables(declaration)
        self.assertEqual({'test-case-name':
                              'twisted.trial.test.test_tests'},
                             localVars)

    def test_invalidLine(self):
        self.failUnlessRaises(ValueError, trial._parseLocalVariables,
                              'foo')

    def test_invalidDeclaration(self):
        self.failUnlessRaises(ValueError, trial._parseLocalVariables,
                              '-*- foo -*-')
        self.failUnlessRaises(ValueError, trial._parseLocalVariables,
                              '-*- foo: bar; qux -*-')
        self.failUnlessRaises(ValueError, trial._parseLocalVariables,
                              '-*- foo: bar: baz; qux: qax -*-')

    def test_variablesFromFile(self):
        localVars = trial.loadLocalVariables(sibpath('moduletest.py'))
        self.assertEqual({'test-case-name':
                              'twisted.trial.test.test_test_visitor'},
                             localVars)

    def test_noVariablesInFile(self):
        localVars = trial.loadLocalVariables(sibpath('novars.py'))
        self.assertEqual({}, localVars)

    def test_variablesFromScript(self):
        localVars = trial.loadLocalVariables(sibpath('scripttest.py'))
        self.assertEqual(
            {'test-case-name': ('twisted.trial.test.test_test_visitor,'
                                'twisted.trial.test.test_class')},
            localVars)

    def test_getTestModules(self):
        modules = trial.getTestModules(sibpath('moduletest.py'))
        self.assertEqual(modules, ['twisted.trial.test.test_test_visitor'])

    def test_getTestModules_noVars(self):
        modules = trial.getTestModules(sibpath('novars.py'))
        self.assertEqual(len(modules), 0)

    def test_getTestModules_multiple(self):
        modules = trial.getTestModules(sibpath('scripttest.py'))
        self.assertEqual(set(modules),
                             set(['twisted.trial.test.test_test_visitor',
                                  'twisted.trial.test.test_class']))

    def test_looksLikeTestModule(self):
        for filename in ['test_script.py', 'twisted/trial/test/test_script.py']:
            self.failUnless(trial.isTestFile(filename),
                            "%r should be a test file" % (filename,))
        for filename in ['twisted/trial/test/moduletest.py',
                         sibpath('scripttest.py'), sibpath('test_foo.bat')]:
            self.failIf(trial.isTestFile(filename),
                        "%r should *not* be a test file" % (filename,))


class WithoutModuleTests(unittest.SynchronousTestCase):
    """
    Test the C{without-module} flag.
    """

    def setUp(self):
        """
        Create a L{trial.Options} object to be used in the tests, and save
        C{sys.modules}.
        """
        self.config = trial.Options()
        self.savedModules = dict(sys.modules)


    def tearDown(self):
        """
        Restore C{sys.modules}.
        """
        for module in ('imaplib', 'smtplib'):
            if module in self.savedModules:
                sys.modules[module] = self.savedModules[module]
            else:
                sys.modules.pop(module, None)


    def _checkSMTP(self):
        """
        Try to import the C{smtplib} module, and return it.
        """
        import smtplib
        return smtplib


    def _checkIMAP(self):
        """
        Try to import the C{imaplib} module, and return it.
        """
        import imaplib
        return imaplib


    def test_disableOneModule(self):
        """
        Check that after disabling a module, it can't be imported anymore.
        """
        self.config.parseOptions(["--without-module", "smtplib"])
        self.assertRaises(ImportError, self._checkSMTP)
        # Restore sys.modules
        del sys.modules["smtplib"]
        # Then the function should succeed
        self.assertIsInstance(self._checkSMTP(), types.ModuleType)


    def test_disableMultipleModules(self):
        """
        Check that several modules can be disabled at once.
        """
        self.config.parseOptions(["--without-module", "smtplib,imaplib"])
        self.assertRaises(ImportError, self._checkSMTP)
        self.assertRaises(ImportError, self._checkIMAP)
        # Restore sys.modules
        del sys.modules["smtplib"]
        del sys.modules["imaplib"]
        # Then the functions should succeed
        self.assertIsInstance(self._checkSMTP(), types.ModuleType)
        self.assertIsInstance(self._checkIMAP(), types.ModuleType)


    def test_disableAlreadyImportedModule(self):
        """
        Disabling an already imported module should produce a warning.
        """
        self.assertIsInstance(self._checkSMTP(), types.ModuleType)
        self.assertWarns(RuntimeWarning,
                "Module 'smtplib' already imported, disabling anyway.",
                trial.__file__,
                self.config.parseOptions, ["--without-module", "smtplib"])
        self.assertRaises(ImportError, self._checkSMTP)



class CoverageTests(unittest.SynchronousTestCase):
    """
    Tests for the I{coverage} option.
    """
    if getattr(sys, 'gettrace', None) is None:
        skip = (
            "Cannot test trace hook installation without inspection API.")

    def setUp(self):
        """
        Arrange for the current trace hook to be restored when the
        test is complete.
        """
        self.addCleanup(sys.settrace, sys.gettrace())


    def test_tracerInstalled(self):
        """
        L{trial.Options} handles C{"--coverage"} by installing a trace
        hook to record coverage information.
        """
        options = trial.Options()
        options.parseOptions(["--coverage"])
        self.assertEqual(sys.gettrace(), options.tracer.globaltrace)


    def test_coverdirDefault(self):
        """
        L{trial.Options.coverdir} returns a L{FilePath} based on the default
        for the I{temp-directory} option if that option is not specified.
        """
        options = trial.Options()
        self.assertEqual(
            options.coverdir(),
            FilePath(".").descendant([options["temp-directory"], "coverage"]))


    def test_coverdirOverridden(self):
        """
        If a value is specified for the I{temp-directory} option,
        L{trial.Options.coverdir} returns a child of that path.
        """
        path = self.mktemp()
        options = trial.Options()
        options.parseOptions(["--temp-directory", path])
        self.assertEqual(
            options.coverdir(), FilePath(path).child("coverage"))



class OptionsTestCase(unittest.TestCase):
    """
    Tests for L{trial.Options}.
    """

    def setUp(self):
        """
        Build an L{Options} object to be used in the tests.
        """
        self.options = trial.Options()


    def test_getWorkerArguments(self):
        """
        C{_getWorkerArguments} discards options like C{random} as they only
        matter in the manager, and forwards options like C{recursionlimit} or
        C{disablegc}.
        """
        self.addCleanup(sys.setrecursionlimit, sys.getrecursionlimit())
        if gc.isenabled():
            self.addCleanup(gc.enable)

        self.options.parseOptions(["--recursionlimit", "2000", "--random",
                                   "4", "--disablegc"])
        args = self.options._getWorkerArguments()
        self.assertIn("--disablegc", args)
        args.remove("--disablegc")
        self.assertEqual(["--recursionlimit", "2000"], args)


    def test_jobsConflictWithDebug(self):
        """
        C{parseOptions} raises a C{UsageError} when C{--debug} is passed along
        C{--jobs} as it's not supported yet.

        @see: U{http://twistedmatrix.com/trac/ticket/5825}
        """
        error = self.assertRaises(
            UsageError, self.options.parseOptions, ["--jobs", "4", "--debug"])
        self.assertEqual("You can't specify --debug when using --jobs",
                         str(error))


    def test_jobsConflictWithProfile(self):
        """
        C{parseOptions} raises a C{UsageError} when C{--profile} is passed
        along C{--jobs} as it's not supported yet.

        @see: U{http://twistedmatrix.com/trac/ticket/5827}
        """
        error = self.assertRaises(
            UsageError, self.options.parseOptions,
            ["--jobs", "4", "--profile"])
        self.assertEqual("You can't specify --profile when using --jobs",
                         str(error))


    def test_jobsConflictWithDebugStackTraces(self):
        """
        C{parseOptions} raises a C{UsageError} when C{--debug-stacktraces} is
        passed along C{--jobs} as it's not supported yet.

        @see: U{http://twistedmatrix.com/trac/ticket/5826}
        """
        error = self.assertRaises(
            UsageError, self.options.parseOptions,
            ["--jobs", "4", "--debug-stacktraces"])
        self.assertEqual(
            "You can't specify --debug-stacktraces when using --jobs",
            str(error))



class MakeRunnerTestCase(unittest.TestCase):
    """
    Tests for the L{_makeRunner} helper.
    """

    def test_jobs(self):
        """
        L{_makeRunner} returns a L{DistTrialRunner} instance when the C{--jobs}
        option is passed, and passes the C{workerNumber} and C{workerArguments}
        parameters to it.
        """
        options = trial.Options()
        options.parseOptions(["--jobs", "4", "--force-gc"])
        runner = trial._makeRunner(options)
        self.assertIsInstance(runner, DistTrialRunner)
        self.assertEqual(4, runner._workerNumber)
        self.assertEqual(["--force-gc"], runner._workerArguments)


    def test_dryRunWithJobs(self):
        """
        L{_makeRunner} returns a L{TrialRunner} instance in C{DRY_RUN} mode
        when the C{--dry-run} option is passed, even if C{--jobs} is set.
        """
        options = trial.Options()
        options.parseOptions(["--jobs", "4", "--dry-run"])
        runner = trial._makeRunner(options)
        self.assertIsInstance(runner, TrialRunner)
        self.assertEqual(TrialRunner.DRY_RUN, runner.mode)


    def test_DebuggerNotFound(self):
        namedAny = trial.reflect.namedAny

        def namedAnyExceptdoNotFind(fqn):
            if fqn == "doNotFind":
                raise trial.reflect.ModuleNotFound(fqn)
            return namedAny(fqn)

        self.patch(trial.reflect, "namedAny", namedAnyExceptdoNotFind)

        options = trial.Options()
        options.parseOptions(["--debug", "--debugger", "doNotFind"])

        self.assertRaises(trial._DebuggerNotFound, trial._makeRunner, options)


class TestRun(unittest.TestCase):
    """
    Tests for the L{run} function.
    """

    def setUp(self):
        # don't re-parse cmdline options, because if --reactor was passed to
        # the test run trial will try to restart the (already running) reactor
        self.patch(trial.Options, "parseOptions", lambda self: None)


    def test_debuggerNotFound(self):
        """
        When a debugger is not found, an error message is printed to the user.

        """

        def _makeRunner(*args, **kwargs):
            raise trial._DebuggerNotFound('foo')
        self.patch(trial, "_makeRunner", _makeRunner)

        try:
            trial.run()
        except SystemExit as e:
            self.assertIn("foo", str(e))
        else:
            self.fail("Should have exited due to non-existent debugger!")
