# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.runner.procmon}.
"""

from twisted.trial import unittest
from twisted.runner.procmon import ProcessMonitor
from twisted.internet import reactor


class ProcmonTests(unittest.TestCase):
    """
    Tests for L{ProcessMonitor}.
    """
    def test_addProcess(self):
        """
        L{ProcessMonitor.addProcess} starts the named program and tracks the
        resulting process, a protocol for collecting its stdout, and the time
        it was started.
        """
        spawnedProcesses = []
        def fakeSpawnProcess(*args, **kwargs):
            spawnedProcesses.append((args, kwargs))
        self.patch(reactor, "spawnProcess", fakeSpawnProcess)
        pm = ProcessMonitor()
        pm.active = True
        pm.addProcess("foo", ["arg1", "arg2"], uid=1, gid=2)
        self.assertEquals(pm.processes, {"foo": (["arg1", "arg2"], 1, 2, {})})
        self.assertEquals(pm.protocols.keys(), ["foo"])
        lp = pm.protocols["foo"]
        self.assertEquals(
            spawnedProcesses,
            [((lp, "arg1", ["arg1", "arg2"]),
              {"uid": 1, "gid": 2, "env": {}})])


    def test_addProcessEnv(self):
        """
        L{ProcessMonitor.addProcess} takes an C{env} parameter that is passed
        to C{spawnProcess}.
        """
        spawnedProcesses = []
        def fakeSpawnProcess(*args, **kwargs):
            spawnedProcesses.append((args, kwargs))
        self.patch(reactor, "spawnProcess", fakeSpawnProcess)
        pm = ProcessMonitor()
        pm.active = True
        fakeEnv = {"KEY": "value"}
        pm.addProcess("foo", ["foo"], uid=1, gid=2, env=fakeEnv)
        self.assertEquals(
            spawnedProcesses,
            [((pm.protocols["foo"], "foo", ["foo"]),
              {"uid": 1, "gid": 2, "env": fakeEnv})])
