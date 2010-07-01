# Copyright (c) 2006-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.python.modules, abstract access to imported or importable
objects.
"""

import sys
import itertools
import zipfile
import compileall
try:
    import ast
except ImportError:
    ast = None

import twisted
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



class BasicTests(PySpaceTestCase):

    def test_unimportablePackageGetItem(self):
        """
        If a package has been explicitly forbidden from importing by setting a
        C{None} key in sys.modules under its name,
        L{modules.PythonPath.__getitem__} should still be able to retrieve an
        unloaded L{modules.PythonModule} for that package.
        """
        shouldNotLoad = []
        path = modules.PythonPath(sysPath=[self.pathEntryWithOnePackage().path],
                                  moduleLoader=shouldNotLoad.append,
                                  importerCache={},
                                  sysPathHooks={},
                                  moduleDict={'test_package': None})
        self.assertEquals(shouldNotLoad, [])
        self.assertEquals(path['test_package'].isLoaded(), False)


    def test_unimportablePackageWalkModules(self):
        """
        If a package has been explicitly forbidden from importing by setting a
        C{None} key in sys.modules under its name, L{modules.walkModules} should
        still be able to retrieve an unloaded L{modules.PythonModule} for that
        package.
        """
        existentPath = self.pathEntryWithOnePackage()
        self.replaceSysPath([existentPath.path])
        self.replaceSysModules({"test_package": None})

        walked = list(modules.walkModules())
        self.assertEquals([m.name for m in walked],
                          ["test_package"])
        self.assertEquals(walked[0].isLoaded(), False)


    def test_nonexistentPaths(self):
        """
        Verify that L{modules.walkModules} ignores entries in sys.path which
        do not exist in the filesystem.
        """
        existentPath = self.pathEntryWithOnePackage()

        nonexistentPath = FilePath(self.mktemp())
        self.failIf(nonexistentPath.exists())

        self.replaceSysPath([existentPath.path])

        expected = [modules.getModule("test_package")]

        beforeModules = list(modules.walkModules())
        sys.path.append(nonexistentPath.path)
        afterModules = list(modules.walkModules())

        self.assertEquals(beforeModules, expected)
        self.assertEquals(afterModules, expected)


    def test_nonDirectoryPaths(self):
        """
        Verify that L{modules.walkModules} ignores entries in sys.path which
        refer to regular files in the filesystem.
        """
        existentPath = self.pathEntryWithOnePackage()

        nonDirectoryPath = FilePath(self.mktemp())
        self.failIf(nonDirectoryPath.exists())
        nonDirectoryPath.setContent("zip file or whatever\n")

        self.replaceSysPath([existentPath.path])

        beforeModules = list(modules.walkModules())
        sys.path.append(nonDirectoryPath.path)
        afterModules = list(modules.walkModules())

        self.assertEquals(beforeModules, afterModules)


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


sampleModuleContents = """
import sys, os
from twisted.python import reflect
import twisted.python.filepath
from twisted.python.components import registerAdapter

foo = 123
def doFoo():
  import datetime
class Foo:
  x = 0
"""

sampleModuleWithExportsContents = """
import sys, os, datetime
from twisted.python import reflect
import twisted.python.filepath
from twisted.python.components import registerAdapter

