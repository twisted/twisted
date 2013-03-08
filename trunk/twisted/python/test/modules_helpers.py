# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Facilities for helping test code which interacts with Python's module system
to load code.
"""

from __future__ import division, absolute_import

import sys

from twisted.python.filepath import FilePath


class TwistedModulesMixin:
    """
    A mixin for C{twisted.trial.unittest.SynchronousTestCase} providing useful
    methods for manipulating Python's module system.
    """

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


    def pathEntryWithOnePackage(self, pkgname=b"test_package"):
        """
        Generate a L{FilePath} with one package, named C{pkgname}, on it, and
        return the L{FilePath} of the path entry.
        """
        # Remove utf-8 encode and bytes for path segments when Filepath
        # supports Unicode paths on Python 3 (#2366, #4736, #5203).
        entry = FilePath(self.mktemp().encode("utf-8"))
        pkg = entry.child(b"test_package")
        pkg.makedirs()
        pkg.child(b"__init__.py").setContent(b"")
        return entry


