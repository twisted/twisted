
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

import gzip
import os
import popen2
import time
import sys
import signal

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

# Twisted Imports
from twisted.internet import reactor, protocol, error, interfaces
from twisted.python import util, runtime, components
from twisted.runner import procutils

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
            self.transport.closeStdin()

    def processEnded(self, reason):
        self.finished = 1
        if not isinstance(reason.value, error.ProcessDone):
            print reason
            raise "process didn't terminate normally"

class SignalProtocol(protocol.ProcessProtocol):
    def __init__(self, sig, testcase):
        self.signal = sig
        self.going = 1
        self.testcase = testcase
        
    def outReceived(self, data):
        self.transport.signalProcess(self.signal)

    def processEnded(self, reason):
        self.going = 0
        reason.trap(error.ProcessTerminated)
        v = reason.value
        self.testcase.assertEquals(v.exitCode, None,
                                   "SIG%s: exitCode is %s, not None" % \
                                   (self.signal, v.exitCode))
        self.testcase.assertEquals(v.signal,
                                   getattr(signal,'SIG'+self.signal),
                                   "SIG%s: .signal was %s, wanted %s" % \
                                   (self.signal, v.signal,
                                    getattr(signal,'SIG'+self.signal)))
        self.testcase.assertEquals(os.WTERMSIG(v.status),
                                   getattr(signal,'SIG'+self.signal),
                                   'SIG%s: %s' % (self.signal,
                                                  os.WTERMSIG(v.status)))

class SignalMixin:
    sigchldHandler = None
    
    def setUpClass(self):
        # make sure SIGCHLD handler is installed, as it should be on reactor.run().
        # problem is reactor may not have been run when this test runs.
        if hasattr(reactor, "_handleSigchld") and hasattr(signal, "SIGCHLD"):
            self.sigchldHandler = signal.signal(signal.SIGCHLD, reactor._handleSigchld)
    
    def tearDownClass(self):
        if self.sigchldHandler:
            signal.signal(signal.SIGCHLD, self.sigchldHandler)


class PausingProcessProtocol(protocol.ProcessProtocol):

    data = ""
    elapsed = None
    
    def connectionMade(self):
        self.transport.pauseProducing()
        self.transport.write("a")
        reactor.callLater(2, self.transport.resumeProducing)
    
    def outReceived(self, d):
        self.data += d

    def processEnded(self, reason):
        self.data = self.data.lstrip("a")
        if len(self.data) != 5: raise ValueError
        self.elapsed = float(self.data)


class ProcessTestCase(SignalMixin, unittest.TestCase):
    """Test running a process."""

    def testProcess(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_tester.py")
        p = TestProcessProtocol()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None)

        timeout = time.time() + 10
        while not p.finished and not (time.time() > timeout):
            reactor.iterate(0.01)
        self.failUnless(p.finished)
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
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None)
        while not p.finished:
            reactor.iterate(0.01)
        self.assert_(hasattr(p, 'buffer'))
        self.assertEquals(len(p.buffer), len(p.s * 10))

    def testPausing(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_pausing.py")
        p = PausingProcessProtocol()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None)
        while p.elapsed == None:
            reactor.iterate(0.01)
        self.assert_(2.1 > p.elapsed > 1.5) # assert how long process was paused


