# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{logfile}.
"""

import os, shutil, time, stat

try:
    import gzip
except ImportError:
    gzip = None

try:
    import bz2
except ImportError:
    bz2 = None

from twisted.trial.unittest import TestCase

from twisted.python import logfile, runtime
from twisted.internet.threads import deferToThread



class FileExistsTestCase(TestCase):
    """
    A TestCase with 2 methods to test the existence of files.
    """

    def assertExists(self, path):
        """
        Check if given path exists.
        """
        return self.assertTrue(os.path.exists(path), "%s doesn't exist" % (path,))


    def assertNotExists(self, path):
        """
        Check if given path doesn't exist.
        """
        return self.assertFalse(os.path.exists(path), "%s exists" % (path,))



class LogFileTestCase(FileExistsTestCase):
    """
    Test the rotating log file.
    """
    logFileFactory = logfile.LogFile
    extension = ""

    def setUp(self):
        self.dir = self.mktemp()
        os.makedirs(self.dir)
        self.name = "test.log"
        self.path = os.path.join(self.dir, self.name)


    def tearDown(self):
        # Restore back write rights if necessary
        os.chmod(self.path, 0666)
        shutil.rmtree(self.dir)


    def test_writing(self):
        """
        Check that the write method of the logfile write data on the
        filesystem.
        """
        log = self.logFileFactory(self.name, self.dir)
        log.write("123")
        log.write("456")
        log.flush()
        log.write("7890")
        log.close()

        f = open(self.path, "r")
        self.assertEquals(f.read(), "1234567890")
        f.close()


    def test_rotation(self):
        """
        Test rotation of log files: it should rotate when expected, and keep
        the data in the good log files.
        """
        # this logfile should rotate every 10 bytes
        log = self.logFileFactory(self.name, self.dir, rotateLength=10)

        # test automatic rotation
        log.write("123")
        log.write("4567890")
        log.write("1" * 11)
        self.assertExists("%s.1%s" % (self.path, self.extension))
        self.assertEquals(log.getLog(1).readLines(), ['1234567890'])
        self.assertNotExists("%s.2%s" % (self.path, self.extension))
        log.write('')
        self.assertExists("%s.1%s" % (self.path, self.extension))
        self.assertExists("%s.2%s" % (self.path, self.extension))
        self.assertEquals(log.getLog(1).readLines(), ['1' * 11])
        self.assertNotExists("%s.3%s" % (self.path, self.extension))
        log.write("3")
        self.assertNotExists("%s.3%s" % (self.path, self.extension))

        # test manual rotation
        log.rotate()
        self.assertExists("%s.3%s" % (self.path, self.extension))
        self.assertNotExists("%s.4%s" % (self.path, self.extension))
        log.close()

        self.assertEquals(log.listLogs(), [1, 2, 3])


    def test_reopen(self):
        """
        Open a logfile, write to it, close it, reopen it, and check that it
        didn't remove previous data.
        """
        log = self.logFileFactory(self.name, self.dir)
 
        log.write("1234567890")
        log.close()
        self.assertTrue(log.closed)

        log = self.logFileFactory(self.name, self.dir)
        log.write("1" * 11)
        log.flush()
        self.assertEquals(log.getCurrentLog().readLines(), ["1234567890" + "1" * 11])

        log.rotate()
        self.assertEquals(log.getLog(1).readLines(), ["1234567890" + "1" * 11])


    def test_append(self):
        log = self.logFileFactory(self.name, self.dir)
        log.write("0123456789")
        log.close()

        log = self.logFileFactory(self.name, self.dir)
        self.assertEquals(log.size, 10)
        self.assertEquals(log._file.tell(), log.size)
        log.write("abc")
        self.assertEquals(log.size, 13)
        self.assertEquals(log._file.tell(), log.size)
        f = log._file
        f.seek(0, 0)
        self.assertEquals(f.read(), "0123456789abc")
        log.close()


    def test_logReader(self):
        log = self.logFileFactory(self.name, self.dir)
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


    def test_modePreservation(self):
        """
        Check rotated files have same permissions as original.
        """
        f = open(self.path, "w").close()
        os.chmod(self.path, 0707)
        mode = os.stat(self.path)[stat.ST_MODE]
        log = self.logFileFactory(self.name, self.dir)
        log.write("abc")
        log.rotate()
        self.assertEquals(mode, os.stat(self.path)[stat.ST_MODE])


    def test_noPermission(self):
        """
        Check it keeps working when permission on dir changes.
        """
        log = self.logFileFactory(self.name, self.dir)
        log.write("abc")

        # change permissions so rotation would fail
        os.chmod(self.dir, 0444)

        try:
            # if this succeeds, chmod doesn't restrict us, so we can't
            # do the test
            try:
                f = open(os.path.join(self.dir, "xxx"), "w")
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

        finally:
            # reset permission so tearDown won't fail, regardless of if an
            # assertion was raised.
            os.chmod(self.dir, 0777)


    def test_maxNumberOfLog(self):
        """
        Test it respect the limit on the number of files when maxRotatedFiles
        is not None.
        """
        log = self.logFileFactory(self.name, self.dir, rotateLength=10,
                              maxRotatedFiles=3)
        log.write("1" * 11)
        log.write("2" * 11)
        self.assertExists("%s.1%s" % (self.path, self.extension))

        log.write("3" * 11)
        self.assertExists("%s.2%s" % (self.path, self.extension))

        log.write("4" * 11)
        self.assertExists("%s.3%s" % (self.path, self.extension))
        self.assertEquals(log.getLog(3).readLines(), ["1" * 11])

        log.write("5" * 11)
        self.assertEquals(log.getLog(3).readLines(), ["2" * 11])
        self.assertNotExists("%s.4%s" % (self.path, self.extension))


    def test_fromFullPath(self):
        """
        Test the fromFullPath method.
        """
        log1 = self.logFileFactory(self.name, self.dir, 10, defaultMode=0777)
        log2 = self.logFileFactory.fromFullPath(self.path, 10, defaultMode=0777)
        self.assertEquals(log1.name, log2.name)
        self.assertEquals(os.path.abspath(log1.path), log2.path)
        self.assertEquals(log1.rotateLength, log2.rotateLength)
        self.assertEquals(log1.defaultMode, log2.defaultMode)


    def test_defaultPermissions(self):
        """
        Test the default permission of the log file: if the file exists, it
        should keep the permission.
        """
        f = file(self.path, "w")
        os.chmod(self.path, 0707)
        currentMode = stat.S_IMODE(os.stat(self.path)[stat.ST_MODE])
        f.close()
        log1 = self.logFileFactory(self.name, self.dir)
        self.assertEquals(stat.S_IMODE(os.stat(self.path)[stat.ST_MODE]),
                          currentMode)


    def test_specifiedPermissions(self):
        """
        Test specifying the permissions used on the log file.
        """
        log1 = self.logFileFactory(self.name, self.dir, defaultMode=0066)
        mode = stat.S_IMODE(os.stat(self.path)[stat.ST_MODE])
        if runtime.platform.isWindows():
            # The only thing we can get here is global read-only
            self.assertEquals(mode, 0444)
        else:
            self.assertEquals(mode, 0066)



class TestableGzipLogFile(logfile.GzipLogFile):
    """
    A gzip compressed log file that can be tested.
    """

    def callInThread(self, method, *args, **kwargs):
        """
        Do not call in thread, call synchronously instead.
        """
        return method(*args, **kwargs)



class TestableWithThreadsGzipLogFile(logfile.GzipLogFile):
    """
    A gzip compressed log file that can be tested, with threads.
    """

    def __init__(self, *args, **kwargs):
        logfile.GzipLogFile.__init__(self, *args, **kwargs)
        self.deferreds = []


    def callInThread(self, method, *args, **kwargs):
        """
        Use deferToThread to call C{method} in a thread, and store the
        resulting deferred.
        """
        d = deferToThread(method, *args, **kwargs)
        self.deferreds.append(d)



class GzipLogFileTestCase(LogFileTestCase):
    """
    Test the gzip-compressed rotating log file.
    """
    logFileFactory = TestableGzipLogFile
    extension = ".gz"

    def test_withThreads(self):
        """
        Check that L{logfile.GzipLogFile} has the same behavior with and
        withtout threads.
        """
        log = TestableWithThreadsGzipLogFile(self.name, self.dir,
                                             rotateLength=10)

        log.write("123")
        log.write("4567890")
        log.write("1" * 11)
        d = log.deferreds.pop(0)
        def check(ign):
            self.assertExists("%s.1%s" % (self.path, self.extension))
        d.addCallback(check)
        return d


    def test_errorReportInCompress(self):
        """
        Check that the L{logfile.GzipLogFile._compress} method reports errors
        using C{log.err}, but doesn't fail.
        """
        log = TestableWithThreadsGzipLogFile(self.name, self.dir,
                                             rotateLength=10)

        def fakeRemove(path):
            raise RuntimeError("Urg")
        self.patch(os, "remove", fakeRemove)

        log.write("123")
        log.write("4567890")
        log.write("1" * 11)
        d = log.deferreds.pop(0)
        def check(ign):
            errs = self.flushLoggedErrors()
            self.assertEquals(len(errs), 1)
            errs[0].trap(RuntimeError)
            self.assertEquals(str(errs[0].value), "Urg")
        d.addCallback(check)
        return d

if gzip is None:
    GzipLogFileTestCase.skip = "gzip not available"



class TestableBz2LogFile(logfile.Bz2LogFile):
    """
    A bz2 compressed log file that can be tested.
    """

    def callInThread(self, method, *args, **kwargs):
        """
        Do not call in thread, call synchronously instead.
        """
        return method(*args, **kwargs)



class Bz2LogFileTestCase(LogFileTestCase):
    """
    Test the bz2-compressed rotating log file.
    """
    logFileFactory = TestableBz2LogFile
    extension = ".bz2"

if bz2 is None:
    Bz2LogFileTestCase.skip = "bz2 not available"



def RiggedDailyLogFile(baseClass):
    _clock = 0.0

    def callInThread(self, method, *args, **kwargs):
        """
        Do not call in thread, call synchronously instead.
        """
        return method(*args, **kwargs)


    def _openFile(self):
        baseClass._openFile(self)
        # rig the date to match _clock, not mtime
        self.lastDate = self.toDate()


    def toDate(self, *args):
        if args:
            return time.gmtime(*args)[:3]
        return time.gmtime(self._clock)[:3]


    logFileClass = type("RiggedDailyLogFile", (baseClass, object),
            {"_openFile": _openFile, "toDate": toDate, "_clock": _clock,
             "callInThread": callInThread})
    return logFileClass



class DailyLogFileTestCase(FileExistsTestCase):
    """
    Test rotating log file.
    """
    logFileFactory = RiggedDailyLogFile(logfile.DailyLogFile)
    extension = ""

    def setUp(self):
        self.dir = self.mktemp()
        os.makedirs(self.dir)
        self.name = "testdaily.log"
        self.path = os.path.join(self.dir, self.name)


    def tearDown(self):
        shutil.rmtree(self.dir)


    def test_writing(self):
        log = self.logFileFactory(self.name, self.dir)
        log.write("123")
        log.write("456")
        log.flush()
        log.write("7890")
        log.close()

        f = open(self.path, "r")
        self.assertEquals(f.read(), "1234567890")
        f.close()


    def test_rotation(self):
        # this logfile should rotate every 10 bytes
        log = self.logFileFactory(self.name, self.dir)
        days = [(self.path + '.' + log.suffix(day * 86400)) for day in range(3)]

        # test automatic rotation
        log._clock = 0.0    # 1970/01/01 00:00.00
        log.write("123")
        log._clock = 43200  # 1970/01/01 12:00.00
        log.write("4567890")
        log._clock = 86400  # 1970/01/02 00:00.00
        log.write("1" * 11)
        self.assertExists(days[0] + self.extension)
        self.assertEquals(log.getLog(0).readLines(), ["1234567890"])
        self.assertNotExists(days[1] + self.extension)
        log._clock = 172800 # 1970/01/03 00:00.00
        log.write('')
        self.assertExists(days[0] + self.extension)
        self.assertEquals(log.getLog(0).readLines(), ["1234567890"])
        self.assertExists(days[1] + self.extension)
        self.assertEquals(log.getLog(86400).readLines(), ["1" * 11])
        self.assertNotExists(days[2] + self.extension)
        log._clock = 259199 # 1970/01/03 23:59.59
        log.write("3")
        self.assertNotExists(days[2] + self.extension)



class GzipDailyLogFileTestCase(DailyLogFileTestCase):
    """
    Test rotating a gzip log file.
    """
    logFileFactory = RiggedDailyLogFile(logfile.GzipDailyLogFile)
    extension = ".gz"

if gzip is None:
    GzipDailyLogFileTestCase.skip = "gzip not available"



class Bz2DailyLogFileTestCase(DailyLogFileTestCase):
    """
    Test rotating a bz2 log file.
    """
    logFileFactory = RiggedDailyLogFile(logfile.Bz2DailyLogFile)
    extension = ".bz2"

if bz2 is None:
    Bz2DailyLogFileTestCase.skip = "bz2 not available"

