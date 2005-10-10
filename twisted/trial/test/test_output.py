from twisted.trial import unittest
from twisted.trial.test import packages
from twisted.python import util
from twisted.internet import utils, reactor, interfaces
import os, re, sys


def runTrialWithEnv(env, *args):
    params = [ '-c', 'from twisted.scripts.trial import run; run()' ]
    params.extend(args)
    return utils.getProcessOutput(sys.executable, args=params, errortoo=1,
                                  env=env)


if not interfaces.IReactorProcess.providedBy(reactor):
    skip = "These tests require the ability to spawn processes"
    

class TestImportErrors(unittest.TestCase):
    """Actually run trial on the command line and check that the output is
    what we expect.
    """
    ## XXX -- ideally refactor the trial top-level stuff so we don't have to
    ## shell out for this stuff.

    debug = False
    parent = "_testImportErrors"

    def setUp(self):
        packages.setUp(self.parent)

    def tearDown(self):
        packages.tearDown(self.parent)

    def _runTrial(self, env, *args):
        d = runTrialWithEnv(env, *args)
        if self.debug:
            d.addCallback(self._print)
        return d
        
    def runTrial(self, *args):
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join([self.parent] + sys.path)
        return self._runTrial(env, *args)

    def runTrialPure(self, *args):
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        return self._runTrial(env, *args)
 
    def _print(self, stuff):
        print stuff
        return stuff

    def failUnlessIn(self, container, containee, *args, **kwargs):
        # redefined to be useful in callbacks
        self.failUnlessSubstring(containee, container, *args, **kwargs)
        return container

    def failIfIn(self, container, containee, *args, **kwargs):
        # redefined to be useful in callbacks
        self.failIfSubstring(containee, container, *args, **kwargs)
        return container

    def test_trialRun(self):
        d = self.runTrial('--help')
        d.addCallback(self.failUnless, 'trial')
        return d

    def test_nonexistentModule(self):
        d = self.runTrial('twisted.doesntexist')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        d.addCallback(self.failUnlessIn, 'twisted.doesntexist')
        return d

    def test_nonexistentPackage(self):
        d = self.runTrial('doesntexist')
        d.addCallback(self.failUnlessIn, 'doesntexist')
        d.addCallback(self.failUnlessIn, 'ValueError')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        return d

    def test_nonexistentPackageWithModule(self):
        d = self.runTrial('doesntexist.barney')
        d.addCallback(self.failUnlessIn, 'doesntexist.barney')
        d.addCallback(self.failUnlessIn, 'ValueError')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        return d

    def test_badpackage(self):
        d = self.runTrial('badpackage')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        d.addCallback(self.failUnlessIn, 'badpackage')
        d.addCallback(self.failIfIn, 'IOError')
        return d

    def test_moduleInBadpackage(self):
        d = self.runTrial('badpackage.test_module')
        d.addCallback(self.failUnlessIn, "IMPORT ERROR")
        d.addCallback(self.failUnlessIn, "badpackage.test_module")
        d.addCallback(self.failIfIn, 'IOError')
        return d

    def test_badmodule(self):
        d = self.runTrial('package.test_bad_module')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        d.addCallback(self.failUnlessIn, 'package.test_bad_module')
        d.addCallback(self.failIfIn, 'IOError')
        d.addCallback(self.failIfIn, '<module')
        return d

    def test_badimport(self):
        d = self.runTrial('package.test_import_module')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        d.addCallback(self.failUnlessIn, 'package.test_import_module')
        d.addCallback(self.failIfIn, 'IOError')
        d.addCallback(self.failIfIn, '<module')
        return d

    def test_recurseImport(self):
        d = self.runTrial('package')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        d.addCallback(self.failUnlessIn, 'test_bad_module')
        d.addCallback(self.failUnlessIn, 'test_import_module')
        d.addCallback(self.failIfIn, '<module')
        d.addCallback(self.failIfIn, 'IOError')
        return d

    def test_recurseImportErrors(self):
        d = self.runTrial('package2')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        d.addCallback(self.failUnlessIn, 'package2')
        d.addCallback(self.failUnlessIn, 'test_module')
        d.addCallback(self.failUnlessIn, "No module named frotz")
        d.addCallback(self.failIfIn, '<module')
        d.addCallback(self.failIfIn, 'IOError')
        return d

    def test_nonRecurseImportErrors(self):
        d = self.runTrial('-N', 'package2')
        d.addCallback(self.failUnlessIn, 'IMPORT ERROR')
        d.addCallback(self.failUnlessIn, "No module named frotz")
        d.addCallback(self.failIfIn, '<module')
        return d

    def test_regularRun(self):
        d = self.runTrial('package.test_module')
        d.addCallback(self.failIfIn, 'IMPORT ERROR')
        d.addCallback(self.failIfIn, 'IOError')
        d.addCallback(self.failUnlessIn, 'OK')
        d.addCallback(self.failUnlessIn, 'PASSED (successes=1)')
        return d
    
    def test_filename(self):
        d = self.runTrialPure(os.path.join(self.parent,
                                           'package', 'test_module.py'))
        d.addCallback(self.failIfIn, 'IMPORT ERROR')
        d.addCallback(self.failIfIn, 'IOError')
        d.addCallback(self.failUnlessIn, 'OK')
        d.addCallback(self.failUnlessIn, 'PASSED (successes=1)')
        return d

    def test_dosFile(self):
        ## XXX -- not really an output test, more of a script test
        d = self.runTrialPure(os.path.join(self.parent,
                                           'package', 'test_dos_module.py'))
        d.addCallback(self.failIfIn, 'IMPORT ERROR')
        d.addCallback(self.failIfIn, 'IOError')
        d.addCallback(self.failUnlessIn, 'OK')
        d.addCallback(self.failUnlessIn, 'PASSED (successes=1)')
        return d
