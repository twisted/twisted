# -*- test-case-name: twisted.test.test_journal -*-
#
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


"""Basic classes and interfaces for journal."""

# system imports
import os, cPickle, time

# twisted imports
from twisted.python.components import Interface


class Journal:
    """All commands to the system get routed through here.

    Subclasses should implement the actual snapshotting capability.
    """

    def __init__(self, log, journaledService):
        self.log = log
        self.journaledService = journaledService
        self.latestIndex = self.log.getCurrentIndex()
        snapshotIndex = self.getLastSnapshot()
        if snapshotIndex < self.latestIndex:
            for cmdtime, command in self.log.getCommandsSince(snapshotIndex + 1):
                command.execute(self.journaledService, cmdtime)

    def executeCommand(self, command):
        """Log and execute a command."""
        runTime = time.time()
        d = self.log.logCommand(command, runTime)
        d.addCallback(self._reallyExecute, command, runTime)
        return d

    def _reallyExecute(self, index, command, runTime):
        """Callback called when logging command is done."""
        result = command.execute(self.journaledService, runTime)
        self.latestIndex = index
        return result
    
    def getLastSnapshot(self):
        """Return command index of the last snapshot taken."""
        raise NotImplementedError

    def sync(self, *args, **kwargs):
        """Save journal to disk, returns Deferred of finish status.

        Subclasses may choose whatever signature is appropriate, or may
        not implement this at all.
        """
        raise NotImplementedError



class MemoryJournal(Journal):
    """Prevayler-like journal that dumps from memory to disk."""

    def __init__(self, log, journaledService, path, loadedCallback):
        self.path = path
        if os.path.exists(path):
            try:
                self.lastSync, obj = cPickle.load(open(path, "rb"))
            except (IOError, OSError, cPickle.UnpicklingError):
                self.lastSync, obj = 0, None
            loadedCallback(obj)
        else:
            self.lastSync = 0
            loadedCallback(None)
        Journal.__init__(self, log, journaledService)

    def getLastSnapshot(self):
        return self.lastSync

    def sync(self, obj):
        # make this more reliable at some point
        f = open(self.path, "wb")
        cPickle.dump((self.latestIndex, obj), f, 1)
        f.close()
        self.lastSync = self.latestIndex


class ICommand(Interface):
    """A serializable command which interacts with a journaled service."""

    def execute(self, journaledService, runTime):
        """Run the command."""


class ICommandLog(Interface):
    """Interface for command log."""

    def logCommand(self, command, runTime):
        """Add a command and its run time to the log.

        @return Deferred of command index.
        """

    def getCurrentIndex(self):
        """Return index of last command that was logged."""

    def getCommandsSince(self, index):
        """Return commands who's index >= the given one.

        @return list of (time, command) tuples, sorted with ascending times.
        """

