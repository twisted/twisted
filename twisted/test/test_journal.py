# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Testing for twisted.persisted.journal."""

from twisted.trial import unittest
from twisted.persisted.journal.base import ICommand, MemoryJournal, serviceCommand, ServiceWrapperCommand, command, Wrappable
from twisted.persisted.journal.picklelog import DirDBMLog
from zope.interface import implements

import shutil, os.path



class AddTime:

    implements(ICommand)

    def execute(self, svc, cmdtime):
        svc.values["time"] = cmdtime


class Counter(Wrappable):

    objectType = "counter"

    def __init__(self, uid):
        self.uid = uid
        self.x = 0

    def getUid(self):
        return self.uid
    
    def _increment(self):
        self.x += 1

    increment = command("_increment")


class Service:

    def __init__(self, logpath, journalpath):
        log = DirDBMLog(logpath)
        self.journal = MemoryJournal(log, self, journalpath, self._gotData)
        self.journal.updateFromLog()
    
    def _gotData(self, result):
        if result is None:
            self.values = {}
            self.counters = {}
        else:
            self.values, self.counters = result

    def _makeCounter(self, id):
        c = Counter(id)
        self.counters[id] = c
        return c

    makeCounter = serviceCommand("_makeCounter")
    
    def loadObject(self, type, id):
        if type != "counter": raise ValueError
        return self.counters[id]
    
    def _add(self, key, value):
        """Add a new entry."""
        self.values[key] = value
    
    def _delete(self, key):
        """Delete an entry."""
        del self.values[key]

    def get(self, key):
        """Return value of an entry."""
        return self.values[key]

    def addtime(self, journal):
        """Set a key 'time' with the current time."""
        journal.executeCommand(AddTime())

    # and now the command wrappers
    
    add = serviceCommand("_add")

    delete = serviceCommand("_delete")


class JournalTestCase(unittest.TestCase):

    def setUp(self):
        self.logpath = self.mktemp()
        self.journalpath = self.mktemp()
        self.svc = Service(self.logpath, self.journalpath)

    def tearDown(self):
        if hasattr(self, "svc"):
            del self.svc
        # delete stuff? ...
        if os.path.isdir(self.logpath):
            shutil.rmtree(self.logpath)
        if os.path.exists(self.logpath):
            os.unlink(self.logpath)
        if os.path.isdir(self.journalpath):
            shutil.rmtree(self.journalpath)
        if os.path.exists(self.journalpath):
            os.unlink(self.journalpath)

    def testCommandExecution(self):
        svc = self.svc
        svc.add(svc.journal, "foo", "bar")
        self.assertEquals(svc.get("foo"), "bar")

        svc.delete(svc.journal, "foo")
        self.assertRaises(KeyError, svc.get, "foo")
    
    def testLogging(self):
        svc = self.svc
        log = self.svc.journal.log
        j = self.svc.journal
        svc.add(j, "foo", "bar")
        svc.add(j, 1, "hello")
        svc.delete(j, "foo")

        commands = [ServiceWrapperCommand("_add", ("foo", "bar")),
                    ServiceWrapperCommand("_add", (1, "hello")),
                    ServiceWrapperCommand("_delete", ("foo",))]

        self.assertEquals(log.getCurrentIndex(), 3)
        for i in range(1, 4):
            for a, b in zip(commands[i-1:], [c for t, c in log.getCommandsSince(i)]):
                self.assertEquals(a, b)

    def testRecovery(self):
        svc = self.svc
        j = svc.journal
        svc.add(j, "foo", "bar")
        svc.add(j, 1, "hello")
        # we sync *before* delete to make sure commands get executed
        svc.journal.sync((svc.values, svc.counters))
        svc.delete(j, "foo")
        d = svc.makeCounter(j, 1)
        d.addCallback(lambda c, j=j: c.increment(j))
        del svc, self.svc

        # first, load from snapshot
        svc = Service(self.logpath, self.journalpath)
        self.assertEquals(svc.values, {1: "hello"})
        self.assertEquals(svc.counters[1].x, 1)
        del svc

        # now, tamper with log, and then try
        f = open(self.journalpath, "w")
        f.write("sfsdfsdfsd")
        f.close()
        svc = Service(self.logpath, self.journalpath)
        self.assertEquals(svc.values, {1: "hello"})
        self.assertEquals(svc.counters[1].x, 1)
        
    def testTime(self):
        svc = self.svc
        svc.addtime(svc.journal)
        t = svc.get("time")

        log = self.svc.journal.log
        (t2, c), = log.getCommandsSince(1)
        self.assertEquals(t, t2)

        
