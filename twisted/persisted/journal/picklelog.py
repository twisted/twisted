# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
# 
# -*- test-case-name: twisted.test.test_journal -*-

"""Logging that uses pickles.

TODO: add log that logs to a file.
"""

# twisted imports
from twisted.spread import banana
from twisted.persisted import dirdbm
from twisted.internet import defer

# sibling imports
import base


class DirDBMLog:
    """Log pickles to DirDBM directory."""

    __implements__ = base.ICommandLog

    def __init__(self, logPath):
        self.db = dirdbm.Shelf(logPath)
        indexs = map(int, self.db.keys())
        if indexs:
            self.currentIndex = max(indexs)
        else:
            self.currentIndex = 0
            
    def logCommand(self, command, time):
        """Log a command."""
        self.currentIndex += 1
        self.db[str(self.currentIndex)] = (time, command)
        return defer.succeed(1)
    
    def getCurrentIndex(self):
        """Return index of last command logged."""
        return self.currentIndex
    
    def getCommandsSince(self, index):
        result = []
        for i in range(index, self.currentIndex + 1):
            result.append(self.db[str(i)])
        return result

