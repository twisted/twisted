
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

from twisted.trial import unittest

# system imports
import os, shutil, time

# twisted imports
from twisted.python import logfile


class LogFileTestCase(unittest.TestCase):
    """Test the rotating log file."""
    
    def setUp(self):
        self.dir = self.mktemp()
        os.makedirs(self.dir)
        self.name = "test.log"
        self.path = os.path.join(self.dir, self.name)
    
    def tearDown(self):
        shutil.rmtree(self.dir)
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
        log.write("1" * 11)
        self.assert_(os.path.exists("%s.1" % self.path))
        self.assert_(not os.path.exists("%s.2" % self.path))
        log.write('')
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

        self.assertEquals(log.listLogs(), [1, 2, 3])
    
    def testAppend(self):
        log = logfile.LogFile(self.name, self.dir)
        log.write("0123456789")
        log.close()
        
        log = logfile.LogFile(self.name, self.dir)
        self.assertEquals(log.size, 10)
        self.assertEquals(log._file.tell(), log.size)
        log.write("abc")
        self.assertEquals(log.size, 13)
        self.assertEquals(log._file.tell(), log.size)
        f = log._file
        f.seek(0, 0)
        self.assertEquals(f.read(), "0123456789abc")
        log.close()

    def testLogReader(self):
        log = logfile.LogFile(self.name, self.dir)
        log.write("abc\n")
        log.write("def\n")
        log.rotate()
        log.write("ghi\n")
        log.flush()
        
        # check reading logs
        self.assertEquals(log.listLogs(), [1])
        reader = log.getCurrentLog()
        reader._file.seek(0)
        self.assertEquals(reader.readLines(), ["ghi\n"])
        self.assertEquals(reader.readLines(), [])
        reader.close()
        reader = log.getLog(1)
        self.assertEquals(reader.readLines(), ["abc\n", "def\n"])
        self.assertEquals(reader.readLines(), [])
        reader.close()
        
        # check getting illegal log readers
        self.assertRaises(ValueError, log.getLog, 2)
        self.assertRaises(TypeError, log.getLog, "1")

        # check that log numbers are higher for older logs
        log.rotate()
        self.assertEquals(log.listLogs(), [1, 2])
        reader = log.getLog(1)
        reader._file.seek(0)
        self.assertEquals(reader.readLines(), ["ghi\n"])
        self.assertEquals(reader.readLines(), [])
        reader.close()
        reader = log.getLog(2)
        self.assertEquals(reader.readLines(), ["abc\n", "def\n"])
        self.assertEquals(reader.readLines(), [])
        reader.close()

    def testModePreservation(self):
        "logfile: check rotated files have same permissions as original."
        if not hasattr(os, "chmod"): return
        f = open(self.path, "w").close()
        os.chmod(self.path, 0707)
        mode = os.stat(self.path)[0]
        log = logfile.LogFile(self.name, self.dir)
        log.write("abc")
        log.rotate()
        self.assertEquals(mode, os.stat(self.path)[0])

    def testNoPermission(self):
        "logfile: check it keeps working when permission on dir changes."
        log = logfile.LogFile(self.name, self.dir)
        log.write("abc")

        # change permissions so rotation would fail
        os.chmod(self.dir, 444)

        # if this succeeds, chmod doesn't restrict us, so we can't
        # do the test
        try:
            f = open(os.path.join(self.dir,"xxx"), "w")
        except (OSError, IOError):
            pass
        else:
            f.close()
            return
        
        log.rotate() # this should not fail

        log.write("def")
        log.flush()

        f = log._file
        self.assertEquals(f.tell(), 6)
        f.seek(0, 0)
        self.assertEquals(f.read(), "abcdef")
        log.close()

        # reset permission so tearDown won't fail
        os.chmod(self.dir, 0777)

        
class RiggedDailyLogFile(logfile.DailyLogFile):
    _clock = 0.0

    def _openFile(self):
        logfile.DailyLogFile._openFile(self)
        # rig the date to match _clock, not mtime
        self.lastDate = self.toDate()

    def toDate(self, *args):
        if args:
            return time.gmtime(*args)[:3]
        return time.gmtime(self._clock)[:3]

class DailyLogFileTestCase(unittest.TestCase):
    """Test the rotating log file."""
    
    def setUp(self):
        self.dir = self.mktemp()
        os.makedirs(self.dir)
        self.name = "testdaily.log"
        self.path = os.path.join(self.dir, self.name)
    
    def tearDown(self):
        shutil.rmtree(self.dir)
        pass
    
    def testWriting(self):
        log = RiggedDailyLogFile(self.name, self.dir)
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
        log = RiggedDailyLogFile(self.name, self.dir)
        days = [(self.path + '.' + log.suffix(day * 86400)) for day in range(3)]
        
        # test automatic rotation
        log._clock = 0.0    # 1970/01/01 00:00.00
        log.write("123")
        log._clock = 43200  # 1970/01/01 12:00.00
        log.write("4567890")
        log._clock = 86400  # 1970/01/02 00:00.00
        log.write("1" * 11)
        self.assert_(os.path.exists(days[0]))
        self.assert_(not os.path.exists(days[1]))
        log._clock = 172800 # 1970/01/03 00:00.00
        log.write('')
        self.assert_(os.path.exists(days[0]))
        self.assert_(os.path.exists(days[1]))
        self.assert_(not os.path.exists(days[2]))
        log._clock = 259199 # 1970/01/03 23:59.59
        log.write("3")
        self.assert_(not os.path.exists(days[2]))
