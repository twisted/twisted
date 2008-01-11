# -*- test-case-name: twisted.test.test_logfile -*-

# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A rotating, browsable log file.
"""

# System Imports
import os, glob, time, stat

try:
    from gzip import GzipFile
except ImportError:
    GzipFile = None

try:
    from bz2 import BZ2File
except ImportError:
    BZ2File = None

from twisted.python import threadable



class LogReader:
    """
    Read from a log file.
    """

    def __init__(self, name):
        self._file = file(name, "r")


    def readLines(self, lines=10):
        """
        Read a list of lines from the log file.

        This doesn't returns all of the files lines - call it multiple times.
        """
        result = []
        for i in range(lines):
            line = self._file.readline()
            if not line:
                break
            result.append(line)
        return result


    def close(self):
        self._file.close()



class GzipLogReader(LogReader):
    """
    Read from a gzip compressed log file.
    """

    def __init__(self, name):
        self._file = GzipFile(name, "r")



class Bz2LogReader(LogReader):
    """
    Read from a bz2 compressed log file.
    """

    def __init__(self, name):
        self._file = BZ2File(name, "r")



class BaseLogFile:
    """
    The base class for a log file that can be rotated.
    """

    synchronized = ["write", "rotate"]

    def __init__(self, name, directory, defaultMode=None):
        """
        Create a log file.

        @param name: name of the file
        @type name: C{str}

        @param directory: directory holding the file
        @type directory: C{str}

        @param defaultMode: permissions used to create the file. Default to
            current permissions of the file if the file exists.
        @type defaultMode: C{int}
        """
        self.directory = directory
        assert os.path.isdir(self.directory)
        self.name = name
        self.path = os.path.join(directory, name)
        if defaultMode is None and os.path.exists(self.path):
            self.defaultMode = stat.S_IMODE(os.stat(self.path)[stat.ST_MODE])
        else:
            self.defaultMode = defaultMode
        self._openFile()


    def fromFullPath(cls, filename, *args, **kwargs):
        """
        Construct a log file from a full file path.
        """
        logPath = os.path.abspath(filename)
        return cls(os.path.basename(logPath),
                   os.path.dirname(logPath), *args, **kwargs)

    fromFullPath = classmethod(fromFullPath)


    def shouldRotate(self):
        """
        Override with a method to that returns true if the log
        should be rotated.
        """
        raise NotImplementedError()


    def _isAccessible(self):
        """
        Helper method to check if path is accessible.
        """
        return (os.access(self.directory, os.W_OK) and
                os.access(self.path, os.W_OK))


    def _openFile(self):
        """
        Open the log file.
        """
        self.closed = False
        if os.path.exists(self.path):
            self._file = file(self.path, "r+", 1)
            self._file.seek(0, 2)
        else:
            if self.defaultMode is not None:
                # Set the lowest permissions
                oldUmask = os.umask(0777)
                try:
                    self._file = file(self.path, "w+", 1)
                finally:
                    os.umask(oldUmask)
            else:
                self._file = file(self.path, "w+", 1)
        if self.defaultMode is not None:
            try:
                os.chmod(self.path, self.defaultMode)
            except OSError:
                # Probably /dev/null or something?
                pass


    def __getstate__(self):
        state = self.__dict__.copy()
        del state["_file"]
        return state


    def __setstate__(self, state):
        self.__dict__ = state
        self._openFile()


    def write(self, data):
        """
        Write some data to the file.
        """
        if self.shouldRotate():
            self.flush()
            self.rotate()
        self._file.write(data)


    def flush(self):
        """
        Flush the file.
        """
        self._file.flush()


    def close(self):
        """
        Close the file.

        The file cannot be used once it has been closed.
        """
        self.closed = True
        self._file.close()
        self._file = None


    def getCurrentLog(self):
        """
        Return a LogReader for the current log file.
        """
        return LogReader(self.path)



class LogFile(BaseLogFile):
    """
    A log file that can be rotated.

    A rotateLength of None disables automatic log rotation.

    @cvar logReaderFactory: factory for log readers.
    @type logReaderFactory: C{class}

    @cvar rotateExtension: the extension appended to rotated files.
    @type rotateExtension: C{str}

    @cvar counterIndex: the index in the log name where the counter is located,
        when the name is splitted with "."
    @type counterIndex: C{int}
    """
    logReaderFactory = LogReader
    rotateExtension = ""
    counterIndex = -1

    def __init__(self, name, directory, rotateLength=1000000, defaultMode=None,
                 maxRotatedFiles=None):
        """
        Create a log file rotating on length.

        @param name: file name.
        @type name: C{str}
        @param directory: path of the log file.
        @type directory: C{str}
        @param rotateLength: size of the log file where it rotates. Default to
            1M.
        @type rotateLength: C{int}
        @param defaultMode: mode used to create the file.
        @type defaultMode: C{int}
        @param maxRotatedFiles: if not None, max number of log files the class
            creates. Warning: it removes all log files above this number.
        @type maxRotatedFiles: C{int}
        """
        BaseLogFile.__init__(self, name, directory, defaultMode)
        self.rotateLength = rotateLength
        self.maxRotatedFiles = maxRotatedFiles


    def _openFile(self):
        BaseLogFile._openFile(self)
        self.size = self._file.tell()


    def shouldRotate(self):
        """
        Rotate when the log file size is larger than rotateLength.
        """
        return self.rotateLength and self.size >= self.rotateLength


    def getLog(self, identifier):
        """
        Given an integer, return a LogReader for an old log file.
        """
        filename = "%s.%d%s" % (self.path, identifier, self.rotateExtension)
        if not os.path.exists(filename):
            raise ValueError("no such logfile exists")
        return self.logReaderFactory(filename)


    def write(self, data):
        """
        Write some data to the file.
        """
        BaseLogFile.write(self, data)
        self.size += len(data)


    def rotate(self):
        """
        Rotate the file and create a new one.

        If it's not possible to open new logfile, this will fail silently, and
        continue logging to old logfile.

        @return: the name of the archived log file, or C{None} if it didn't
            manage to rotate.
        @rtype: C{str} or C{NoneType}
        """
        if not self._isAccessible():
            return
        logs = self.listLogs()
        logs.reverse()
        for i in logs:
            extension = "%d%s" % (i, self.rotateExtension)
            if self.maxRotatedFiles is not None and i >= self.maxRotatedFiles:
                os.remove("%s.%s" % (self.path, extension))
            else:
                newExtension = "%d%s" % (i + 1, self.rotateExtension)
                os.rename("%s.%s" % (self.path, extension),
                          "%s.%s" % (self.path, newExtension))
        self._file.close()
        newPath = "%s.1" % (self.path,)
        os.rename(self.path, newPath)
        self._openFile()
        return newPath


    def listLogs(self):
        """
        Return sorted list of integers - the old logs' identifiers.
        """
        result = []
        for name in glob.glob("%s.*" % self.path):
            try:
                counter = int(name.split('.')[self.counterIndex])
                if counter:
                    result.append(counter)
            except ValueError:
                pass
        result.sort()
        return result


    def __getstate__(self):
        state = BaseLogFile.__getstate__(self)
        del state["size"]
        return state

threadable.synchronize(LogFile)



def CompressorHelper(baseClass, compressorClass):
    """
    A helper to compress log files.

    @param baseClass: parent class writing to the log file. It should provide a
        C{rotate} method.
    @type baseClass: C{class}

    @param compressorClass: class offering a file-like interface to create
        compressed files.
    @type compressorClass: C{class}

    @return: a child class of C{baseClass} with compressing facility.
    @rtype: C{class}
    """

    def __init__(self, *args, **kwargs):
        """
        @param callInThread: callable that executes the compression outside the
            main loop. You'll generally want to pass
            L{twisted.internet.reactor.callInThread}.
        @type callInThread: C{callable}
        """
        self.callInThread = kwargs.pop("callInThread")
        baseClass.__init__(self, *args, **kwargs)


    def rotate(self):
        """
        Do the rotation and compress the rotated log file.
        """
        newPath = baseClass.rotate(self)
        if newPath is None:
            return
        self.callInThread(self._compress, newPath)
        return newPath


    def _compress(self, path, chunkSize=8192):
        """
        Compress logfile. Warning, this is a blocking method.

        @param path: the file to compress.
        @type path: C{str}

        @param chunkSize: size of a chunk read on the file to compress, in
            bytes.
        @type: chunkSize: C{int}
        """
        compressedFile = compressorClass("%s%s" %
            (path, self.rotateExtension), "wb")
        newfp = open(path)

        data = newfp.read(chunkSize)
        compressedFile.write(data)
        while len(data) == chunkSize:
            data = newfp.read(chunkSize)
            compressedFile.write(data)

        compressedFile.close()
        newfp.close()
        os.remove(path)

    compressor = type("CompressorHelper", (baseClass, object),
            {"rotate": rotate, "_compress": _compress,
             "__init__": __init__})
    return compressor



class GzipLogFile(CompressorHelper(LogFile, GzipFile)):
    """
    A gzip compressed log file.
    """
    logReaderFactory = GzipLogReader
    counterIndex = -2
    rotateExtension = ".gz"



class Bz2LogFile(CompressorHelper(LogFile, BZ2File)):
    """
    A bz2 compressed log file.
    """
    logReaderFactory = Bz2LogReader
    counterIndex = -2
    rotateExtension = ".bz2"



class DailyLogFile(BaseLogFile):
    """
    A log file that is rotated daily (at or after midnight localtime).

    @cvar logReaderFactory: factory for log readers.
    @type logReaderFactory: C{class}

    @cvar rotateExtension: the extension appended to rotated files.
    @type rotateExtension: C{str}
    """
    logReaderFactory = LogReader
    rotateExtension = ""

    def _openFile(self):
        BaseLogFile._openFile(self)
        self.lastDate = self.toDate(os.stat(self.path)[8])


    def shouldRotate(self):
        """
        Rotate when the date has changed since last write.
        """
        return self.toDate() > self.lastDate


    def toDate(self, *args):
        """
        Convert a unixtime to (year, month, day) localtime tuple, or return the
        current (year, month, day) localtime tuple.

        This function primarily exists so you may overload it with gmtime, or
        some cruft to make unit testing possible.
        """
        # primarily so this can be unit tested easily
        return time.localtime(*args)[:3]


    def suffix(self, tupledate):
        """
        Return the suffix given a (year, month, day) tuple or unixtime.
        """
        try:
            return '_'.join(map(str, tupledate))
        except TypeError:
            # try taking a float unixtime
            return '_'.join(map(str, self.toDate(tupledate)))


    def getLog(self, identifier):
        """
        Given a unix time, return a LogReader for an old log file.
        """
        if self.toDate(identifier) == self.lastDate:
            return self.getCurrentLog()
        filename = "%s.%s%s" % (self.path, self.suffix(identifier),
                                self.rotateExtension)
        if not os.path.exists(filename):
            raise ValueError("no such logfile exists")
        return self.logReaderFactory(filename)


    def write(self, data):
        """
        Write some data to the log file.
        """
        BaseLogFile.write(self, data)
        # Guard against a corner case where time.time()
        # could potentially run backwards to yesterday.
        # Primarily due to network time.
        self.lastDate = max(self.lastDate, self.toDate())


    def rotate(self):
        """
        Rotate the file and create a new one.

        If it's not possible to open new logfile, this will fail silently, and
        continue logging to old logfile.

        @return: the name of the archived log file, or C{None} if it didn't
            manage to rotate.
        @rtype: C{str} or C{NoneType}
        """
        if not self._isAccessible():
            return
        newPath = "%s.%s" % (self.path, self.suffix(self.lastDate))
        if os.path.exists(newPath):
            return
        self._file.close()
        os.rename(self.path, newPath)
        self._openFile()
        return newPath


    def __getstate__(self):
        state = BaseLogFile.__getstate__(self)
        del state["lastDate"]
        return state

threadable.synchronize(DailyLogFile)



class GzipDailyLogFile(CompressorHelper(DailyLogFile, GzipFile)):
    """
    A gzip compressed dailylog file.
    """
    logReaderFactory = GzipLogReader
    rotateExtension = ".gz"



class Bz2DailyLogFile(CompressorHelper(DailyLogFile, BZ2File)):
    """
    A bz2 compressed dailylog file.
    """
    logReaderFactory = Bz2LogReader
    rotateExtension = ".bz2"

