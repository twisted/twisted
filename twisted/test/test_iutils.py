
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test running processes.
"""

from twisted.trial import unittest, util
from twisted.test.test_process import SignalMixin

import gzip, os, popen2, time, sys, signal

# Twisted Imports
from twisted.internet import reactor, utils, interfaces
from twisted.python import components


class UtilsTestCase(SignalMixin, unittest.TestCase):
    """Test running a process."""
    
    output = None
    value = None

    def testOutput(self):
        exe = sys.executable
        d=utils.getProcessOutput(exe, ['-c', 'print "hello world"'])
        d.addCallback(self.saveOutput)
        ttl = time.time() + 5
        while self.output is None and time.time() < ttl:
            reactor.iterate(0.01)
        self.failIf(self.output is None, "timeout")
        self.assertEquals(self.output, "hello world\n")

    def testOutputWithError(self):
        exe = sys.executable
        sx = r'import sys; sys.stderr.write("hello world\n")'
        res1 = []
        # make sure stderr raises an error normally
        d = utils.getProcessOutput(exe, ['-c', sx], errortoo=0)
        d.addBoth(res1.append)
        ttl = time.time() + 5
        while len(res1) == 0 and time.time() < ttl:
            reactor.iterate(0.01)
        self.failUnless(len(res1), "timeout")
        self.failUnless(isinstance(res1.pop().value, IOError))
        # make sure the error can be turned off
        res2 = []
        d = utils.getProcessOutput(exe, ['-c', sx], errortoo=1)
        d.addBoth(res2.append)
        ttl = time.time() + 5
        while len(res2) == 0 and time.time() < ttl:
            reactor.iterate(0.01)
        self.failUnless(len(res2), "timeout")
        actual = res2[0]
        expected = 'hello world\n'
        self.assertEquals(actual, expected)

    def testValue(self):
        exe = sys.executable
        d=utils.getProcessValue(exe, ['-c', 'import sys;sys.exit(1)'])
        d.addCallback(self.saveValue)
        ttl = time.time() + 5
        while self.value is None and time.time() < ttl:
            reactor.iterate(0.01)
        self.failIf(self.value is None, "timeout")
        self.assertEquals(self.value, 1)

    def saveValue(self, o):
        self.value = o

    def saveOutput(self, o):
        self.output = o

    def testOutputAndValue(self):
        exe = sys.executable
        sx = r'import sys; sys.stdout.write("hello world!\n"); ' \
             r'sys.stderr.write("goodbye world!\n"); sys.exit(1)'
        result = []
        d = utils.getProcessOutputAndValue(exe, ['-c', sx])
        d.addCallback(result.append)
        ttl = time.time() + 5
        while len(result) == 0 and time.time() < ttl:
            reactor.iterate(0.01)
        self.failUnless(len(result), "timeout")
        actual = result[0]
        expected = ('hello world!\n', 'goodbye world!\n', 1)
        self.assertEquals(actual, expected)

    def testOutputSignal(self):
        # Use SIGKILL here because it's guaranteed to be delivered. Using
        # SIGHUP might not work in, e.g., a buildbot slave run under the
        # 'nohup' command.
        exe = sys.executable
        sx = r'import os, signal;os.kill(os.getpid(), signal.SIGKILL)'
        result = []
        d = utils.getProcessOutputAndValue(exe, ['-c', sx])
        d.addErrback(result.append)
        ttl = time.time() + 5
        while len(result) == 0 and time.time() < ttl:
            reactor.iterate(0.01)
        self.failUnless(len(result), "timeout")
        actual = result[0].value
        expected = ('', '', signal.SIGKILL)
        self.assertEquals(actual, expected)

if not interfaces.IReactorProcess(reactor, None):
    UtilsTestCase.skip = "reactor doesn't implement IReactorProcess"
