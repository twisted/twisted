
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test running processes.
"""

from twisted.trial import unittest, util, assertions
from twisted.test.test_process import SignalMixin

import gzip, os, popen2, time, sys, signal

# Twisted Imports
from twisted.internet import reactor, utils, interfaces
from twisted.python import components


class UtilsTestCase(SignalMixin, unittest.TestCase):
    """Test running a process."""

    output = None
    value = None

    def makeSourceFile(self, source):
        script = self.mktemp()
        scriptFile = file(script, 'wt')
        scriptFile.write(source)
        scriptFile.close()
        return script

    def testOutput(self):
        scriptFile = self.makeSourceFile('print "hello world"\n')
        d = utils.getProcessOutput(sys.executable, [scriptFile])
        return d.addCallback(self.assertEquals, "hello world\n")

    def testOutputWithErrorIgnored(self):
        # make sure stderr raises an error normally
        exe = sys.executable
        scriptFile = self.makeSourceFile(
            'import sys\n'
            'sys.stderr.write("hello world\\n")\n')

        d = utils.getProcessOutput(exe, [scriptFile], errortoo=0)
        return assertions.assertFailure(d, IOError)

    def testOutputWithErrorCollected(self):
        # make sure stderr raises an error normally
        exe = sys.executable
        scriptFile = self.makeSourceFile(
            'import sys\n'
            'sys.stderr.write("hello world\\n")\n')

        d = utils.getProcessOutput(exe, [scriptFile], errortoo=1)
        return d.addCallback(self.assertEquals, "hello world\n")

    def testValue(self):
        exe = sys.executable
        scriptFile = self.makeSourceFile(
            "import sys\n"
            "sys.exit(1)\n")

        d = utils.getProcessValue(exe, [scriptFile])
        return d.addCallback(self.assertEquals, 1)

    def testOutputAndValue(self):
        exe = sys.executable
        scriptFile = self.makeSourceFile(
            "import sys\n"
            "sys.stdout.write('hello world!\\n')\n"
            "sys.stderr.write('goodbye world!\\n')\n"
            "sys.exit(1)")

        def gotOutputAndValue((out, err, code)):
            self.assertEquals(out, "hello world!\n")
            self.assertEquals(err, "goodbye world!\n")
            self.assertEquals(code, 1)
        d = utils.getProcessOutputAndValue(exe, [scriptFile])
        return d.addCallback(gotOutputAndValue)

    def testOutputSignal(self):
        # Use SIGKILL here because it's guaranteed to be delivered. Using
        # SIGHUP might not work in, e.g., a buildbot slave run under the
        # 'nohup' command.
        exe = sys.executable
        scriptFile = self.makeSourceFile(
            "import sys, os, signal\n"
            "sys.stdout.write('stdout bytes\\n')\n"
            "sys.stderr.write('stderr bytes\\n')\n"
            "sys.stdout.flush()\n"
            "sys.stderr.flush()\n"
            "os.kill(os.getpid(), signal.SIGKILL)\n")

        def gotOutputAndValue(err):
            (out, err, sig) = err.value # XXX Sigh wtf
            self.assertEquals(out, "stdout bytes\n")
            self.assertEquals(err, "stderr bytes\n")
            self.assertEquals(sig, signal.SIGKILL)

        d = utils.getProcessOutputAndValue(exe, [scriptFile])
        return d.addErrback(gotOutputAndValue)

if interfaces.IReactorProcess(reactor, None) is None:
    UtilsTestCase.skip = "reactor doesn't implement IReactorProcess"
