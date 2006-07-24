
"""

Tests for twisted.python.modules, abstract access to imported or importable
objects.

"""

import sys
import itertools
import zipfile

from twisted.trial.unittest import TestCase

from twisted.python import modules
from twisted.python.filepath import FilePath
from twisted.python.reflect import namedAny

from twisted.test.test_paths import zipit

class PySpaceTestCase(TestCase):

    def findByIteration(self, modname, where=modules, importPackages=False):
        """ You don't ever actually want to do this, so it's not in the public API, but
        sometimes we want to compare the result of an iterative call with a
        lookup call and make sure they're the same for test purposes.  """
        for modinfo in where.walkModules(importPackages=importPackages):
            if modinfo.name == modname:
                return modinfo
        self.fail("Unable to find module %r through iteration." % (modname,))



class BasicTests(PySpaceTestCase):
    def test_twistedShowsUp(self):
        """ Scrounge around in the top-level module namespace and make sure that
        Twisted shows up, and that the module thusly obtained is the same as
        the module that we find when we look for it explicitly by name.  """
        self.assertEquals(modules.getModule('twisted'),
                          self.findByIteration("twisted"))


    def test_dottedNames(self):
        """ Verify that the walkModules APIs will give us back subpackages, not just
        subpackages.  """
        self.assertEquals(
            modules.getModule('twisted.python'),
            self.findByIteration("twisted.python",
                                 where=modules.getModule('twisted')))


    def test_onlyTopModules(self):
        """ Verify that the iterModules API will only return top-level modules and
        packages, not submodules or subpackages.  """
        for module in modules.iterModules():
            self.failIf(
                '.' in module.name,
                "no nested modules should be returned from iterModules: %r"
                % (module.filePath))


    def test_loadPackagesAndModules(self):
        """ Verify that we can locate and load packages, modules, submodules, and
        subpackages.  """
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
        """ Verify that path entries discovered via module loading are, in fact, on
        sys.path somewhere.  """
        for n in ['os',
                  'twisted',
                  'twisted.python',
                  'twisted.python.reflect']:
            self.failUnlessIn(
                modules.getModule(n).pathEntry.filePath.path,
                sys.path)



class PathModificationTest(PySpaceTestCase):
    """ These tests share setup/cleanup behavior of creating a dummy package and
    stuffing some code in it.  """

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
        """ Verify that iterModules will honor the __path__ of already-loaded packages.
        """
        self._underUnderPathTest()


    def test_underUnderPathNotAlreadyImported(self):
        """ Verify that iterModules will honor the __path__ of already-loaded packages.
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
        """ Make sure the module list comes back as we expect from iterModules on a
        package, whether zipped or not.  """
        self._setupSysPath()
        self._listModules()


    def test_listingModulesAlreadyImported(self):
        """ Make sure the module list comes back as we expect from iterModules on a
        package, whether zipped or not, even if the package has already been
        imported.  """
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



class ZipPathModificationTest(PathModificationTest):
    def _setupSysPath(self):
        assert not self.pathSetUp
        zipit(self.pathExtensionName, self.pathExtensionName+'.zip')
        self.pathExtensionName += '.zip'
        assert zipfile.is_zipfile(self.pathExtensionName)
        PathModificationTest._setupSysPath(self)


