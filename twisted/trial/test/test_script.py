import inspect
from twisted.trial import unittest
from twisted.scripts import trial
from twisted.python import util, usage


def sibpath(filename):
    """For finding files in twisted/trial/test"""
    return util.sibpath(__file__, filename)


class TestModuleTest(unittest.TestCase):
    def setUp(self):
        self.config = trial.Options()

    def tearDown(self):
        self.config = None

    def test_baseState(self):
        self.failUnlessEqual(0, len(self.config['modules']))

    def test_testmoduleOnModule(self):
        self.config.opt_testmodule(sibpath('moduletest.py'))
        self.failUnless(inspect.ismodule(self.config['modules'][0]))
        self.failUnlessEqual('twisted.trial.test.test_test_visitor',
                             self.config['modules'][0].__name__)

    def test_testmoduleOnScript(self):
        self.config.opt_testmodule(sibpath('scripttest.py'))
        self.failUnless(inspect.ismodule(self.config['modules'][0]))
        self.failUnlessEqual('twisted.trial.test.test_test_visitor',
                             self.config['modules'][0].__name__)

    def test_testmoduleOnNonexistentFile(self):
        self.failUnlessRaises(usage.UsageError,
                              self.config.opt_testmodule,
                              'test_thisbetternoteverexist.py')

    def test_testmoduleOnEmptyVars(self):
        self.config.opt_testmodule(sibpath('novars.py'))
        self.failUnlessEqual([], self.config['modules'])

    def test_testmoduleOnModuleName(self):
        self.failUnlessRaises(usage.UsageError,
                              self.config.opt_testmodule,
                              'twisted.trial.test.test_script')

    def test_actuallyRuns(self):
        from twisted.internet import interfaces, reactor
        if not interfaces.IReactorProcess.providedBy(reactor):
            raise SkipTest("This test runs an external process. "
                           "This reactor doesn't support it.")
        import test_output, os
        d = test_output.runTrialWithEnv(os.environ, '--testmodule',
                                        sibpath('moduletest.py'))
        d.addCallback(lambda x : self.assertSubstring(
            'twisted.trial.test.test_test_visitor', x))
        return d
                             
    def test_parseLocalVariable(self):
        declaration = '-*- test-case-name: twisted.trial.test.test_trial -*-'
        localVars = trial._parseLocalVariables(declaration)
        self.failUnlessEqual({'test-case-name': 'twisted.trial.test.test_trial'},
                             localVars)

    def test_trailingSemicolon(self):
        declaration = '-*- test-case-name: twisted.trial.test.test_trial; -*-'
        localVars = trial._parseLocalVariables(declaration)
        self.failUnlessEqual({'test-case-name': 'twisted.trial.test.test_trial'},
                             localVars)
        
    def test_parseLocalVariables(self):
        declaration = '-*- test-case-name: twisted.trial.test.test_trial; ' \
                      'foo: bar -*-'
        localVars = trial._parseLocalVariables(declaration)
        self.failUnlessEqual({'test-case-name': 'twisted.trial.test.test_trial',
                              'foo': 'bar'},
                             localVars)

    def test_surroundingGuff(self):
        declaration = '## -*- test-case-name: twisted.trial.test.test_trial -*- #'
        localVars = trial._parseLocalVariables(declaration)
        self.failUnlessEqual({'test-case-name': 'twisted.trial.test.test_trial'},
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
        self.failUnlessEqual({'test-case-name': 'twisted.trial.test.test_test_visitor'},
                             localVars)
        
    def test_noVariablesInFile(self):
        localVars = trial.loadLocalVariables(sibpath('novars.py'))
        self.failUnlessEqual({}, localVars)

    def test_variablesFromScript(self):
        localVars = trial.loadLocalVariables(sibpath('scripttest.py'))
        self.failUnlessEqual({'test-case-name': 'twisted.trial.test.test_test_visitor'},
                             localVars)

    def test_looksLikeTestModule(self):
        for filename in ['test_script.py', 'twisted/trial/test/test_script.py']:
            self.failUnless(trial.isTestFile(filename),
                            "%r should be a test file" % (filename,))
        for filename in ['twisted/trial/test/moduletest.py',
                         sibpath('scripttest.py'), sibpath('test_foo.bat')]:
            self.failIf(trial.isTestFile(filename),
                        "%r should *not* be a test file" % (filename,))
