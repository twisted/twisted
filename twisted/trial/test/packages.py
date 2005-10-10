import os, shutil

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


files = [
    ('badpackage/__init__.py', 'frotz\n'),
    ('badpackage/test_module.py', ''),
    ('package2/__init__.py', ''),
    ('package2/test_module.py', 'import frotz\n'),
    ('package/__init__.py', ''),
    ('package/frotz.py', 'frotz\n'),
    ('package/test_bad_module.py', 'raise ZeroDivisionError("fake error")'),
    ('package/test_dos_module.py', dosModule),
    ('package/test_import_module.py', 'import frotz'),
    ('package/test_module.py', testModule),
    ('goodpackage/__init__.py', ''),
    ('goodpackage/test_sample.py', testSample),
    ('goodpackage/sub/__init__.py', ''),
    ('goodpackage/sub/test_sample.py', testSample)
    ]


def createFiles(files, parentDir='.'):
    for filename, contents in files:
        filename = os.path.join(parentDir, filename)
        _createDirectory(filename)
        fd = open(filename, 'w')
        fd.write(contents)
        fd.close()

def _createDirectory(filename):
    directory = os.path.dirname(filename)
    if not os.path.exists(directory):
        os.makedirs(directory)

def setUp(parentDir='.'):
    createFiles(files, parentDir)

def removeFiles(files, parentDir):
    directories = {}
    for filename, _ in files:
        directories[os.path.dirname(os.path.join(parentDir, filename))] = True
    dirs = directories.keys()
    dirs.sort()
    dirs.reverse()
    for directory in dirs:
        shutil.rmtree(directory)

def tearDown(parentDir='.'):
    removeFiles(files, parentDir)
