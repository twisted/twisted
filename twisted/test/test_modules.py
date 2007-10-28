# Copyright (c) 2006-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.python.modules, abstract access to imported or importable
objects.
"""

import os
import sys
import itertools
import zipfile
import compileall

from twisted.trial.unittest import TestCase

from twisted.python import modules
from twisted.python.filepath import FilePath
from twisted.python.reflect import namedAny

from twisted.test.test_paths import zipit



class PySpaceTestCase(TestCase):

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



class BasicTests(PySpaceTestCase):
    def test_nonexistentPaths(self):
        """
        Verify that L{modules.walkModules} ignores entries in sys.path which
        do not exist in the filesystem.
        """
        existentPath = FilePath(self.mktemp())
        os.makedirs(existentPath.child("test_package").path)
        existentPath.child("test_package").child("__init__.py").setContent("")

        nonexistentPath = FilePath(self.mktemp())
        self.failIf(nonexistentPath.exists())

        originalSearchPaths = sys.path[:]
        sys.path[:] = [existentPath.path]
        try:
            expected = [modules.getModule("test_package")]

            beforeModules = list(modules.walkModules())
            sys.path.append(nonexistentPath.path)
            afterModules = list(modules.walkModules())
        finally:
            sys.path[:] = originalSearchPaths

        self.assertEqual(beforeModules, expected)
        self.assertEqual(afterModules, expected)


    def test_nonDirectoryPaths(self):
        """
        Verify that L{modules.walkModules} ignores entries in sys.path which
        refer to regular files in the filesystem.
        """
        existentPath = FilePath(self.mktemp())
        os.makedirs(existentPath.child("test_package").path)
        existentPath.child("test_package").child("__init__.py").setContent("")

        nonDirectoryPath = FilePath(self.mktemp())
        self.failIf(nonDirectoryPath.exists())
        nonDirectoryPath.setContent("zip file or whatever\n")

        originalSearchPaths = sys.path[:]
        sys.path[:] = [existentPath.path]
        try:
            beforeModules = list(modules.walkModules())
            sys.path.append(nonDirectoryPath.path)
            afterModules = list(modules.walkModules())
        finally:
            sys.path[:] = originalSearchPaths

        self.assertEqual(beforeModules, afterModules)


    def test_twistedShowsUp(self):
        """
        Scrounge around in the top-level module namespace and make sure that
        Twisted shows up, and that the module thusly obtained is the same as
        the module that we find when we look for it explicitly by name.
        """
        self.assertEquals(modules.getModule('twisted'),
                          self.findByIteration("twisted"))


    def test_dottedNames(self):
        """
        Verify that the walkModules APIs will give us back subpackages, not just
        subpackages.
        """
        self.assertEquals(
            modules.getModule('twisted.python'),
            self.findByIteration("twisted.python",
                                 where=modules.getModule('twisted')))


    def test_onlyTopModules(self):
        """
        Verify that the iterModules API will only return top-level modules and
        packages, not submodules or subpackages.
        """
        for module in modules.iterModules():
            self.failIf(
                '.' in module.name,
                "no nested modules should be returned from iterModules: %r"
                % (module.filePath))


    def test_loadPackagesAndModules(self):
        """
        Verify that we can locate and load packages, modules, submodules, and
        subpackages.
        """
        for n in ['os',
                  'twisted',
                  'twisted.python',
                  'twisted.python.reflect']:
            m = namedAny(n)
            self.failUnlessIdentical(
                modules.getModule(n).load(),
                m)
            self.failUnlessIdentical(
                self.findByIteration(n).load(),
                m)


    def test_pathEntriesOnPath(self):
        """
        Verify that path entries discovered via module loading are, in fact, on
        sys.path somewhere.
        """
        for n in ['os',
                  'twisted',
                  'twisted.python',
                  'twisted.python.reflect']:
            self.failUnlessIn(
                modules.getModule(n).pathEntry.filePath.path,
                sys.path)


    def test_alwaysPreferPy(self):
        """
        Verify that .py files will always be preferred to .pyc files, regardless of
        directory listing order.
        """
        mypath = FilePath(self.mktemp())
        mypath.createDirectory()
        pp = modules.PythonPath(sysPath=[mypath.path])
        originalSmartPath = pp._smartPath
        def _evilSmartPath(pathName):
            o = originalSmartPath(pathName)
            originalChildren = o.children
            def evilChildren():
                # normally this order is random; let's make sure it always
                # comes up .pyc-first.
                x = originalChildren()
                x.sort()
                x.reverse()
                return x
            o.children = evilChildren
            return o
        mypath.child("abcd.py").setContent('\n')
        compileall.compile_dir(mypath.path, quiet=True)
        # sanity check
        self.assertEquals(len(mypath.children()), 2)
        pp._smartPath = _evilSmartPath
        self.assertEquals(pp['abcd'].filePath,
                          mypath.child('abcd.py'))


    def test_packageMissingPath(self):
        """
        A package can delete its __path__ for some reasons,
        C{modules.PythonPath} should be able to deal with it.
        """
        mypath = FilePath(self.mktemp())
        mypath.createDirectory()
        pp = modules.PythonPath(sysPath=[mypath.path])
        subpath = mypath.child("abcd")
        subpath.createDirectory()
        subpath.child("__init__.py").setContent('del __path__\n')
        sys.path.append(mypath.path)
        import abcd
        try:
            l = list(pp.walkModules())
            self.assertEquals(len(l), 1)
            self.assertEquals(l[0].name, 'abcd')
        finally:
            del abcd
            del sys.modules['abcd']
            sys.path.remove(mypath.path)



class PathModificationTest(PySpaceTestCase):
    """
    These tests share setup/cleanup behavior of creating a dummy package and
    stuffing some code in it.
    """

    _serialnum = itertools.count().next # used to generate serial numbers for
                                        # package names.

    def setUp(self):
        self.pathExtensionName = self.mktemp()
        self.pathExtension = FilePath(self.pathExtensionName)
        self.pathExtension.createDirectory()
        self.packageName = "pyspacetests%d" % (self._serialnum(),)
        self.packagePath = self.pathExtension.child(self.packageName)
        self.packagePath.createDirectory()
        self.packagePath.child("__init__.py").setContent("")
        self.packagePath.child("a.py").setContent("")
        self.packagePath.child("b.py").setContent("")
        self.packagePath.child("c__init__.py").setContent("")
        self.pathSetUp = False


    def _setupSysPath(self):
        assert not self.pathSetUp
        self.pathSetUp = True
        sys.path.append(self.pathExtensionName)


    def _underUnderPathTest(self, doImport=True):
        moddir2 = self.mktemp()
        fpmd = FilePath(moddir2)
        fpmd.createDirectory()
        fpmd.child("foozle.py").setContent("x = 123\n")
        self.packagePath.child("__init__.py").setContent(
            "__path__.append(%r)\n" % (moddir2,))
        # Cut here
        self._setupSysPath()
        modinfo = modules.getModule(self.packageName)
        self.assertEquals(
            self.findByIteration(self.packageName+".foozle", modinfo,
                                 importPackages=doImport),
            modinfo['foozle'])
        self.assertEquals(modinfo['foozle'].load().x, 123)


    def test_underUnderPathAlreadyImported(self):
        """
        Verify that iterModules will honor the __path__ of already-loaded packages.
        """
        self._underUnderPathTest()


    def test_underUnderPathNotAlreadyImported(self):
        """
        Verify that iterModules will honor the __path__ of already-loaded packages.
        """
        self._underUnderPathTest(False)


    test_underUnderPathNotAlreadyImported.todo = (
        "This may be impossible but it sure would be nice.")


    def _listModules(self):
        pkginfo = modules.getModule(self.packageName)
        nfni = [modinfo.name.split(".")[-1] for modinfo in
                pkginfo.iterModules()]
        nfni.sort()
        self.failUnlessEqual(nfni, ['a', 'b', 'c__init__'])


    def test_listingModules(self):
        """
        Make sure the module list comes back as we expect from iterModules on a
        package, whether zipped or not.
        """
        self._setupSysPath()
        self._listModules()


    def test_listingModulesAlreadyImported(self):
        """
        Make sure the module list comes back as we expect from iterModules on a
        package, whether zipped or not, even if the package has already been
        imported.
        """
        self._setupSysPath()
        namedAny(self.packageName)
        self._listModules()


    def tearDown(self):
        # Intentionally using 'assert' here, this is not a test assertion, this
        # is just an "oh fuck what is going ON" assertion. -glyph
        if self.pathSetUp:
            HORK = "path cleanup failed: don't be surprised if other tests break"
            assert sys.path.pop() is self.pathExtensionName, HORK+", 1"
            assert self.pathExtensionName not in sys.path, HORK+", 2"



class RebindingTest(PathModificationTest):
    """
    These tests verify that the default path interrogation API works properly
    even when sys.path has been rebound to a different object.
    """
    def _setupSysPath(self):
        assert not self.pathSetUp
        self.pathSetUp = True
        self.savedSysPath = sys.path
        sys.path = sys.path[:]
        sys.path.append(self.pathExtensionName)


    def tearDown(self):
        """
        Clean up sys.path by re-binding our original object.
        """
        if self.pathSetUp:
            sys.path = self.savedSysPath



class ZipPathModificationTest(PathModificationTest):
    def _setupSysPath(self):
        assert not self.pathSetUp
        zipit(self.pathExtensionName, self.pathExtensionName+'.zip')
        self.pathExtensionName += '.zip'
        assert zipfile.is_zipfile(self.pathExtensionName)
        PathModificationTest._setupSysPath(self)


class PythonPathTestCase(TestCase):
    """
    Tests for the class which provides the implementation for all of the
    public API of L{twisted.python.modules}.
    """
    def test_unhandledImporter(self):
        """
        Make sure that the behavior when encountering an unknown importer
        type is not catastrophic failure.
        """
        class SecretImporter(object):
            pass

        def hook(name):
            return SecretImporter()

        syspath = ['example/path']
        sysmodules = {}
        syshooks = [hook]
        syscache = {}
        def sysloader(name):
            return None
        space = modules.PythonPath(
            syspath, sysmodules, syshooks, syscache, sysloader)
        entries = list(space.iterEntries())
        self.assertEquals(len(entries), 1)
        self.assertRaises(KeyError, lambda: entries[0]['module'])
