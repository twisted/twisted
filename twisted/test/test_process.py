
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
from twisted.internet import process, main
from twisted.python import util, runtime

s = "there's no place like home!\n" * 3


class PosixProcessTestCase(unittest.TestCase):
    """Test running processes."""
    
    def testProcess(self):
        f = cStringIO.StringIO()
        p = process.Process("/bin/gzip", ["/bin/gzip", "-"], {}, "/tmp")
        p.handleChunk = f.write
        p.write(s)
        p.closeStdin()
        while hasattr(p, 'writer'):
            main.iterate()
        f.seek(0, 0)
        gf = gzip.GzipFile(fileobj=f)
        self.assertEquals(gf.read(), s)
    
    def testStderr(self):
        # we assume there is no file named ZZXXX..., both in . and in /tmp
        err = popen2.popen3("/bin/ls ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")[2].read()
        f = cStringIO.StringIO()
        p = process.Process('/bin/ls', ["/bin/ls", "ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"], {}, "/tmp")
        p.handleError = f.write
        p.closeStdin()
        while hasattr(p, 'writer'):
            main.iterate()
        self.assertEquals(err, f.getvalue())
    
    def testPopen(self):
        """Make sure popen isn't broken by our signal handlers."""
        main.handleSignals() # install signal handlers
        for i in range(20):
            f = os.popen("/bin/gzip --help")
            f.read()
            f.close()


class Win32ProcessTestCase(unittest.TestCase):
    """Test process programs that are packaged with twisted."""
    
    def testStdinReader(self):
        import win32api
        pyExe = win32api.GetModuleFileName(0)
        errF = cStringIO.StringIO()
        outF = cStringIO.StringIO()
        scriptPath = util.sibpath(__file__, "process_stdinreader.py")
        p = process.Process(pyExe, [pyExe, "-u", scriptPath], None, None)
        p.handleError = errF.write
        p.handleChunk = outF.write
        main.iterate()
        
        p.write("hello, world")
        p.closeStdin()
        while not p.closed:
            main.iterate()
        self.assertEquals(errF.getvalue(), "err\nerr\n")
        self.assertEquals(outF.getvalue(), "out\nhello, world\nout\n")


if runtime.platform.getType() != 'posix':
    del PosixProcessTestCase
elif runtime.platform.getType() != 'win32':
    del Win32ProcessTestCase
