
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

from pyunit import unittest

import cStringIO, gzip, os, popen2, time, sys

# Twisted Imports
from twisted.internet import reactor
from twisted.protocols import protocol
from twisted.python import util, runtime

class TestProcessProtocol(protocol.ProcessProtocol):

    finished = 0
    
    def connectionMade(self):
        self.stages = [1]
        self.data = ''
        self.err = ''
        self.transport.write("abcd")

    def dataReceived(self, data):
        self.data = self.data + data

    def connectionLost(self):
        self.stages.append(2)
        if self.data != "abcd":
            raise RuntimeError
        self.transport.write("1234")

    def errReceived(self, data):
        self.err = self.err + data

    def errConnectionLost(self):
        self.stages.append(3)
        if self.err != "1234":
            raise RuntimeError
        self.transport.write("abcd")
        self.stages.append(4)

    def processEnded(self):
        self.finished = 1


class ProcessTestCase(unittest.TestCase):
    """Test running a process."""
    
    def testProcess(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_tester.py")
        p = TestProcessProtocol()
        reactor.spawnProcess(p, exe, ["python", "-u", scriptPath])
        while not p.finished:
            reactor.iterate()
        self.assertEquals(p.stages, [1, 2, 3, 4])


class Accumulator(protocol.ProcessProtocol):
    """Accumulate data from a process."""
    
    closed = 0
    
    def connectionMade(self):
        # print "connection made"
        self.outF = cStringIO.StringIO()
        self.errF = cStringIO.StringIO()

    def dataReceived(self, d):
        # print "data", repr(d)
        self.outF.write(d)

    def errReceived(self, d):
        # print "err", repr(d)
        self.errF.write(d)

    def connectionLost(self):
        # print "out closed"
        pass

    def errConnectionLost(self):
        # print "err closed"
        pass
    
    def processEnded(self):
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
            reactor.iterate()
        self.assertEquals(p.outF.getvalue(), "hello, worldabc123", p.errF.getvalue())
    
    def testProcess(self):
        if os.path.exists('/bin/gzip'): cmd = '/bin/gzip'
        elif os.path.exists('/usr/bin/gzip'): cmd = '/usr/bin/gzip'
        else: raise "gzip not found in /bin or /usr/bin"
        s = "there's no place like home!\n" * 3
	p = Accumulator()
        reactor.spawnProcess(p, cmd, [cmd, "-c"], {}, "/tmp")
        p.transport.write(s)
        # p.transport.loseConnection()
        p.transport.closeStdin()

        while not p.closed:
            reactor.iterate()
        f = p.outF
        f.seek(0, 0)
        gf = gzip.GzipFile(fileobj=f)
        self.assertEquals(gf.read(), s)
    
    def testStderr(self):
        # we assume there is no file named ZZXXX..., both in . and in /tmp
        if not os.path.exists('/bin/ls'): raise "/bin/ls not found"

	p = Accumulator()
        reactor.spawnProcess(p, '/bin/ls', ["/bin/ls", "ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"], {}, "/tmp")
        p.transport.loseConnection()
        while not p.closed:
            reactor.iterate()
        self.assertEquals(lsOut, p.errF.getvalue())
    


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

if runtime.platform.getType() != 'win32':
    del Win32ProcessTestCase
