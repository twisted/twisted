import sys, os
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
        ('goodpackage/sub/test_sample.py', testSample)
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

    def createFiles(self, files, parentDir='.'):
        for filename, contents in self.files:
            filename = os.path.join(parentDir, filename)
            self._createDirectory(filename)
            fd = open(filename, 'w')
            fd.write(contents)
            fd.close()

    def _createDirectory(self, filename):
        directory = os.path.dirname(filename)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def setUp(self, parentDir=None):
        if parentDir is None:
            parentDir = self.mktemp()
        self.parent = parentDir
        self.createFiles(self.files, parentDir)

    def tearDown(self):
        self.cleanUpModules()

class SysPathManglingTest(PackageTest):
    def setUp(self, parent=None):
        self.oldPath = sys.path[:]
        self.newPath = sys.path[:]
        if parent is None:
            parent = self.mktemp()
        PackageTest.setUp(self, parent)
        self.newPath.append(self.parent)
        self.mangleSysPath(self.newPath)

    def tearDown(self):
        PackageTest.tearDown(self)
        self.mangleSysPath(self.oldPath)

    def mangleSysPath(self, pathVar):
        sys.path[:] = pathVar

