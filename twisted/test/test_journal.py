"""Testing for twisted.persisted.journal."""

from pyunit import unittest

from twisted.persisted.journal.base import ICommand, MemoryJournal
from twisted.persisted.journal.picklelog import DirDBMLog

import tempfile



class AddEntry:
    
    __implements__ = ICommand
    
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def execute(self, svc, time):
        svc.values[self.key] = self.value

    def __eq__(self, other):
        if hasattr(other, "__dict__"):
            return self.__dict__ == other.__dict__
        else:
            return 0


class DeleteEntry:

    __implements__ = ICommand

    def __init__(self, key):
        self.key = key

    def execute(self, svc, time):
        del svc.values[self.key]

    def __eq__(self, other):
        if hasattr(other, "__dict__"):
            return self.__dict__ == other.__dict__
        else:
            return 0


class AddTime:

    __implements__ = ICommand

    def execute(self, svc, cmdtime):
        svc.values["time"] = cmdtime


class Service:

    def __init__(self, logpath, journalpath):
        log = DirDBMLog(logpath)
        self.journal = MemoryJournal(log, self, journalpath, self._gotData)

    def _gotData(self, result):
        if result is None:
            self.values = {}
        else:
            self.values = result

    # next 3 methods are "business logic":

    def add(self, key, value):
        """Add a new entry."""
        self.journal.executeCommand(AddEntry(key, value))

    def delete(self, key):
        """Delete an entry."""
        self.journal.executeCommand(DeleteEntry(key))

    def get(self, key):
        """Return value of an entry."""
        return self.values[key]

    def addtime(self):
        """Set a key 'time' with the current time."""
        self.journal.executeCommand(AddTime())


class JournalTestCase(unittest.TestCase):

    def setUp(self):
        self.logpath = tempfile.mktemp()
        self.journalpath = tempfile.mktemp()
        self.svc = Service(self.logpath, self.journalpath)

    def tearDown(self):
        if hasattr(self, "svc"):
            del self.svc
        # delete stuff? ...

    def testCommandExecution(self):
        svc = self.svc

        svc.add("foo", "bar")
        self.assertEquals(svc.get("foo"), "bar")

        svc.delete("foo")
        self.assertRaises(KeyError, svc.get, "foo")
    
    def testLogging(self):
        svc = self.svc
        log = self.svc.journal.log
        svc.add("foo", "bar")
        svc.add(1, "hello")
        svc.delete("foo")

        commands = [AddEntry("foo", "bar"), AddEntry(1, "hello"), DeleteEntry("foo")]

        self.assertEquals(log.getCurrentIndex(), 3)

        for i in range(1, 4):
            self.assertEquals(commands[i-1:], [c for t, c in log.getCommandsSince(i)])

    def testRecovery(self):
        svc = self.svc
        svc.add("foo", "bar")
        svc.add(1, "hello")
        # we sync *before* delete to make sure commands get executed
        svc.journal.sync(svc.values)
        svc.delete("foo")
        del svc, self.svc

        # first, load from snapshot
        svc = Service(self.logpath, self.journalpath)
        self.assertEquals(svc.values, {1: "hello"})
        del svc

        # now, tamper with log, and then try
        f = open(self.journalpath, "w")
        f.write("sfsdfsdfsd")
        f.close()
        svc = Service(self.logpath, self.journalpath)
        self.assertEquals(svc.values, {1: "hello"})

    def testTime(self):
        svc = self.svc
        svc.addtime()
        t = svc.get("time")

        log = self.svc.journal.log
        (t2, c), = log.getCommandsSince(1)
        self.assertEquals(t, t2)
