
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

import gzip, os, popen2, time, sys

# Twisted Imports
from twisted.internet import reactor, utils, interfaces
from twisted.python import components


class UtilsTestCase(unittest.TestCase):
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


if not components.implements(reactor, interfaces.IReactorProcess):
    UtilsTestCase.skip = "reactor doesn't implement IReactorProcess"