class TwoProcessProtocol(protocol.ProcessProtocol):
    finished = 0
    num = -1
    def outReceived(self, data):
        pass
    def processEnded(self, reason):
        self.finished = 1
        
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
            self.pp[num] = TwoProcessProtocol()
            self.pp[num].num = num 
            p = reactor.spawnProcess(self.pp[num],
                                     exe, [exe, "-u", scriptPath], env=None,
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

class TestTwoProcessesNonPosix(TestTwoProcessesBase, SignalMixin, unittest.TestCase):
    pass

class TestTwoProcessesPosix(TestTwoProcessesBase, SignalMixin, unittest.TestCase):
    def tearDown(self):
        TestTwoProcessesBase.tearDown(self)
        self.check()
        for i in (0,1):
            pp, process = self.pp[i], self.processes[i]
            if not pp.finished:
                try:
                    os.kill(process.pid, signal.SIGTERM)
                except OSError:
                    print "OSError"
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

class FDChecker(protocol.ProcessProtocol):
    state = 0
    data = ""
    done = False
    failed = None

    def fail(self, why):
        self.failed = why
        self.done = True

    def connectionMade(self):
        self.transport.writeToChild(0, "abcd")
        self.state = 1

    def childDataReceived(self, childFD, data):
        #print "[%d] dataReceived(%d,%s)" % (self.state, childFD, data)
        if self.state == 1:
            if childFD != 1:
                self.fail("read '%s' on fd %d (not 1) during state 1" \
                          % (childFD, data))
                return
            self.data += data
            #print "len", len(self.data)
            if len(self.data) == 6:
                if self.data != "righto":
                    self.fail("got '%s' on fd1, expected 'righto'" \
                              % self.data)
                    return
                self.data = ""
                self.state = 2
                #print "state2", self.state
                self.transport.writeToChild(3, "efgh")
                return
        if self.state == 2:
            self.fail("read '%s' on fd %s during state 2" % (childFD, data))
            return
        if self.state == 3:
            if childFD != 1:
                self.fail("read '%s' on fd %s (not 1) during state 3" \
                          % (childFD, data))
                return
            self.data += data
            if len(self.data) == 6:
                if self.data != "closed":
                    self.fail("got '%s' on fd1, expected 'closed'" \
                              % self.data)
                    return
                self.state = 4
            return
        if self.state == 4:
            self.fail("read '%s' on fd %s during state 4" % (childFD, data))
            return

    def childConnectionLost(self, childFD):
        #print "[%d] connectionLost(%d)" % (self.state, childFD)
        if self.state == 1:
            self.fail("got connectionLost(%d) during state 1" % childFD)
            return
        if self.state == 2:
            if childFD != 4:
                self.fail("got connectionLost(%d) (not 4) during state 2" \
                          % childFD)
                return
            self.state = 3
            self.transport.closeChildFD(5)
            return

    def processEnded(self, status):
        #print "[%d] processEnded" % self.state
        rc = status.value.exitCode
        if self.state != 4:
            self.fail("processEnded early, rc %d" % rc)
            return
        if status.value.signal != None:
            self.fail("processEnded with signal %s" % status.value.signal)
            return
        if rc != 0:
            self.fail("processEnded with rc %d" % rc)
            return
        self.done = True

class FDTest(SignalMixin, unittest.TestCase):
    def NOTsetUp(self):
        from twisted.internet import process
        process.Process.debug_child = True
    def NOTtearDown(self):
        from twisted.internet import process
        process.Process.debug_child = False

    def testFD(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_fds.py")
        p = FDChecker()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None,
                             path=None,
                             childFDs={0:"w", 1:"r", 2:2,
                                       3:"w", 4:"r", 5:"w"})
        timeout = time.time() + 5
        while not p.done and time.time() < timeout:
            reactor.iterate(0.01)
        self.failUnless(p.done, "timeout")
        self.failIf(p.failed, p.failed)

    def testLinger(self):
        # See what happens when all the pipes close before the process
        # actually stops. This test *requires* SIGCHLD catching to work,
        # as there is no other way to find out the process is done.
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_linger.py")
        p = Accumulator()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None,
                             path=None,
                             childFDs={1:"r", 2:2},
                             )
        timeout = time.time() + 7
        while not p.closed and time.time() < timeout:
            reactor.iterate(0.01)
        self.failUnless(p.closed, "timeout")
        self.failUnlessEqual(p.outF.getvalue(),
                             "here is some text\ngoodbye\n")

class Accumulator(protocol.ProcessProtocol):
    """Accumulate data from a process."""

    closed = 0

    def connectionMade(self):
        # print "connection made"
        self.outF = StringIO.StringIO()
        self.errF = StringIO.StringIO()

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


