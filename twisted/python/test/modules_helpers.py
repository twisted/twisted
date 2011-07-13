# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Facilities for helping test code which interacts with L{twisted.python.modules},
or uses Python's own module system to load code.
"""

import sys

from twisted.trial.unittest import TestCase
from twisted.python import modules
from twisted.python.filepath import FilePath

class TwistedModulesTestCase(TestCase):

    def findByIteration(self, modname, where=modules, importPackages=False):
        """
        You don't ever actually want to do this, so it's not in the public API, but
        sometimes we want to compare the result of an iterative call with a
        lookup call and make sure they're the same for test purposes.
        """
        for modinfo in where.walkModules(importPackages=importPackages):
            if modinfo.name == modname:
                return modinfo
        self.fail("Unable to find module %r through iteration." % (modname,))


    def replaceSysPath(self, sysPath):
        """
        Replace sys.path, for the duration of the test, with the given value.
        """
        originalSysPath = sys.path[:]
        def cleanUpSysPath():
            sys.path[:] = originalSysPath
        self.addCleanup(cleanUpSysPath)
        sys.path[:] = sysPath


    def replaceSysModules(self, sysModules):
        """
        Replace sys.modules, for the duration of the test, with the given value.
        """
        originalSysModules = sys.modules.copy()
        def cleanUpSysModules():
            sys.modules.clear()
            sys.modules.update(originalSysModules)
        self.addCleanup(cleanUpSysModules)
        sys.modules.clear()
        sys.modules.update(sysModules)


    def pathEntryWithOnePackage(self, pkgname="test_package"):
        """
        Generate a L{FilePath} with one package, named C{pkgname}, on it, and
        return the L{FilePath} of the path entry.
        """
        entry = FilePath(self.mktemp())
        pkg = entry.child("test_package")
        pkg.makedirs()
        pkg.child("__init__.py").setContent("")
        return entry


