
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


class LogFile:
    """A log file that can be rotated.
    
    A rotateLength of None disables automatic log rotation.
    """

    synchronized = ["write", "rotate"]
    
    def __init__(self, name, directory, rotateLength=1000000):
        self.directory = directory
        self.name = name
        self.path = os.path.join(directory, name)
        self.rotateLength = rotateLength
        if os.path.exists(self.path) and hasattr(os, "chmod"):
            self.defaultMode = os.stat(self.path)[0]
        else:
            self.defaultMode = None
        self._openFile()
    
    def _openFile(self):
        """Open the log file."""
        self.closed = 0
        if os.path.exists(self.path):
            self.size = os.stat(self.path)[stat.ST_SIZE]
            self._file = open(self.path, "r+")
            self._file.seek(0, 2)
        else:
            self.size = 0
            self._file = open(self.path, "w+")
        # set umask to be same as original log file
        if self.defaultMode is not None:
            os.chmod(self.path, self.defaultMode)
    
    def __getstate__(self):
        state = self.__dict__.copy()
        del state["size"]
        del state["_file"]
        return state
    
    def __setstate__(self, state):
        self.__dict__ = state
        self._openFile()
    
    def write(self, data):
        """Write some data to the file."""
        self.size = self.size + len(data)
        self._file.write(data)
        if self.rotateLength and self.size >= self.rotateLength:
            self.rotate()
    
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
    
    def getCurrentLog(self):
        """Return a LogReader for the current log file."""
        return LogReader(self.path)
    
    def getLog(self, identifier):
        """Given an integer, return a LogReader for an old log file."""
        filename = "%s.%d" % (self.path, identifier)
        if not os.path.exists(filename):
            raise ValueError, "no such logfile exists"
        return LogReader(filename)

threadable.synchronize(LogFile)


class LogReader:
    """Read from a log file."""
    
    def __init__(self, name):
        self._file = open(name, "r")
    
    def readLines(self):
        """Read a list of lines from the log file.
        
        This doesn't returns all of the files lines - call it multiple times.
        """
        result = []
        for i in range(10):
            line = self._file.readline()
            if not line:
                break
            result.append(line)
        return result

    def close(self):
        self._file.close()
