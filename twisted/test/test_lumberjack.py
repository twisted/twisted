
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

from pyunit import unittest

# system imports
import os, tempfile

# twisted imports
from twisted.lumberjack import logfile


class LogFileTestCase(unittest.TestCase):
    """Test the rotating log file."""
    
    def setUp(self):
        self.dir = tempfile.mktemp()
        os.makedirs(self.dir)
        self.name = "test.log"
        self.path = os.path.join(self.dir, self.name)
    
    def tearDown(self):
        #shutil.rmtree(self.dir)
        pass
    
    def testWriting(self):
        log = logfile.LogFile(self.name, self.dir)
        log.write("123")
        log.write("456")
        log.flush()
        log.write("7890")
        log.close()
        
        f = open(self.path, "r")
        self.assertEquals(f.read(), "1234567890")
        f.close()
    
    def testRotation(self):
        # this logfile should rotate every 10 bytes
        log = logfile.LogFile(self.name, self.dir, rotateLength=10)
        
        # test automatic rotation
        log.write("123")
        log.write("4567890")
        self.assert_(os.path.exists("%s.1" % self.path))
        self.assert_(not os.path.exists("%s.2" % self.path))
        log.write("1" * 11)
        self.assert_(os.path.exists("%s.1" % self.path))
        self.assert_(os.path.exists("%s.2" % self.path))
        self.assert_(not os.path.exists("%s.3" % self.path))
        log.write("3")
        self.assert_(not os.path.exists("%s.3" % self.path))
        
        # test manual rotation
        log.rotate()
        self.assert_(os.path.exists("%s.3" % self.path))
        self.assert_(not os.path.exists("%s.4" % self.path))
        log.close()
