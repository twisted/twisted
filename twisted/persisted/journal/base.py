# -*- test-case-name: twisted.test.test_journal -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# 


"""Basic classes and interfaces for journal."""

from __future__ import nested_scopes

# system imports
import os, time

try:
    import cPickle as pickle
except ImportError:
    import pickle

# twisted imports
from zope.interface import implements, Interface


class Journal:
    """All commands to the system get routed through here.

    Subclasses should implement the actual snapshotting capability.
    """

    def __init__(self, log, journaledService):
        self.log = log
        self.journaledService = journaledService
        self.latestIndex = self.log.getCurrentIndex()

    def updateFromLog(self):
        """Run all commands from log that haven't been run yet.

        This method should be run on startup to ensure the snapshot
        is up-to-date.
        """
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
                self.lastSync, obj = pickle.load(open(path, "rb"))
            except (IOError, OSError, pickle.UnpicklingError):
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
        pickle.dump((self.latestIndex, obj), f, 1)
        f.close()
        self.lastSync = self.latestIndex


class ICommand(Interface):
    """A serializable command which interacts with a journaled service."""

    def execute(journaledService, runTime):
        """Run the command and return result."""


class ICommandLog(Interface):
    """Interface for command log."""

    def logCommand(command, runTime):
        """Add a command and its run time to the log.

        @return: Deferred of command index.
        """

    def getCurrentIndex():
        """Return index of last command that was logged."""

    def getCommandsSince(index):
        """Return commands who's index >= the given one.

        @return: list of (time, command) tuples, sorted with ascending times.
        """


class LoadingService:
    """Base class for journalled service used with Wrappables."""

    def loadObject(self, objType, objId):
        """Return object of specified type and id."""
        raise NotImplementedError


class Wrappable:
    """Base class for objects used with LoadingService."""

    objectType = None # override in base class

    def getUid(self):
        """Return uid for loading with LoadingService.loadObject"""
        raise NotImplementedError


class WrapperCommand:
    
    implements(ICommand)

    def __init__(self, methodName, obj, args=(), kwargs={}):
        self.obj = obj
        self.objId = obj.getUid()
        self.objType = obj.objectType
        self.methodName = methodName
        self.args = args
        self.kwargs = kwargs

    def execute(self, svc, commandTime):
        if not hasattr(self, "obj"):
            obj = svc.loadObject(self.objType, self.objId)
        else:
            obj = self.obj
        return getattr(obj, self.methodName)(*self.args, **self.kwargs)

    def __getstate__(self):
        d = self.__dict__.copy()
        del d["obj"]
        return d


def command(methodName, cmdClass=WrapperCommand):
    """Wrap a method so it gets turned into command automatically.

    For use with Wrappables.

    Usage::

        | class Foo(Wrappable):
        |     objectType = "foo"
        |     def getUid(self):
        |         return self.id
        |     def _bar(self, x):
        |         return x + 1
        |
        |     bar = command('_bar')

    The resulting callable will have signature identical to wrapped
    function, except that it expects journal as first argument, and
    returns a Deferred.
    """
    def wrapper(obj, journal, *args, **kwargs):
        return journal.executeCommand(cmdClass(methodName, obj, args, kwargs))
    return wrapper


class ServiceWrapperCommand:

    implements(ICommand)

    def __init__(self, methodName, args=(), kwargs={}):
        self.methodName = methodName
        self.args = args
        self.kwargs = kwargs

    def execute(self, svc, commandTime):
        return getattr(svc, self.methodName)(*self.args, **self.kwargs)

    def __repr__(self):
        return "<ServiceWrapperCommand: %s, %s, %s>" % (self.methodName, self.args, self.kwargs)
    
    def __cmp__(self, other):
        if hasattr(other, "__dict__"):
            return cmp(self.__dict__, other.__dict__)
        else:
            return 0


def serviceCommand(methodName, cmdClass=ServiceWrapperCommand):
    """Wrap methods into commands for a journalled service.

    The resulting callable will have signature identical to wrapped
    function, except that it expects journal as first argument, and
    returns a Deferred.
    """
    def wrapper(obj, journal, *args, **kwargs):
        return journal.executeCommand(cmdClass(methodName, args, kwargs))
    return wrapper