class PosixProcessBase:
    """Test running processes."""
    usePTY = 0

    def testNormalTermination(self):
        if os.path.exists('/bin/true'): cmd = '/bin/true'
        elif os.path.exists('/usr/bin/true'): cmd = '/usr/bin/true'
        else: raise RuntimeError("true not found in /bin or /usr/bin")

        p = TrivialProcessProtocol()
        reactor.spawnProcess(p, cmd, ['true'], env=None,
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
        reactor.spawnProcess(p, cmd, ['false'], env=None,
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
            p = SignalProtocol(sig, self)
            reactor.spawnProcess(p, exe, [exe, "-u", scriptPath, sig],
                                 env=None,
                                 usePTY=self.usePTY)
            protocols.append(p)

        while reduce(lambda a,b:a+b,[p.going for p in protocols]):
            reactor.iterate(0.01)

class PosixProcessTestCase(SignalMixin, unittest.TestCase, PosixProcessBase):
    # add three non-pty test cases
        
    def testStdio(self):
        """twisted.internet.stdio test."""
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_twisted.py")
        p = Accumulator()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None,
                             path=None, usePTY=self.usePTY)
        p.transport.write("hello, world")
        p.transport.write("abc")
        p.transport.write("123")
        p.transport.closeStdin()
        timeout = time.time() + 10
        while not p.closed and not (time.time() > timeout):
            reactor.iterate(0.01)
        self.failUnless(p.closed)
        self.assertEquals(p.outF.getvalue(), "hello, worldabc123", "Error message from process_twisted follows:\n\n%s\n\n" % p.errF.getvalue())

    def testStderr(self):
        # we assume there is no file named ZZXXX..., both in . and in /tmp
        if not os.path.exists('/bin/ls'): raise RuntimeError("/bin/ls not found")

        p = Accumulator()
        reactor.spawnProcess(p, '/bin/ls',
                             ["/bin/ls",
                              "ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"],
                             env=None, path="/tmp",
                             usePTY=self.usePTY)

        while not p.closed:
            reactor.iterate(0.01)
        self.assertEquals(lsOut, p.errF.getvalue())

    def testProcess(self):
        if os.path.exists('/bin/gzip'): cmd = '/bin/gzip'
        elif os.path.exists('/usr/bin/gzip'): cmd = '/usr/bin/gzip'
        else: raise RuntimeError("gzip not found in /bin or /usr/bin")
        s = "there's no place like home!\n" * 3
        p = Accumulator()
        reactor.spawnProcess(p, cmd, [cmd, "-c"], env=None, path="/tmp",
                             usePTY=self.usePTY)
        p.transport.write(s)
        p.transport.closeStdin()

        timeout = time.time() + 10
        while not p.closed and not (time.time() > timeout):
            reactor.iterate(0.01)
        self.failUnless(p.closed)
        f = p.outF
        f.seek(0, 0)
        gf = gzip.GzipFile(fileobj=f)
        self.assertEquals(gf.read(), s)
    
class PosixProcessTestCasePTY(SignalMixin, unittest.TestCase, PosixProcessBase):
    """Just like PosixProcessTestCase, but use ptys instead of pipes."""
    usePTY = 1
    # PTYs only offer one input and one output. What still makes sense?
    # testNormalTermination
    # testAbnormalTermination
    # testSignal
    # testProcess, but not without p.transport.closeStdin
    #  might be solveable: TODO: add test if so
    
class Win32ProcessTestCase(SignalMixin, unittest.TestCase):
    """Test process programs that are packaged with twisted."""

    def testStdinReader(self):
        pyExe = sys.executable
        scriptPath = util.sibpath(__file__, "process_stdinreader.py")
        p = Accumulator()
        reactor.spawnProcess(p, pyExe, [pyExe, "-u", scriptPath], env=None,
                             path=None)
        p.transport.write("hello, world")
        p.transport.closeStdin()

        while not p.closed:
            reactor.iterate(0.01)
        self.assertEquals(p.errF.getvalue(), "err\nerr\n")
        self.assertEquals(p.outF.getvalue(), "out\nhello, world\nout\n")

class UtilTestCase(unittest.TestCase):
    def setUpClass(klass):
        j = os.path.join
        foobar = j("foo", "bar")
        foobaz = j("foo", "baz")
        bazfoo = j("baz", "foo")
        barfoo = j("baz", "bar")
        
        for d in "foo", foobar, foobaz, "baz", bazfoo, barfoo:
            os.mkdir(d)
        
        f = file(j(foobaz, "executable"), "w")
        f.close()
        os.chmod(j(foobaz, "executable"), 0700)
        
        f = file(j("foo", "executable"), "w")
        f.close()
        os.chmod(j("foo", "executable"), 0700)
        
        f = file(j(bazfoo, "executable"), "w")
        f.close()
        os.chmod(j(bazfoo, "executable"), 0700)
        
        f = file(j(bazfoo, "executable.bin"), "w")
        f.close()
        os.chmod(j(bazfoo, "executable.bin"), 0700)
        
        f = file(j(barfoo, "executable"), "w")
        f.close()
        
        klass.oldPath = os.environ['PATH']
        os.environ['PATH'] = os.pathsep.join((foobar, foobaz, bazfoo, barfoo))
    
    def tearDownClass(klass):
        os.environ['PATH'] = klass.oldPath
    
    def testWhich(self):
        j = os.path.join
        paths = procutils.which("executable")
        self.assertEquals(paths, [
            j("foo", "baz", "executable"), j("baz", "foo", "executable")
        ])
    
    def testWhichPathExt(self):
        j = os.path.join
        old = os.environ.get('PATHEXT', None)
        os.environ['PATHEXT'] = os.pathsep.join(('.bin', '.exe', '.sh'))
        try:
            paths = procutils.which("executable")
        finally:
            if old is None:
                del os.environ['PATHEXT']
            else:
                os.environ['PATHEXT'] = old
        self.assertEquals(paths, [
            j("foo", "baz", "executable"), j("baz", "foo", "executable"),
            j("baz", "foo", "executable.bin")
        ])

skipMessage = "wrong platform or reactor doesn't support IReactorProcess"
if (runtime.platform.getType() != 'posix') or (not components.implements(reactor, interfaces.IReactorProcess)):
    PosixProcessTestCase.skip = skipMessage
    PosixProcessTestCasePTY.skip = skipMessage
    TestTwoProcessesPosix.skip = skipMessage
    FDTest.skip = skipMessage
else:
    # do this before running the tests: it uses SIGCHLD and stuff internally
    lsOut = popen2.popen3("/bin/ls ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")[2].read()

if (runtime.platform.getType() != 'win32') or (not components.implements(reactor, interfaces.IReactorProcess)):
    Win32ProcessTestCase.skip = skipMessage
    TestTwoProcessesNonPosix.skip = skipMessage

if runtime.platform.getType() == 'win32':
    ProcessTestCase.testEcho.im_func.todo = "goes into infinite loop in win32eventreactor :("
    UtilTestCase.todo = "do not assume that platform retains 'executable' mode"

if (not components.implements(reactor, interfaces.IReactorProcess)):
    ProcessTestCase.skip = skipMessage
