import sys, os, py_compile
from twisted.trial import unittest

testModule = """
from twisted.trial import unittest

class FooTest(unittest.TestCase):
    def testFoo(self):
        pass
"""

dosModule = testModule.replace('\n', '\r\n')


testSample = """
'''This module is used by test_loader to test the Trial test loading
functionality. Do NOT change the number of tests in this module.
Do NOT change the names the tests in this module.
'''

import unittest as pyunit
from twisted.trial import unittest

class FooTest(unittest.TestCase):
    def test_foo(self):
        pass

    def test_bar(self):
        pass


class PyunitTest(pyunit.TestCase):
    def test_foo(self):
        pass

    def test_bar(self):
        pass


class NotATest(object):
    def test_foo(self):
        pass


class AlphabetTest(unittest.TestCase):
    def test_a(self):
        pass

    def test_b(self):
        pass

    def test_c(self):
        pass
"""


class PackageTest(unittest.TestCase):
    files = [
        ('badpackage/__init__.py', 'frotz\n'),
        ('badpackage/test_module.py', ''),
        ('package2/__init__.py', ''),
        ('package2/test_module.py', 'import frotz\n'),
        ('package/__init__.py', ''),
        ('package/frotz.py', 'frotz\n'),
        ('package/test_bad_module.py',
         'raise ZeroDivisionError("fake error")'),
        ('package/test_dos_module.py', dosModule),
        ('package/test_import_module.py', 'import frotz'),
        ('package/test_module.py', testModule),
        ('goodpackage/__init__.py', ''),
        ('goodpackage/test_sample.py', testSample),
        ('goodpackage/sub/__init__.py', ''),
        ('goodpackage/sub/test_sample.py', testSample),
        ('stalepackage/__init__.py', ''),
        ('stalepackage/test_sample.py', testModule),
        ('stalepackage/test_sample2.py', testModule),
        ('stalepackage/test_removed.py', testModule),
        ('nosourcepackage/__init__.py', ''),
        ('nosourcepackage/test_sample.py', testModule),
        ]

    def _toModuleName(self, filename):
        name = os.path.splitext(filename)[0]
        segs = name.split('/')
        if segs[-1] == '__init__':
            segs = segs[:-1]
        return '.'.join(segs)

    def getModules(self):
        return map(self._toModuleName, zip(*self.files)[0])

    def cleanUpModules(self):
        modules = self.getModules()
        modules.sort()
        modules.reverse()
        for module in modules:
            try:
                del sys.modules[module]
            except KeyError:
                pass

    def createFiles(self, files, parentDir='.', clean=False):
        """
        Create files for testing Python package loading.

        @param parentDir: A filesystem path in which to create the files.
        @type parentDir: C{str}, or None.

        @param clean: Whether or not to exclude the package with stale .pyc
        files.
        @type clean: C{bool}
        """
        for filename, contents in files:
            filename = os.path.join(parentDir, filename)
            self._createDirectory(filename)
            fd = open(filename, 'w')
            fd.write(contents)
            fd.close()

        if not clean:
            staledir = os.path.join(parentDir, 'stalepackage')
            py_compile.compile(os.path.join(staledir, 'test_sample2.py'))
            removable = os.path.join(staledir, 'test_removed.py')
            py_compile.compile(removable)
            os.remove(removable)

            nosourcedir = os.path.join(parentDir, 'nosourcepackage')
            testfile = os.path.join(nosourcedir, 'test_sample.py')
            initfile = os.path.join(nosourcedir, '__init__.py')
            py_compile.compile(testfile)
            py_compile.compile(initfile)
            os.remove(testfile)
            os.remove(initfile)


    def _createDirectory(self, filename):
        directory = os.path.dirname(filename)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def setUp(self, parentDir=None, clean=False):
        """
        Create files needed for testing Python package loading.

        @param parentDir: A filesystem path in which to create the files.
        @type parentDir: C{str}, or None.

        @param clean: Whether or not to exclude the package with stale .pyc
        files.
        @type clean: C{bool}
        """
        if parentDir is None:
            parentDir = self.mktemp()
        self.parent = parentDir
        self.createFiles(self.files, parentDir, clean)


    def tearDown(self):
        self.cleanUpModules()

class SysPathManglingTest(PackageTest):
    def setUp(self, parent=None, clean=False):
        """
        Add files created for these tests to sys.path.

        @param parent: A filesystem path in which to create the files.
        @type parent: C{str}, or None.

        @param clean: Whether or not to exclude the package with stale .pyc
        files.
        @type clean: C{bool}
        """
        self.oldPath = sys.path[:]
        self.newPath = sys.path[:]
        if parent is None:
            parent = self.mktemp()
        PackageTest.setUp(self, parent, clean)
        self.newPath.append(self.parent)
        self.mangleSysPath(self.newPath)

    def tearDown(self):
        PackageTest.tearDown(self)
        self.mangleSysPath(self.oldPath)

    def mangleSysPath(self, pathVar):
        sys.path[:] = pathVar

