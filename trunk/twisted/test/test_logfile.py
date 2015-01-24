# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import os, time, stat, errno

from twisted.trial import unittest
from twisted.python import logfile, runtime


class LogFileTestCase(unittest.TestCase):
    """
    Test the rotating log file.
    """

    def setUp(self):
        self.dir = self.mktemp()
        os.makedirs(self.dir)
        self.name = "test.log"
        self.path = os.path.join(self.dir, self.name)


    def tearDown(self):
        """
        Restore back write rights on created paths: if tests modified the
        rights, that will allow the paths to be removed easily afterwards.
        """
        os.chmod(self.dir, 0777)
        if os.path.exists(self.path):
            os.chmod(self.path, 0777)


    def testWriting(self):
        log = logfile.LogFile(self.name, self.dir)
        log.write("123")
        log.write("456")
        log.flush()
        log.write("7890")
        log.close()

        f = open(self.path, "r")
        self.assertEqual(f.read(), "1234567890")
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

        self.assertEqual(log.listLogs(), [1, 2, 3])

    def testAppend(self):
        log = logfile.LogFile(self.name, self.dir)
        log.write("0123456789")
        log.close()

        log = logfile.LogFile(self.name, self.dir)
        self.assertEqual(log.size, 10)
        self.assertEqual(log._file.tell(), log.size)
        log.write("abc")
        self.assertEqual(log.size, 13)
        self.assertEqual(log._file.tell(), log.size)
        f = log._file
        f.seek(0, 0)
        self.assertEqual(f.read(), "0123456789abc")
        log.close()

    def testLogReader(self):
        log = logfile.LogFile(self.name, self.dir)
        log.write("abc\n")
        log.write("def\n")
        log.rotate()
        log.write("ghi\n")
        log.flush()

        # check reading logs
        self.assertEqual(log.listLogs(), [1])
        reader = log.getCurrentLog()
        reader._file.seek(0)
        self.assertEqual(reader.readLines(), ["ghi\n"])
        self.assertEqual(reader.readLines(), [])
        reader.close()
        reader = log.getLog(1)
        self.assertEqual(reader.readLines(), ["abc\n", "def\n"])
        self.assertEqual(reader.readLines(), [])
        reader.close()

        # check getting illegal log readers
        self.assertRaises(ValueError, log.getLog, 2)
        self.assertRaises(TypeError, log.getLog, "1")

        # check that log numbers are higher for older logs
        log.rotate()
        self.assertEqual(log.listLogs(), [1, 2])
        reader = log.getLog(1)
        reader._file.seek(0)
        self.assertEqual(reader.readLines(), ["ghi\n"])
        self.assertEqual(reader.readLines(), [])
        reader.close()
        reader = log.getLog(2)
        self.assertEqual(reader.readLines(), ["abc\n", "def\n"])
        self.assertEqual(reader.readLines(), [])
        reader.close()

    def testModePreservation(self):
        """
        Check rotated files have same permissions as original.
        """
        f = open(self.path, "w").close()
        os.chmod(self.path, 0707)
        mode = os.stat(self.path)[stat.ST_MODE]
        log = logfile.LogFile(self.name, self.dir)
        log.write("abc")
        log.rotate()
        self.assertEqual(mode, os.stat(self.path)[stat.ST_MODE])


    def test_noPermission(self):
        """
        Check it keeps working when permission on dir changes.
        """
        log = logfile.LogFile(self.name, self.dir)
        log.write("abc")

        # change permissions so rotation would fail
        os.chmod(self.dir, 0555)

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
        self.assertEqual(f.tell(), 6)
        f.seek(0, 0)
        self.assertEqual(f.read(), "abcdef")
        log.close()


    def test_maxNumberOfLog(self):
        """
        Test it respect the limit on the number of files when maxRotatedFiles
        is not None.
        """
        log = logfile.LogFile(self.name, self.dir, rotateLength=10,
                              maxRotatedFiles=3)
        log.write("1" * 11)
        log.write("2" * 11)
        self.failUnless(os.path.exists("%s.1" % self.path))

        log.write("3" * 11)
        self.failUnless(os.path.exists("%s.2" % self.path))

        log.write("4" * 11)
        self.failUnless(os.path.exists("%s.3" % self.path))
        self.assertEqual(file("%s.3" % self.path).read(), "1" * 11)

        log.write("5" * 11)
        self.assertEqual(file("%s.3" % self.path).read(), "2" * 11)
        self.failUnless(not os.path.exists("%s.4" % self.path))

    def test_fromFullPath(self):
        """
        Test the fromFullPath method.
        """
        log1 = logfile.LogFile(self.name, self.dir, 10, defaultMode=0777)
        log2 = logfile.LogFile.fromFullPath(self.path, 10, defaultMode=0777)
        self.assertEqual(log1.name, log2.name)
        self.assertEqual(os.path.abspath(log1.path), log2.path)
        self.assertEqual(log1.rotateLength, log2.rotateLength)
        self.assertEqual(log1.defaultMode, log2.defaultMode)

    def test_defaultPermissions(self):
        """
        Test the default permission of the log file: if the file exist, it
        should keep the permission.
        """
        f = file(self.path, "w")
        os.chmod(self.path, 0707)
        currentMode = stat.S_IMODE(os.stat(self.path)[stat.ST_MODE])
        f.close()
        log1 = logfile.LogFile(self.name, self.dir)
        self.assertEqual(stat.S_IMODE(os.stat(self.path)[stat.ST_MODE]),
                          currentMode)


    def test_specifiedPermissions(self):
        """
        Test specifying the permissions used on the log file.
        """
        log1 = logfile.LogFile(self.name, self.dir, defaultMode=0066)
        mode = stat.S_IMODE(os.stat(self.path)[stat.ST_MODE])
        if runtime.platform.isWindows():
            # The only thing we can get here is global read-only
            self.assertEqual(mode, 0444)
        else:
            self.assertEqual(mode, 0066)


    def test_reopen(self):
        """
        L{logfile.LogFile.reopen} allows to rename the currently used file and
        make L{logfile.LogFile} create a new file.
        """
        log1 = logfile.LogFile(self.name, self.dir)
        log1.write("hello1")
        savePath = os.path.join(self.dir, "save.log")
        os.rename(self.path, savePath)
        log1.reopen()
        log1.write("hello2")
        log1.close()

        f = open(self.path, "r")
        self.assertEqual(f.read(), "hello2")
        f.close()
        f = open(savePath, "r")
        self.assertEqual(f.read(), "hello1")
        f.close()

    if runtime.platform.isWindows():
        test_reopen.skip = "Can't test reopen on Windows"


    def test_nonExistentDir(self):
        """
        Specifying an invalid directory to L{LogFile} raises C{IOError}.
        """
        e = self.assertRaises(
            IOError, logfile.LogFile, self.name, 'this_dir_does_not_exist')
        self.assertEqual(e.errno, errno.ENOENT)



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
    """
    Test rotating log file.
    """

    def setUp(self):
        self.dir = self.mktemp()
        os.makedirs(self.dir)
        self.name = "testdaily.log"
        self.path = os.path.join(self.dir, self.name)


    def testWriting(self):
        log = RiggedDailyLogFile(self.name, self.dir)
        log.write("123")
        log.write("456")
        log.flush()
        log.write("7890")
        log.close()

        f = open(self.path, "r")
        self.assertEqual(f.read(), "1234567890")
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