foo = 123
baz = 456
__all__ = ['foo']
"""



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
        self.packagePath.child("a.py").setContent(sampleModuleContents)
        self.packagePath.child("b.py").setContent(sampleModuleWithExportsContents)
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



    def test_moduleAttributes(self):
        """
        Module attributes can be iterated over without executing the code.
        """
        self._setupSysPath()
        modinfo = modules.getModule(self.packageName + ".a")
        attrs = sorted(modinfo.iterAttributes(), key=lambda a: a.name)
        names = sorted(["foo", "doFoo", "Foo"])
        for attr, name in zip(attrs, names):
            self.assertEquals(attr.onObject, modinfo)
            self.assertFalse(attr.isLoaded())
            self.assertEquals(attr.name, modinfo.name + '.' + name)
            self.assertRaises(NotImplementedError, lambda: list(attr.iterAttributes()))


    def test_loadedModuleAttributes(self):
        """
        Module attributes can be iterated over after the module has been loaded.
        """
        self._setupSysPath()
        modinfo = modules.getModule(self.packageName + ".a")
        modinfo.load()
        attrs = sorted([a for a in modinfo.iterAttributes() if '_' not in a.name], key=lambda a: a.name)
        names = sorted(["foo", "doFoo", "Foo"])
        for attr, name in zip(attrs, names):
            self.assertEquals(attr.onObject, modinfo)
            self.assertTrue(attr.isLoaded())
            self.assertEquals(attr.name, modinfo.name + '.' + name)
            if name == "Foo":
                classattrs = [a.name for a in attr.iterAttributes()]
                self.assertIn(modinfo.name + '.Foo.x', classattrs)


    def test_moduleImportNames(self):
        """
        The fully qualified names imported by a module can be inspected.
        """
        self._setupSysPath()
        modinfo = modules.getModule(self.packageName + ".a")
        self.assertEquals(sorted(modinfo.iterImportNames()),
                         sorted(["sys", "os", "datetime",
                                 "twisted.python.reflect",
                                 "twisted.python.filepath",
                                 "twisted.python.components.registerAdapter"]))


    def test_moduleExportDefinedNames(self):
        """
        The exports of a module with no __all__ are all its defined
        names.
        """
        self._setupSysPath()
        modinfo = modules.getModule(self.packageName + ".a")
        self.assertEqual(sorted(modinfo.iterExportNames()),
                         sorted(["foo", "doFoo", "Foo"]))


    def test_moduleExportAll(self):
        """
        If __all__ is defined as a list of string literals, the names
        in it are used as the list of the module's exports.
        """
        self._setupSysPath()
        modinfo = modules.getModule(self.packageName + ".b")
        self.assertEqual(sorted(modinfo.iterExportNames()),
                         sorted(["foo"]))


    def test_moduleExportProblems(self):
        """
        C{SyntaxError} is raised when doing inspection of module
        exports if __all__ is not a single list of string literals.
        """
        self.packagePath.child("e.py").setContent("__all__ = ['a' + 'b']")
        self.packagePath.child("f.py").setContent("__all__ = ['a']\n__all__ = ['a', 'b']")
        self._setupSysPath()
        modinfo1 = modules.getModule(self.packageName + ".e")
        modinfo2 = modules.getModule(self.packageName + ".f")
        self.assertRaises(SyntaxError, lambda: list(modinfo1.iterExportNames()))
        self.assertRaises(SyntaxError, lambda: list(modinfo2.iterExportNames()))


    if ast is None:
        astMsg = ("Examining unloaded module attributes requires the 'ast'"
                 " module from Python 2.6.")
        test_moduleAttributes.skip = astMsg
        test_moduleImportNames.skip = astMsg
        test_moduleExportAll.skip = astMsg
        test_moduleExportDefinedNames.skip = astMsg
        test_moduleExportProblems.skip = astMsg


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
    public API of L{twisted.python.modules}, L{PythonPath}.
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


    def test_inconsistentImporterCache(self):
        """
        If the path a module loaded with L{PythonPath.__getitem__} is not
        present in the path importer cache, a warning is emitted, but the
        L{PythonModule} is returned as usual.
        """
        space = modules.PythonPath([], sys.modules, [], {})
        thisModule = space[__name__]
        warnings = self.flushWarnings([self.test_inconsistentImporterCache])
        self.assertEquals(warnings[0]['category'], UserWarning)
        self.assertEquals(
            warnings[0]['message'],
            FilePath(twisted.__file__).parent().dirname() +
            " (for module " + __name__ + ") not in path importer cache "
            "(PEP 302 violation - check your local configuration).")
        self.assertEquals(len(warnings), 1)
        self.assertEquals(thisModule.name, __name__)



class ASTVisitorTests(TestCase):
    """
    Tests for L{ast.NodeVisitor} subclasses used to extract
    information from modules without importing them.
    """

    def test_justOneAll(self):
        """
        Modules with more than one definition of __all__ are rejected
        by L{_ImportExportFinder}.
        """

        code = "__all__ = ['a']\n__all__ = ['a', 'b']"
        tree = ast.parse(code)
        f = modules._ImportExportFinder()
        self.assertRaises(SyntaxError, f.visit, tree)


    def test_literalStringsAll(self):
        """
        Modules with a definition of __all__ that isn't a list of
        literal strings are rejected by L{_ImportExportFinder}.
        """

        code = "__all__ = ['a' + 'b']"
        tree = ast.parse(code)
        f = modules._ImportExportFinder()
        self.assertRaises(SyntaxError, f.visit, tree)

if ast is None:
    ASTVisitorTests.skip = "AST visitor tests require the 'ast' module from Python 2.6."
