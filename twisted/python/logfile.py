# -*- test-case-name: twisted.test.test_logfile -*-

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
A rotating, browsable log file.
"""

# System Imports
import os, stat, glob, string

# sibling imports

import threadable

class BaseLogFile:
    """The base class for a log file that can be rotated.
    """

    synchronized = ["write", "rotate"]
    
    def __init__(self, name, directory, defaultMode=None):
        self.directory = os.path.realpath(directory)
        assert os.path.isdir(self.directory)
        self.name = name
        self.path = os.path.join(directory, name)
        if defaultMode is None and os.path.exists(self.path) and hasattr(os, "chmod"):
            self.defaultMode = os.stat(self.path)[0]
        else:
            self.defaultMode = None
        self._openFile()
    
    def shouldRotate(self):
        """Override with a method to that returns true if the log 
        should be rotated"""
        raise NotImplementedError

    def _openFile(self):
        """Open the log file."""
        self.closed = 0
        if os.path.exists(self.path):
            self._file = open(self.path, "r+")
            self._file.seek(0, 2)
        else:
            self._file = open(self.path, "w+")
        # set umask to be same as original log file
        if self.defaultMode is not None:
            os.chmod(self.path, self.defaultMode)
    
    def __getstate__(self):
        state = self.__dict__.copy()
        del state["_file"]
        return state
    
    def __setstate__(self, state):
        self.__dict__ = state
        self._openFile()
    
    def write(self, data):
        """Write some data to the file."""
        if self.shouldRotate():
            self.flush()
            self.rotate()
        self._file.write(data)
    
    def flush(self):
        """Flush the file."""
        self._file.flush()
    
    def close(self):
        """Close the file.
        
        The file cannot be used once it has been closed.
        """
        self.closed = 1
        self._file.close()
        self._file = None
    
    def getCurrentLog(self):
        """Return a LogReader for the current log file."""
        return LogReader(self.path)
    
class LogFile(BaseLogFile):
    """A log file that can be rotated.
    
    A rotateLength of None disables automatic log rotation.
    """
    def __init__(self, name, directory, rotateLength=1000000, defaultMode=None):
        BaseLogFile.__init__(self, name, directory, defaultMode)
        self.rotateLength = rotateLength

    def _openFile(self):
        BaseLogFile._openFile(self)
        self.size = self._file.tell()
        
    def shouldRotate(self):
        return self.rotateLength and self.size >= self.rotateLength

    def getLog(self, identifier):
        """Given an integer, return a LogReader for an old log file."""
        filename = "%s.%d" % (self.path, identifier)
        if not os.path.exists(filename):
            raise ValueError, "no such logfile exists"
        return LogReader(filename)

    def write(self, data):
        BaseLogFile.write(self, data)
        self.size += len(data)

    def rotate(self):
        """Rotate the file and create a new one.

        If it's not possible to open new logfile, this will fail silently,
        and continue logging to old logfile.
        """
        if not (os.access(self.directory, os.W_OK) and os.access(self.path, os.W_OK)):
            return
        logs = self.listLogs()
        logs.reverse()
        for i in logs:
            os.rename("%s.%d" % (self.path, i), "%s.%d" % (self.path, i + 1))
        self._file.close()
        os.rename(self.path, "%s.1" % self.path)
        self._openFile()

    def listLogs(self):
        """Return sorted list of integers - the old logs' identifiers."""
        result = []
        for name in glob.glob("%s.*" % self.path):
            try:
                counter = int(string.split(name, '.')[-1])
                if counter:
                    result.append(counter)
            except ValueError:
                pass
        result.sort()
        return result

    def __getstate__(self):
        state = LogFile.__getstate__(self)
        del state["size"]
        return state

threadable.synchronize(LogFile)
  
class LogReader:
    """Read from a log file."""
    
    def __init__(self, name):
        self._file = open(name, "r")
    
    def readLines(self, lines=10):
        """Read a list of lines from the log file.
        
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
