
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

    def testStdio(self):
        """twisted.internet.stdio test."""
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_twisted.py")
        p = Accumulator()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], None, None)
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
        reactor.spawnProcess(p, cmd, [cmd, "-c"], {}, "/tmp")
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
        reactor.spawnProcess(p, '/bin/ls', ["/bin/ls", "ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"], {}, "/tmp")

        while not p.closed:
            reactor.iterate(0.01)
        self.assertEquals(lsOut, p.errF.getvalue())
    

    def testNormalTermination(self):
        if os.path.exists('/bin/true'): cmd = '/bin/true'
        elif os.path.exists('/usr/bin/true'): cmd = '/usr/bin/true'
        else: raise RuntimeError("true not found in /bin or /usr/bin")

        p = TrivialProcessProtocol()
        reactor.spawnProcess(p, cmd, ['true'])

        while not p.finished:
            reactor.iterate(0.01)
        p.reason.trap(error.ProcessDone)
        self.assertEquals(p.reason.value.exitCode, 0)


    def testAbnormalTermination(self):
        if os.path.exists('/bin/false'): cmd = '/bin/false'
        elif os.path.exists('/usr/bin/false'): cmd = '/usr/bin/false'
        else: raise RuntimeError("false not found in /bin or /usr/bin")
        
        p = TrivialProcessProtocol()
        reactor.spawnProcess(p, cmd, ['false'])

        while not p.finished:
            reactor.iterate(0.01)
        p.reason.trap(error.ProcessTerminated)
        self.assertEquals(p.reason.value.exitCode, 1)


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
else:
    lsOut = popen2.popen3("/bin/ls ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")[2].read()
    # make sure SIGCHILD handler is installed, as it should be on reactor.run().
    # problem is reactor may not have been run when this test runs.
    import signal
    from twisted.internet import process
    signal.signal(signal.SIGCHLD, process.reapAllProcesses)

if runtime.platform.getType() != 'win32':
    del Win32ProcessTestCase
else:
    def testEcho(self): raise RuntimeError, "this test is disabled since it goes into infinite loop on windows :("
    ProcessTestCase.testEcho = testEcho
