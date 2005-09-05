from twisted.trial import unittest
from twisted.trial.assertions import FailTest
from twisted.internet import utils, reactor, interfaces
import os, re

def getTrialPath():
    fp = os.path.abspath(unittest.__file__)
    trialPath = fp.split(os.path.sep)[:-3] + ['bin', 'trial']
    return os.path.normpath(os.path.join(fp, os.pardir, os.pardir,
                                         os.pardir, 'bin', 'trial'))


def runTrial(*args):
    return utils.getProcessOutput(getTrialPath(), args=args, errortoo=1,
                                  env=os.environ)


if not interfaces.IReactorProcess.providedBy(reactor):
    skip = "These tests require the ability to spawn processes"
    

class TestImportErrors(unittest.TestCase):
    """Actually run trial on the command line and check that the output is
    what we expect.
    """
    ## XXX -- ideally refactor the trial top-level stuff so we don't have to
    ## shell out for this stuff.

    def test_trialFound(self):
        self.failUnless(os.path.isfile(getTrialPath()), getTrialPath())

    def test_trialRun(self):
        d = runTrial('--help')
        d.addCallback(lambda x : self.failUnless('trial' in x))
        return d

    def test_nonexistentModule(self):
        d = runTrial('twisted.doesntexist')
        d.addCallback(lambda x : self.failUnlessIn('IMPORT ERROR', x) and x)
        d.addCallback(lambda x : self.failUnlessIn('twisted.doesntexist', x))
        return d

    ## XXX -- needs tests for
    ## - nonexistent toplevel package
    ## - nonexistent toplevel package with module
    ## - package that doesn't import
    ## - module inside package that doesn't import
    ## - module that doesn't import inside package
    ## - recursive on package that contains module that doesn't import
    ## - package / modules that _do_ import
