
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


class UtilsTestCase(unittest.TestCase, SignalMixin):
    """Test running a process."""
    
    output = None
    value = None

    def testOutput(self):
        exe = sys.executable
        d=utils.getProcessOutput(exe, ['-c', 'print "hello world"'])
        d.addCallback(self.saveOutput)
        while self.output is None:
            reactor.iterate()
        self.assertEquals(self.output, "hello world\n")

    def testOutputWithError(self):
        exe = sys.executable
        sx = r'import sys; sys.stderr.write("hello world\n")'
        res1 = []
        # make sure stderr raises an error normally
        d = utils.getProcessOutput(exe, ['-c', sx], errortoo=0)
        d.addBoth(res1.append)
        while len(res1) == 0:
            reactor.iterate()
        self.failUnless(isinstance(res1.pop().value, IOError))
        # make sure the error can be turned off
        res2 = []
        d = utils.getProcessOutput(exe, ['-c', sx], errortoo=1)
        d.addBoth(res2.append)
        while len(res2) == 0:
            reactor.iterate()
        actual = res2[0]
        expected = 'hello world\n'
        self.assertEquals(actual, expected)

    def testValue(self):
        exe = sys.executable
        d=utils.getProcessValue(exe, ['-c', 'import sys;sys.exit(1)'])
        d.addCallback(self.saveValue)
        while self.value is None:
            reactor.iterate()
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
        while len(result) == 0:
            reactor.iterate()
        actual = result[0]
        expected = ('hello world!\n', 'goodbye world!\n', 1)
        self.assertEquals(actual, expected)

    def testOutputSignal(self):
        exe = sys.executable
        sx = r'import os, signal;os.kill(os.getpid(), signal.SIGHUP)'
        result = []
        d = utils.getProcessOutputAndValue(exe, ['-c', sx])
        d.addErrback(result.append)
        while len(result) == 0:
            reactor.iterate()
        actual = result[0].value
        expected = ('', '', signal.SIGHUP)
        self.assertEquals(actual, expected)

if not interfaces.IReactorProcess(reactor, None):
    UtilsTestCase.skip = "reactor doesn't implement IReactorProcess"
