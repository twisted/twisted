import os, sys

from twisted.trial import unittest, util
from twisted.python import util as pythonutil
from twisted.internet import protocol, defer, reactor, error

script = pythonutil.sibpath(__file__, 'wprocess_for_testing')

class TestProcessPro(protocol.ProcessProtocol):
    def __init__(self, deferred):
        self.deferred = deferred
        self.result = {'err': '', 'out': '', 'reason': None}
    def outReceived(self, data):
        out = self.result['out']
        self.result['out'] = out + data
    def errReceived(self, data):
        err = self.result['err']
        self.result['err'] = err + data
    def processEnded(self, reason):
        self.result['reason'] = reason
        self.deferred.callback(self.result)

class ProcessOnWin32TestCase(unittest.TestCase):
    def setUp(self):
        """gimme some threads"""
        self.deferred = defer.Deferred()
        self.pp = TestProcessPro(self.deferred)
        reactor.suggestThreadPoolSize(8)
    def tearDown(self):
        """clean up threads, otherwise the test hangs"""
        del self.deferred, self.pp
        reactor.suggestThreadPoolSize(0)
    def test_bad_exit(self):
        """runs wprocess_for_testing with an arg that makes it return error 1
        """
        reactor.spawnProcess(self.pp, 'python', ['-u', script, 'abort'],
                             env=os.environ)
        reason = util.wait(self.deferred)['reason']
        reason.trap(error.ProcessTerminated)
    def test_err_python(self):
        """runs wprocess_for_testing with an arg that makes it print to stderr
        """
        reactor.spawnProcess(self.pp, 'python', 
                             ['-u', script, 'stderr'],
                             env=os.environ)
        actual = util.wait(self.deferred)['err']
        expected = 'a\r\nb\r\nc\r\n'
        self.assertEqual(actual, expected)
    def test_err_nonpy(self):
        """runs more.com with an arg that makes it print to stderr
        """
        reactor.spawnProcess(self.pp, 'more.com', ['woop'], env=os.environ)
        actual = util.wait(self.deferred)['err']
        self.failUnless(actual.startswith('Cannot access file '))
        self.failUnless(actual.endswith('\r\n'))
    def test_good_exit(self):
        """runs wprocess_for_testing which exits cleanly
        """
        reactor.spawnProcess(self.pp, 'python', ['-u', script],
                             env=os.environ)
        reason = util.wait(self.deferred)['reason']
        reason.trap(error.ProcessDone)
    def test_in_python(self):
        """runs wprocess_for_testing with a stdin pipe
        """
        pr = reactor.spawnProcess(self.pp, 'python', 
                                  ['-u', script, 'stdin'],
                                  env=os.environ)
        pr.write('asdf\n')
        pr.closeStdin()
        actual = util.wait(self.deferred)['out']
        expected = 'a\r\ns\r\nd\r\nf\r\n'
        self.assertEqual(actual, expected)
    def test_out_python(self):
        """runs wprocess_for_testing normal, checks for output
        """
        reactor.spawnProcess(self.pp, 'python', ['-u', script],
                             env=os.environ)
        actual = util.wait(self.deferred)['out']
        expected = '1\r\n2\r\n3\r\n'
        self.assertEqual(actual, expected)
    def test_out_nonpy(self):
        """runs more.com normal, checks for output
        """
        file("woop", 'w').write('woop\n')
        reactor.spawnProcess(self.pp, 'more.com', ['woop'], env=os.environ)
        actual = util.wait(self.deferred)['out']
        expected = 'woop\r\n'
        self.assertEqual(actual, expected)
    def test_in_nonpy(self):
        """runs more.com with a stdin pipe
        """
        pr = reactor.spawnProcess(self.pp, 'more.com', [], env=os.environ)
        pr.write("woop\n")
        pr.closeStdin()
        actual = util.wait(self.deferred)['out']
        expected = 'woop\r\n\r\n'
        self.assertEqual(actual, expected)
    def test_loseConnection(self):
        """use loseConnection to end a process' life; make sure it aborted
        early
        """
        self._dieDieDie(diefunc = 'loseConnection')
    def test_killProcess(self):
        """send a signal to wprocess_for_testing to make it diediedie; make
        sure it aborted early
        """
        self._dieDieDie(diefunc = 'killProcess')
    def _dieDieDie(self, diefunc):
        """Kill a process using one of the supported methods.  Pass
        'loseConnection' or 'killProcess' for diefunc.
        """
        pr = reactor.spawnProcess(self.pp, 'python', ['-u', script],
                             env=os.environ)
        reactor.callLater(0.1, getattr(pr, diefunc))
        actual = util.wait(self.deferred)['out']
        expected = '1\r\n2\r\n3\r\n'
        # this test may be fragile or it may not -- if it fails, poke MFen
        # basically, test that some subset of expected appeared, but not 
        # the whole thing.. proving that the process was indeed interrupted
        # before finishing
        self.failUnless(actual.startswith('1\r\n'))
        self.failUnless(expected.startswith(actual))
        self.failIfEqual(actual, expected)

from twisted.python.runtime import platform
if platform.getType() != 'win32':
    ProcessOnWin32TestCase.skip = 'ignore wprocess when not on win32'
