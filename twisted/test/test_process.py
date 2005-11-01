
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test running processes.
"""
from __future__ import nested_scopes, generators

from twisted.trial import unittest
from twisted.trial.util import spinUntil, spinWhile
from twisted.python import log

import gzip
import os
import popen2
import time
import sys
import signal
import shutil

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

# Twisted Imports
from twisted.internet import reactor, protocol, error, interfaces, defer
from twisted.python import util, runtime, components
from twisted.python import procutils

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
    n = 10
    finished = 0

    failure = None

    def __init__(self, onEnded):
        self.onEnded = onEnded
        self.count = 0

    def connectionMade(self):
        assert self.n > 2
        for i in range(self.n - 2):
            self.transport.write(self.s)
        # test writeSequence
        self.transport.writeSequence([self.s, self.s])
        self.buffer = self.s * self.n
    
    def outReceived(self, data):
        if buffer(self.buffer, self.count, len(data)) != buffer(data):
            self.failure = ("wrong bytes received", data, self.count)
            self.transport.closeStdin()
        else:
            self.count += len(data)
            if self.count == len(self.buffer):
                self.transport.closeStdin()

    def processEnded(self, reason):
        self.finished = 1
        if not reason.check(error.ProcessDone):
            self.failure = "process didn't terminate normally: " + str(reason)
        self.onEnded.callback(self)


class SignalProtocol(protocol.ProcessProtocol):
    def __init__(self, sig, testcase):
        self.signal = sig
        self.going = 1
        self.testcase = testcase
        
    def outReceived(self, data):
        self.transport.signalProcess(self.signal)

    def processEnded(self, reason):
        self.going = 0
        if not reason.check(error.ProcessTerminated):
            self.failure = "wrong termination: %s" % reason
            return
        v = reason.value
        if v.exitCode is not None:
            self.failure = "SIG%s: exitCode is %s, not None" % \
                           (self.signal, v.exitCode)
            return
        if v.signal != getattr(signal,'SIG'+self.signal):
            self.failure = "SIG%s: .signal was %s, wanted %s" % \
                           (self.signal, v.signal,
                            getattr(signal,'SIG'+self.signal))
            return
        if os.WTERMSIG(v.status) != getattr(signal,'SIG'+self.signal):
            self.failure = 'SIG%s: %s' % (self.signal,
                                          os.WTERMSIG(v.status))
            return
        self.failure = None

class SignalMixin:
    # XXX: Trial now does this (see
    #      twisted.trial.runner.MethodInfoBase._setUpSigchldHandler)... perhaps
    #      this class should be removed?  Or trial shouldn't bother, and this
    #      class used where it matters?
    #        - spiv, 2005-04-01
    sigchldHandler = None
    
    def setUpClass(self):
        # make sure SIGCHLD handler is installed, as it should be on
        # reactor.run(). Do this because the reactor may not have been run
        # by the time this test runs.
        if hasattr(reactor, "_handleSigchld") and hasattr(signal, "SIGCHLD"):
            log.msg("Installing SIGCHLD signal handler.")
            self.sigchldHandler = signal.signal(signal.SIGCHLD,
                                                reactor._handleSigchld)
        else:
            log.msg("Skipped installing SIGCHLD signal handler.")
    
    def tearDownClass(self):
        if self.sigchldHandler:
            log.msg("Uninstalled SIGCHLD signal handler.")
            signal.signal(signal.SIGCHLD, self.sigchldHandler)


class ProcessTestCase(SignalMixin, unittest.TestCase):
    """Test running a process."""

    def testProcess(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_tester.py")
        p = TestProcessProtocol()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None)

        spinUntil(lambda :p.finished, 10)
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
        finished = defer.Deferred()
        p = EchoProtocol(finished)

        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_echoer.py")
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None)

        def asserts(ignored):
            self.failIf(p.failure, p.failure)
            self.failUnless(hasattr(p, 'buffer'))
            self.assertEquals(len(''.join(p.buffer)), len(p.s * p.n))

        def takedownProcess(err):
            p.transport.closeStdin()
            return err

        return finished.addCallback(asserts).addErrback(takedownProcess)

    def testCommandLine(self):
        args = [r'a\"b ', r'a\b ', r' a\\"b', r' a\\b', r'"foo bar" "']
        pyExe = sys.executable
        scriptPath = util.sibpath(__file__, "process_cmdline.py")
        p = Accumulator()
        reactor.spawnProcess(p, pyExe, [pyExe, "-u", scriptPath]+args, env=None,
                             path=None)

        spinUntil(lambda :p.closed)
        self.assertEquals(p.errF.getvalue(), "")
        recvdArgs = p.outF.getvalue().splitlines()
        self.assertEquals(recvdArgs, args)
        
    testEcho.timeout = 60

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
        self.verbose = 0

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
        
    def check(self):
        #print self.pp[0].finished, self.pp[1].finished
        #print "  ", self.pp[0].num, self.pp[1].num
        if self.pp[0].finished and self.pp[1].finished:
            self.done = 1
        return self.done
            
    def testClose(self):
        if self.verbose: print "starting processes"
        self.createProcesses()
        reactor.callLater(1, self.close, 0)
        reactor.callLater(2, self.close, 1)
        spinUntil(self.check, 5)

class TestTwoProcessesNonPosix(TestTwoProcessesBase, SignalMixin, unittest.TestCase):
    pass

class TestTwoProcessesPosix(TestTwoProcessesBase, SignalMixin, unittest.TestCase):
    def tearDown(self):
        self.check()
        for i in (0,1):
            pp, process = self.pp[i], self.processes[i]
            if not pp.finished:
                try:
                    os.kill(process.pid, signal.SIGTERM)
                except OSError:
                    print "OSError"
        spinUntil(self.check, 5, msg="unable to shutdown child processes")

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
        spinUntil(self.check, 5)

    def testClosePty(self):
        if self.verbose: print "starting processes"
        self.createProcesses(usePTY=1)
        reactor.callLater(1, self.close, 0)
        reactor.callLater(2, self.close, 1)
        spinUntil(self.check, 5)
    
    def testKillPty(self):
        if self.verbose: print "starting processes"
        self.createProcesses(usePTY=1)
        reactor.callLater(1, self.kill, 0)
        reactor.callLater(2, self.kill, 1)
        spinUntil(self.check, 5)

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
        spinUntil(lambda :p.done, 5)
        self.failIf(p.failed, p.failed)

    if sys.platform.find("freebsd") != -1:
        testFD.todo = "This test fails on freebsd5 - slyphon"

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
        spinUntil(lambda :p.closed, 7)
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

        spinUntil(lambda :p.finished)
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

        spinUntil(lambda :p.finished)
        p.reason.trap(error.ProcessTerminated)
        self.assertEquals(p.reason.value.exitCode, 1)
        self.assertEquals(p.reason.value.signal, None)

    def testSignal(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_signal.py")
        signals = ('HUP', 'INT', 'KILL')
        for sig in signals:
            p = SignalProtocol(sig, self)
            reactor.spawnProcess(p, exe, [exe, "-u", scriptPath, sig],
                                 env=None,
                                 usePTY=self.usePTY)
            spinWhile(lambda :p.going)
            self.failIf(p.failure, p.failure)

class PosixProcessTestCase(SignalMixin, unittest.TestCase, PosixProcessBase):
    # add three non-pty test cases
        
    def testStdio(self):
        """twisted.internet.stdio test."""
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_twisted.py")
        p = Accumulator()
        # As trial chdirs to _trial_temp after startup, this makes any
        # possible relative entries in PYTHONPATH invalid. Attempt to
        # fix that up.  Otherwise process_twisted.py will use the
        # installed Twisted, which isn't really guaranteed to exist at
        # this stage.
        def fixup(l):
            for path in l:
                if os.path.isabs(path):
                    yield path
                else:
                    yield os.path.join(os.path.pardir, path)
        env = {"PYTHONPATH": os.pathsep.join(fixup(sys.path))}
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=env,
                             path=None, usePTY=self.usePTY)
        p.transport.write("hello, world")
        p.transport.write("abc")
        p.transport.write("123")
        p.transport.closeStdin()
        spinUntil(lambda :p.closed, 10)
        self.assertEquals(p.outF.getvalue(), "hello, worldabc123",
                          "Error message from process_twisted follows:"
                          "\n\n%s\n\n" % p.errF.getvalue())

    def testStderr(self):
        # we assume there is no file named ZZXXX..., both in . and in /tmp
        if not os.path.exists('/bin/ls'):
            raise RuntimeError("/bin/ls not found")

        p = Accumulator()
        reactor.spawnProcess(p, '/bin/ls',
                             ["/bin/ls",
                              "ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"],
                             env=None, path="/tmp",
                             usePTY=self.usePTY)

        spinUntil(lambda :p.closed)
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

        spinUntil(lambda :p.closed, 10)
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

    def testOpeningTTY(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_tty.py")
        p = Accumulator()
        
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None,
                            path=None, usePTY=self.usePTY)
        p.transport.write("hello world!\n")
        spinUntil(lambda :p.closed, 10)
        self.assertEquals(p.outF.getvalue(), "hello world!\r\nhello world!\r\n", "Error message from process_tty follows:\n\n%s\n\n" % p.outF.getvalue())
    
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

        spinUntil(lambda :p.closed)
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
            if os.path.exists(d):
                shutil.rmtree(d, True)
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
        j = os.path.join
        os.environ['PATH'] = klass.oldPath
        foobar = j("foo", "bar")
        foobaz = j("foo", "baz")
        bazfoo = j("baz", "foo")
        barfoo = j("baz", "bar")
        
       
        os.remove(j(foobaz, "executable"))
        os.remove(j("foo", "executable"))
        os.remove(j(bazfoo, "executable"))
        os.remove(j(bazfoo, "executable.bin"))
        os.remove(j(barfoo, "executable"))

        for d in foobar, foobaz, bazfoo, barfoo, "foo", "baz":
            os.rmdir(d)
     
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

class ClosingPipesProcessProtocol(protocol.ProcessProtocol):
    output = ''
    errput = ''

    def __init__(self, outOrErr):
        self.deferred = defer.Deferred()
        self.outOrErr = outOrErr

    def processEnded(self, reason):
        self.deferred.callback(reason)

    def outReceived(self, data):
        self.output += data

    def errReceived(self, data):
        self.errput += data


class ClosingPipes(unittest.TestCase):

    def doit(self, fd):
        p = ClosingPipesProcessProtocol(True)
        p.deferred.addCallbacks(
            callback=lambda _: self.fail("I wanted an errback."),
            errback=self._endProcess, errbackArgs=(p,))
        reactor.spawnProcess(p, sys.executable,
                             [sys.executable, '-u', '-c', 
                              r'raw_input(); import sys, os; os.write(%d, "foo\n"); sys.exit(42)' % fd],
                             env=None)
        p.transport.write('go\n')

        if fd == 1:
            p.transport.closeStdout()
        elif fd == 2:
            p.transport.closeStderr()
        else:
            raise RuntimeError

        # make the buggy case not hang
        p.transport.closeStdin()
        return p.deferred

    def _endProcess(self, reason, p):
        self.failIf(reason.check(error.ProcessDone),
                    'Child should fail due to EPIPE.')
        reason.trap(error.ProcessTerminated)
        # child must not get past that write without raising
        self.failIfEqual(reason.value.exitCode, 42, 
                         'process reason was %r' % reason)
        self.failUnlessEqual(p.output, '')
        return p.errput

    def test_stdout(self):
        """ProcessProtocol.transport.closeStdout actually closes the pipe."""
        d = self.doit(1)
        def _check(errput):
            self.failIfEqual(errput.index('OSError'), -1)
            self.failIfEqual(errput.index('Broken pipe'), -1)
        d.addCallback(_check)
        return d

    def test_stderr(self):
        """ProcessProtocol.transport.closeStderr actually closes the pipe."""
        d = self.doit(2)
        def _check(errput):
            # there should be no stderr open, so nothing for it to
            # write the error to.
            self.failUnlessEqual(errput, '')
        d.addCallback(_check)
        return d


skipMessage = "wrong platform or reactor doesn't support IReactorProcess"
if (runtime.platform.getType() != 'posix') or (not interfaces.IReactorProcess(reactor, None)):
    PosixProcessTestCase.skip = skipMessage
    PosixProcessTestCasePTY.skip = skipMessage
    TestTwoProcessesPosix.skip = skipMessage
    FDTest.skip = skipMessage
else:
    # do this before running the tests: it uses SIGCHLD and stuff internally
    lsOut = popen2.popen3("/bin/ls ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")[2].read()

if (runtime.platform.getType() != 'win32') or (not interfaces.IReactorProcess(reactor, None)):
    Win32ProcessTestCase.skip = skipMessage
    TestTwoProcessesNonPosix.skip = skipMessage

if runtime.platform.getType() == 'win32':
    UtilTestCase.todo = "do not assume that platform retains 'executable' mode"

if not interfaces.IReactorProcess(reactor, None):
    ProcessTestCase.skip = skipMessage
    ClosingPipes.skip = skipMessage
