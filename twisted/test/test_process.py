
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""
Test running processes.
"""
from __future__ import nested_scopes

from twisted.trial import unittest

import cStringIO, gzip, os, popen2, time, sys

# Twisted Imports
from twisted.internet import reactor, protocol, error
from twisted.python import util, runtime

class TrivialProcessProtocol(protocol.ProcessProtocol):
    finished = 0
    def processEnded(self, reason):
        self.finished = 1
        self.reason = reason


class TestProcessProtocol(protocol.ProcessProtocol):

    finished = 0

    def connectionMade(self):
        self.stages = [1]
        self.data = ''
        self.err = ''
        self.transport.write("abcd")

    def outReceived(self, data):
        self.data = self.data + data

    def outConnectionLost(self):
        self.stages.append(2)
        if self.data != "abcd":
            raise RuntimeError
        self.transport.write("1234")

    def errReceived(self, data):
        self.err = self.err + data

    def errConnectionLost(self):
        self.stages.append(3)
        if self.err != "1234":
            print 'err != 1234: ' + repr(self.err)
            raise RuntimeError()
        self.transport.write("abcd")
        self.stages.append(4)

    def inConnectionLost(self):
        self.stages.append(5)

    def processEnded(self, reason):
        self.finished = 1
        self.reason = reason

class EchoProtocol(protocol.ProcessProtocol):

    s = "1234567" * 1001
    finished = 0

    def connectionMade(self):
        for i in range(10):
            self.transport.write(self.s)
        self.buffer = ""

    def outReceived(self, data):
        self.buffer += data
        if len(self.buffer) == 70070:
            self.transport.loseConnection()

    def processEnded(self, reason):
        self.finished = 1

class SignalProtocol(protocol.ProcessProtocol):
    def __init__(self, sig):
        self.signal = sig
        self.going = 1

    def outReceived(self, data):
        self.transport.signalProcess(self.signal)

    def processEnded(self, reason):
        self.going = 0
        reason.trap(error.ProcessTerminated)
        assert reason.value.exitCode == None
        assert reason.value.signal == getattr(signal,'SIG'+self.signal)
        assert os.WTERMSIG(reason.value.status) == getattr(signal,'SIG'+self.signal), '%s %s' % (self.signal, os.WTERMSIG(reason.value.status))

class ProcessTestCase(unittest.TestCase):
    """Test running a process."""

    def testProcess(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_tester.py")
        p = TestProcessProtocol()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath])
        while not p.finished:
            reactor.iterate()
        self.assertEquals(p.stages, [1, 2, 3, 4, 5])

        # test status code
        f = p.reason
        f.trap(error.ProcessTerminated)
        self.assertEquals(f.value.exitCode, 23)
        # would .signal be available on non-posix?
        #self.assertEquals(f.value.signal, None)

        try:
            import process_tester
            os.remove(process_tester.test_file)
        except:
            pass

    def testEcho(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_echoer.py")
        p = EchoProtocol()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath])
        while not p.finished:
            reactor.iterate(0.01)
        self.assertEquals(len(p.buffer), len(p.s * 10))

class TwoProcessProtocol(protocol.ProcessProtocol):
    finished = 0
    num = -1
    def outReceived(self, data):
        pass
    def processEnded(self, reason):
        print "TwoProcessProtocol.processEnded [%d]" % self.num
        self.finished = 1
        self.check()
        
class TestTwoProcessesBase:
    def setUp(self):
        self.processes = [None, None]
        self.pp = [None, None]
        self.done = 0
        self.timeout = None
        self.verbose = 0
    def tearDown(self):
        if self.timeout:
            self.timeout.cancel()
            self.timeout = None
        # I don't think I can use os.kill outside of POSIX, so skip cleanup

    def createProcesses(self, usePTY=0):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_reader.py")
        for num in (0,1):
            self.pp[num] = TrivialProcessProtocol()
            self.pp[num].num = num 
            p = reactor.spawnProcess(self.pp[num],
                                     exe, [exe, "-u", scriptPath],
                                     usePTY=usePTY)
            self.processes[num] = p

    def close(self, num):
        if self.verbose: print "closing stdin [%d]" % num
        p = self.processes[num]
        pp = self.pp[num]
        self.failIf(pp.finished, "Process finished too early")
        p.loseConnection()
        if self.verbose: print self.pp[0].finished, self.pp[1].finished

    def giveUp(self):
        self.timeout = None
        self.done = 1
        if self.verbose: print "timeout"
        self.fail("timeout")
        
    def check(self):
        #print self.pp[0].finished, self.pp[1].finished
        #print "  ", self.pp[0].num, self.pp[1].num
        if self.pp[0].finished and self.pp[1].finished:
            self.done = 1
            
    def testClose(self):
        if self.verbose: print "starting processes"
        self.createProcesses()
        reactor.callLater(1, self.close, 0)
        reactor.callLater(2, self.close, 1)
        self.timeout = reactor.callLater(5, self.giveUp)
        self.check()
        while not self.done:
            reactor.iterate(0.01)
            self.check()

class TestTwoProcessesNonPosix(TestTwoProcessesBase, unittest.TestCase):
    pass

class TestTwoProcessesPosix(TestTwoProcessesBase, unittest.TestCase):
    def tearDown(self):
        TestTwoProcessesBase.tearDown(self)
        self.check()
        if self.done:
            return
        import signal
        for i in (0,1):
            pp, process = self.pp[i], self.processes[i]
            if not pp.finished:
                os.kill(process.pid, signal.SIGTERM)
        now = time.time()
        self.check()
        while not self.done or (time.time() > now + 5):
            reactor.iterate(0.01)
            self.check()
        if not self.done:
            print "unable to shutdown child processes"

    def kill(self, num):
        if self.verbose: print "kill [%d] with SIGTERM" % num
        p = self.processes[num]
        pp = self.pp[num]
        self.failIf(pp.finished, "Process finished too early")
        os.kill(p.pid, signal.SIGTERM)
        if self.verbose: print self.pp[0].finished, self.pp[1].finished

    def testKill(self):
        if self.verbose: print "starting processes"
        self.createProcesses(usePTY=0)
        reactor.callLater(1, self.kill, 0)
        reactor.callLater(2, self.kill, 1)
        self.timeout = reactor.callLater(5, self.giveUp)
        self.check()
        while not self.done:
            reactor.iterate(0.01)
            self.check()

    def testClosePty(self):
        if self.verbose: print "starting processes"
        self.createProcesses(usePTY=1)
        reactor.callLater(1, self.close, 0)
        reactor.callLater(2, self.close, 1)
        self.timeout = reactor.callLater(5, self.giveUp)
        self.check()
        while not self.done:
            reactor.iterate(0.01)
            self.check()
    testClosePty.todo = "still doesn't work yet"
    
    def testKillPty(self):
        if self.verbose: print "starting processes"
        self.createProcesses(usePTY=1)
        reactor.callLater(1, self.kill, 0)
        reactor.callLater(2, self.kill, 1)
        self.timeout = reactor.callLater(5, self.giveUp)
        self.check()
        while not self.done:
            reactor.iterate(0.01)
            self.check()

class Accumulator(protocol.ProcessProtocol):
    """Accumulate data from a process."""

    closed = 0

    def connectionMade(self):
        # print "connection made"
        self.outF = cStringIO.StringIO()
        self.errF = cStringIO.StringIO()

    def outReceived(self, d):
        # print "data", repr(d)
        self.outF.write(d)

    def errReceived(self, d):
        # print "err", repr(d)
        self.errF.write(d)

    def outConnectionLost(self):
        # print "out closed"
        pass

    def errConnectionLost(self):
        # print "err closed"
        pass

    def processEnded(self, reason):
        self.closed = 1


class PosixProcessTestCase(unittest.TestCase):
    """Test running processes."""
    usePTY = 0
        
    def testStdio(self):
        """twisted.internet.stdio test."""
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_twisted.py")
        p = Accumulator()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], None, None,
                             usePTY=self.usePTY)
        p.transport.write("hello, world")
        p.transport.write("abc")
        p.transport.write("123")
        p.transport.closeStdin()
        while not p.closed:
            reactor.iterate(0.01)
        self.assertEquals(p.outF.getvalue(), "hello, worldabc123", "Error message from process_twisted follows:\n\n%s\n\n" % p.errF.getvalue())

    def testProcess(self):
        if os.path.exists('/bin/gzip'): cmd = '/bin/gzip'
        elif os.path.exists('/usr/bin/gzip'): cmd = '/usr/bin/gzip'
        else: raise RuntimeError("gzip not found in /bin or /usr/bin")
        s = "there's no place like home!\n" * 3
        p = Accumulator()
        reactor.spawnProcess(p, cmd, [cmd, "-c"], {}, "/tmp",
                             usePTY=self.usePTY)
        p.transport.write(s)
        p.transport.closeStdin()

        while not p.closed:
            reactor.iterate(0.01)
        f = p.outF
        f.seek(0, 0)
        gf = gzip.GzipFile(fileobj=f)
        self.assertEquals(gf.read(), s)

    def testStderr(self):
        # we assume there is no file named ZZXXX..., both in . and in /tmp
        if not os.path.exists('/bin/ls'): raise RuntimeError("/bin/ls not found")

        p = Accumulator()
        reactor.spawnProcess(p, '/bin/ls', ["/bin/ls", "ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"], {}, "/tmp",
                             usePTY=self.usePTY)

        while not p.closed:
            reactor.iterate(0.01)
        self.assertEquals(lsOut, p.errF.getvalue())


    def testNormalTermination(self):
        if os.path.exists('/bin/true'): cmd = '/bin/true'
        elif os.path.exists('/usr/bin/true'): cmd = '/usr/bin/true'
        else: raise RuntimeError("true not found in /bin or /usr/bin")

        p = TrivialProcessProtocol()
        reactor.spawnProcess(p, cmd, ['true'],
                             usePTY=self.usePTY)

        while not p.finished:
            reactor.iterate(0.01)
        p.reason.trap(error.ProcessDone)
        self.assertEquals(p.reason.value.exitCode, 0)
        self.assertEquals(p.reason.value.signal, None)


    def testAbnormalTermination(self):
        if os.path.exists('/bin/false'): cmd = '/bin/false'
        elif os.path.exists('/usr/bin/false'): cmd = '/usr/bin/false'
        else: raise RuntimeError("false not found in /bin or /usr/bin")

        p = TrivialProcessProtocol()
        reactor.spawnProcess(p, cmd, ['false'],
                             usePTY=self.usePTY)

        while not p.finished:
            reactor.iterate(0.01)
        p.reason.trap(error.ProcessTerminated)
        self.assertEquals(p.reason.value.exitCode, 1)
        self.assertEquals(p.reason.value.signal, None)

    def testSignal(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_signal.py")
        signals = ('HUP', 'INT', 'KILL')
        protocols = []
        for sig in signals:
            p = SignalProtocol(sig)
            reactor.spawnProcess(p, exe, [exe, "-u", scriptPath, sig],
                                 usePTY=self.usePTY)
            protocols.append(p)

        while reduce(lambda a,b:a+b,[p.going for p in protocols]):
            reactor.iterate()

class PosixProcessTestCasePTY(PosixProcessTestCase):
    """Just like PosixProcessTestCase, but use ptys instead of pipes."""
    usePTY = 1
    def testStderr(self):
        # pass-through method to give us something to hang the .todo from
        PosixProcessTestCase.testStderr(self)
    testStderr.todo = "still broken"
    def testProcess(self):
        PosixProcessTestCase.testProcess(self)
    testProcess.todo = "still broken"
    def testStdio(self):
        PosixProcessTestCase.testStdio(self)
    testStdio.skip = "hangs completely"
    
class Win32ProcessTestCase(unittest.TestCase):
    """Test process programs that are packaged with twisted."""

    def testStdinReader(self):
        pyExe = sys.executable
        scriptPath = util.sibpath(__file__, "process_stdinreader.py")
        p = Accumulator()
        reactor.spawnProcess(p, pyExe, [pyExe, "-u", scriptPath], None, None)
        p.transport.write("hello, world")
        p.transport.closeStdin()

        while not p.closed:
            reactor.iterate()
        self.assertEquals(p.errF.getvalue(), "err\nerr\n")
        self.assertEquals(p.outF.getvalue(), "out\nhello, world\nout\n")


if runtime.platform.getType() != 'posix':
    del PosixProcessTestCase
    del PosixProcessTestCasePTY
    del TestTwoProcessesPosix
else:
    lsOut = popen2.popen3("/bin/ls ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")[2].read()
    # make sure SIGCHLD handler is installed, as it should be on reactor.run().
    # problem is reactor may not have been run when this test runs.
    import signal
    from twisted.internet import process
    signal.signal(signal.SIGCHLD, reactor._handleSigchld)

if runtime.platform.getType() != 'win32':
    del Win32ProcessTestCase
    del TestTwoProcessesNonPosix
else:
    def testEcho(self): raise RuntimeError, "this test is disabled since it goes into infinite loop on windows :("
    ProcessTestCase.testEcho = testEcho
