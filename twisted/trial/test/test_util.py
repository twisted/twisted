from twisted.trial import unittest, util
from twisted.trial.test import packages

import sys, os


class TestMktemp(unittest.TestCase):
    def test_name(self):
        name = self.mktemp()
        dirs = os.path.dirname(name).split(os.sep)[:-1]
        self.failUnlessEqual(
            dirs, ['twisted.trial.test.test_util', 'TestMktemp', 'test_name'])

    def test_unique(self):
        name = self.mktemp()
        self.failIfEqual(name, self.mktemp())

    def test_created(self):
        name = self.mktemp()
        dirname = os.path.dirname(name)
        self.failUnless(os.path.exists(dirname))
        self.failIf(os.path.exists(name))

    def test_location(self):
        path = os.path.abspath(self.mktemp())
        self.failUnless(path.startswith(os.getcwd()))


class TestIntrospection(unittest.TestCase):
    def test_containers(self):
        import suppression
        parents = util.getPythonContainers(
            suppression.TestSuppression2.testSuppressModule)
        expected = [ suppression.TestSuppression2,
                     suppression ]
        for a, b in zip(parents, expected):
            self.failUnlessEqual(a, b)


class TestFindObject(packages.SysPathManglingTest):
    def test_importPackage(self):
        package1 = util.findObject('package')
        import package as package2
        self.failUnlessEqual(package1, (True, package2))

    def test_importModule(self):
        test_sample2 = util.findObject('goodpackage.test_sample')
        from goodpackage import test_sample
        self.failUnlessEqual((True, test_sample), test_sample2)

    def test_importError(self):
        self.failUnlessRaises(ZeroDivisionError,
                              util.findObject, 'package.test_bad_module')

    def test_sophisticatedImportError(self):
        self.failUnlessRaises(ImportError,
                              util.findObject, 'package2.test_module')

    def test_importNonexistentPackage(self):
        self.failUnlessEqual(util.findObject('doesntexist')[0], False)

    def test_findNonexistentModule(self):
        self.failUnlessEqual(util.findObject('package.doesntexist')[0], False)

    def test_findNonexistentObject(self):
        self.failUnlessEqual(util.findObject(
            'goodpackage.test_sample.doesnt')[0], False)
        self.failUnlessEqual(util.findObject(
            'goodpackage.test_sample.AlphabetTest.doesntexist')[0], False)

    def test_findObjectExist(self):
        alpha1 = util.findObject('goodpackage.test_sample.AlphabetTest')
        from goodpackage import test_sample
        self.failUnlessEqual(alpha1, (True, test_sample.AlphabetTest))

