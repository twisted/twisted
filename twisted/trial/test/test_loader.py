# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for loading tests by name.
"""

import os
import shutil
import sys

from twisted.python import util
from twisted.python.hashlib import md5
from twisted.trial.test import packages
from twisted.trial import runner, reporter, unittest
from twisted.trial.itrial import ITestCase

from twisted.python.modules import getModule



def testNames(tests):
    """
    Return the id of each test within the given test suite or case.
    """
    names = []
    for test in unittest._iterateTests(tests):
        names.append(test.id())
    return names



class FinderTest(packages.PackageTest):
    def setUp(self):
        packages.PackageTest.setUp(self)
        self.loader = runner.TestLoader()

    def tearDown(self):
        packages.PackageTest.tearDown(self)

    def test_findPackage(self):
        sample1 = self.loader.findByName('twisted')
        import twisted as sample2
        self.assertEqual(sample1, sample2)

    def test_findModule(self):
        sample1 = self.loader.findByName('twisted.trial.test.sample')
        import sample as sample2
        self.assertEqual(sample1, sample2)

    def test_findFile(self):
        path = util.sibpath(__file__, 'sample.py')
        sample1 = self.loader.findByName(path)
        import sample as sample2
        self.assertEqual(sample1, sample2)

    def test_findObject(self):
        sample1 = self.loader.findByName('twisted.trial.test.sample.FooTest')
        import sample
        self.assertEqual(sample.FooTest, sample1)

    def test_findNonModule(self):
        self.failUnlessRaises(AttributeError,
                              self.loader.findByName,
                              'twisted.trial.test.nonexistent')

    def test_findNonPackage(self):
        self.failUnlessRaises(ValueError,
                              self.loader.findByName,
                              'nonextant')

    def test_findNonFile(self):
        path = util.sibpath(__file__, 'nonexistent.py')
        self.failUnlessRaises(ValueError, self.loader.findByName, path)



class FileTest(packages.SysPathManglingTest):
    """
    Tests for L{runner.filenameToModule}.
    """
    def test_notFile(self):
        self.failUnlessRaises(ValueError,
                              runner.filenameToModule, 'doesntexist')

    def test_moduleInPath(self):
        sample1 = runner.filenameToModule(util.sibpath(__file__, 'sample.py'))
        import sample as sample2
        self.assertEqual(sample2, sample1)


    def test_moduleNotInPath(self):
        """
        If passed the path to a file containing the implementation of a
        module within a package which is not on the import path,
        L{runner.filenameToModule} returns a module object loosely
        resembling the module defined by that file anyway.
        """
        # "test_sample" isn't actually the name of this module.  However,
        # filenameToModule can't seem to figure that out.  So clean up this
        # mis-named module.  It would be better if this weren't necessary
        # and filenameToModule either didn't exist or added a correctly
        # named module to sys.modules.
        self.addCleanup(sys.modules.pop, 'test_sample', None)

        self.mangleSysPath(self.oldPath)
        sample1 = runner.filenameToModule(
            os.path.join(self.parent, 'goodpackage', 'test_sample.py'))
        self.mangleSysPath(self.newPath)
        from goodpackage import test_sample as sample2
        self.assertEqual(os.path.splitext(sample2.__file__)[0],
                             os.path.splitext(sample1.__file__)[0])


    def test_packageInPath(self):
        package1 = runner.filenameToModule(os.path.join(self.parent,
                                                        'goodpackage'))
        import goodpackage
        self.assertEqual(goodpackage, package1)


    def test_packageNotInPath(self):
        """
        If passed the path to a directory which represents a package which
        is not on the import path, L{runner.filenameToModule} returns a
        module object loosely resembling the package defined by that
        directory anyway.
        """
        # "__init__" isn't actually the name of the package!  However,
        # filenameToModule is pretty stupid and decides that is its name
        # after all.  Make sure it gets cleaned up.  See the comment in
        # test_moduleNotInPath for possible courses of action related to
        # this.
        self.addCleanup(sys.modules.pop, "__init__")

        self.mangleSysPath(self.oldPath)
        package1 = runner.filenameToModule(
            os.path.join(self.parent, 'goodpackage'))
        self.mangleSysPath(self.newPath)
        import goodpackage
        self.assertEqual(os.path.splitext(goodpackage.__file__)[0],
                             os.path.splitext(package1.__file__)[0])


    def test_directoryNotPackage(self):
        self.failUnlessRaises(ValueError, runner.filenameToModule,
                              util.sibpath(__file__, 'directory'))

    def test_filenameNotPython(self):
        self.failUnlessRaises(ValueError, runner.filenameToModule,
                              util.sibpath(__file__, 'notpython.py'))

    def test_filenameMatchesPackage(self):
        filename = os.path.join(self.parent, 'goodpackage.py')
        fd = open(filename, 'w')
        fd.write(packages.testModule)
        fd.close()
        try:
            module = runner.filenameToModule(filename)
            self.assertEqual(filename, module.__file__)
        finally:
            os.remove(filename)

    def test_directory(self):
        """
        Test loader against a filesystem directory. It should handle
        'path' and 'path/' the same way.
        """
        path  = util.sibpath(__file__, 'goodDirectory')
        os.mkdir(path)
        f = file(os.path.join(path, '__init__.py'), "w")
        f.close()
        try:
            module = runner.filenameToModule(path)
            self.assert_(module.__name__.endswith('goodDirectory'))
            module = runner.filenameToModule(path + os.path.sep)
            self.assert_(module.__name__.endswith('goodDirectory'))
        finally:
            shutil.rmtree(path)



class LoaderTest(packages.SysPathManglingTest):
    """
    Tests for L{trial.TestLoader}.
    """

    def setUp(self):
        self.loader = runner.TestLoader()
        packages.SysPathManglingTest.setUp(self)


    def test_sortCases(self):
        import sample
        suite = self.loader.loadClass(sample.AlphabetTest)
        self.assertEqual(['test_a', 'test_b', 'test_c'],
                             [test._testMethodName for test in suite._tests])
        newOrder = ['test_b', 'test_c', 'test_a']
        sortDict = dict(zip(newOrder, range(3)))
        self.loader.sorter = lambda x : sortDict.get(x.shortDescription(), -1)
        suite = self.loader.loadClass(sample.AlphabetTest)
        self.assertEqual(newOrder,
                             [test._testMethodName for test in suite._tests])


    def test_loadMethod(self):
        import sample
        suite = self.loader.loadMethod(sample.FooTest.test_foo)
        self.assertEqual(1, suite.countTestCases())
        self.assertEqual('test_foo', suite._testMethodName)


    def test_loadFailingMethod(self):
        # test added for issue1353
        import erroneous
        suite = self.loader.loadMethod(erroneous.TestRegularFail.test_fail)
        result = reporter.TestResult()
        suite.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 1)


    def test_loadNonMethod(self):
        import sample
        self.failUnlessRaises(TypeError, self.loader.loadMethod, sample)
        self.failUnlessRaises(TypeError,
                              self.loader.loadMethod, sample.FooTest)
        self.failUnlessRaises(TypeError, self.loader.loadMethod, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadMethod, ('foo', 'bar'))


    def test_loadBadDecorator(self):
        """
        A decorated test method for which the decorator has failed to set the
        method's __name__ correctly is loaded and its name in the class scope
        discovered.
        """
        import sample
        suite = self.loader.loadMethod(sample.DecorationTest.test_badDecorator)
        self.assertEqual(1, suite.countTestCases())
        self.assertEqual('test_badDecorator', suite._testMethodName)


    def test_loadGoodDecorator(self):
        """
        A decorated test method for which the decorator has set the method's
        __name__ correctly is loaded and the only name by which it goes is used.
        """
        import sample
        suite = self.loader.loadMethod(
            sample.DecorationTest.test_goodDecorator)
        self.assertEqual(1, suite.countTestCases())
        self.assertEqual('test_goodDecorator', suite._testMethodName)


    def test_loadRenamedDecorator(self):
        """
        Load a decorated method which has been copied to a new name inside the
        class.  Thus its __name__ and its key in the class's __dict__ no
        longer match.
        """
        import sample
        suite = self.loader.loadMethod(
            sample.DecorationTest.test_renamedDecorator)
        self.assertEqual(1, suite.countTestCases())
        self.assertEqual('test_renamedDecorator', suite._testMethodName)


    def test_loadClass(self):
        import sample
        suite = self.loader.loadClass(sample.FooTest)
        self.assertEqual(2, suite.countTestCases())
        self.assertEqual(['test_bar', 'test_foo'],
                             [test._testMethodName for test in suite._tests])


    def test_loadNonClass(self):
        import sample
        self.failUnlessRaises(TypeError, self.loader.loadClass, sample)
        self.failUnlessRaises(TypeError,
                              self.loader.loadClass, sample.FooTest.test_foo)
        self.failUnlessRaises(TypeError, self.loader.loadClass, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadClass, ('foo', 'bar'))


    def test_loadNonTestCase(self):
        import sample
        self.failUnlessRaises(ValueError, self.loader.loadClass,
                              sample.NotATest)


    def test_loadModule(self):
        import sample
        suite = self.loader.loadModule(sample)
        self.assertEqual(10, suite.countTestCases())


    def test_loadNonModule(self):
        import sample
        self.failUnlessRaises(TypeError,
                              self.loader.loadModule, sample.FooTest)
        self.failUnlessRaises(TypeError,
                              self.loader.loadModule, sample.FooTest.test_foo)
        self.failUnlessRaises(TypeError, self.loader.loadModule, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadModule, ('foo', 'bar'))


    def test_loadPackage(self):
        import goodpackage
        suite = self.loader.loadPackage(goodpackage)
        self.assertEqual(7, suite.countTestCases())


    def test_loadNonPackage(self):
        import sample
        self.failUnlessRaises(TypeError,
                              self.loader.loadPackage, sample.FooTest)
        self.failUnlessRaises(TypeError,
                              self.loader.loadPackage, sample.FooTest.test_foo)
        self.failUnlessRaises(TypeError, self.loader.loadPackage, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadPackage, ('foo', 'bar'))


    def test_loadModuleAsPackage(self):
        import sample
        ## XXX -- should this instead raise a ValueError? -- jml
        self.failUnlessRaises(TypeError, self.loader.loadPackage, sample)


    def test_loadPackageRecursive(self):
        import goodpackage
        suite = self.loader.loadPackage(goodpackage, recurse=True)
        self.assertEqual(14, suite.countTestCases())


    def test_loadAnythingOnModule(self):
        import sample
        suite = self.loader.loadAnything(sample)
        self.assertEqual(sample.__name__,
                             suite._tests[0]._tests[0].__class__.__module__)


    def test_loadAnythingOnClass(self):
        import sample
        suite = self.loader.loadAnything(sample.FooTest)
        self.assertEqual(2, suite.countTestCases())


    def test_loadAnythingOnMethod(self):
        import sample
        suite = self.loader.loadAnything(sample.FooTest.test_foo)
        self.assertEqual(1, suite.countTestCases())


    def test_loadAnythingOnPackage(self):
        import goodpackage
        suite = self.loader.loadAnything(goodpackage)
        self.failUnless(isinstance(suite, self.loader.suiteFactory))
        self.assertEqual(7, suite.countTestCases())


    def test_loadAnythingOnPackageRecursive(self):
        import goodpackage
        suite = self.loader.loadAnything(goodpackage, recurse=True)
        self.failUnless(isinstance(suite, self.loader.suiteFactory))
        self.assertEqual(14, suite.countTestCases())


    def test_loadAnythingOnString(self):
        # the important thing about this test is not the string-iness
        # but the non-handledness.
        self.failUnlessRaises(TypeError,
                              self.loader.loadAnything, "goodpackage")


    def test_importErrors(self):
        import package
        suite = self.loader.loadPackage(package, recurse=True)
        result = reporter.Reporter()
        suite.run(result)
        self.assertEqual(False, result.wasSuccessful())
        self.assertEqual(2, len(result.errors))
        errors = [test.id() for test, error in result.errors]
        errors.sort()
        self.assertEqual(errors, ['package.test_bad_module',
                                      'package.test_import_module'])


    def test_differentInstances(self):
        """
        L{TestLoader.loadClass} returns a suite with each test method
        represented by a different instances of the L{TestCase} they are
        defined on.
        """
        class DistinctInstances(unittest.TestCase):
            def test_1(self):
                self.first = 'test1Run'

            def test_2(self):
                self.assertFalse(hasattr(self, 'first'))

        suite = self.loader.loadClass(DistinctInstances)
        result = reporter.Reporter()
        suite.run(result)
        self.assertTrue(result.wasSuccessful())


    def test_loadModuleWith_test_suite(self):
        """
        Check that C{test_suite} is used when present and other L{TestCase}s are
        not included.
        """
        from twisted.trial.test import mockcustomsuite
        suite = self.loader.loadModule(mockcustomsuite)
        self.assertEqual(0, suite.countTestCases())
        self.assertEqual("MyCustomSuite", getattr(suite, 'name', None))


    def test_loadModuleWith_testSuite(self):
        """
        Check that C{testSuite} is used when present and other L{TestCase}s are
        not included.
        """
        from twisted.trial.test import mockcustomsuite2
        suite = self.loader.loadModule(mockcustomsuite2)
        self.assertEqual(0, suite.countTestCases())
        self.assertEqual("MyCustomSuite", getattr(suite, 'name', None))


    def test_loadModuleWithBothCustom(self):
        """
        Check that if C{testSuite} and C{test_suite} are both present in a
        module then C{testSuite} gets priority.
        """
        from twisted.trial.test import mockcustomsuite3
        suite = self.loader.loadModule(mockcustomsuite3)
        self.assertEqual('testSuite', getattr(suite, 'name', None))


    def test_customLoadRaisesAttributeError(self):
        """
        Make sure that any C{AttributeError}s raised by C{testSuite} are not
        swallowed by L{TestLoader}.
        """
        def testSuite():
            raise AttributeError('should be reraised')
        from twisted.trial.test import mockcustomsuite2
        mockcustomsuite2.testSuite, original = (testSuite,
                                                mockcustomsuite2.testSuite)
        try:
            self.assertRaises(AttributeError, self.loader.loadModule,
                              mockcustomsuite2)
        finally:
            mockcustomsuite2.testSuite = original


    # XXX - duplicated and modified from test_script
    def assertSuitesEqual(self, test1, test2):
        names1 = testNames(test1)
        names2 = testNames(test2)
        names1.sort()
        names2.sort()
        self.assertEqual(names1, names2)


    def test_loadByNamesDuplicate(self):
        """
        Check that loadByNames ignores duplicate names
        """
        module = 'twisted.trial.test.test_test_visitor'
        suite1 = self.loader.loadByNames([module, module], True)
        suite2 = self.loader.loadByName(module, True)
        self.assertSuitesEqual(suite1, suite2)


    def test_loadDifferentNames(self):
        """
        Check that loadByNames loads all the names that it is given
        """
        modules = ['goodpackage', 'package.test_module']
        suite1 = self.loader.loadByNames(modules)
        suite2 = runner.TestSuite(map(self.loader.loadByName, modules))
        self.assertSuitesEqual(suite1, suite2)

    def test_loadInheritedMethods(self):
        """
        Check that test methods names which are inherited from are all
        loaded rather than just one.
        """
        methods = ['inheritancepackage.test_x.A.test_foo',
                   'inheritancepackage.test_x.B.test_foo']
        suite1 = self.loader.loadByNames(methods)
        suite2 = runner.TestSuite(map(self.loader.loadByName, methods))
        self.assertSuitesEqual(suite1, suite2)
        


class ZipLoadingTest(LoaderTest):
    def setUp(self):
        from twisted.test.test_paths import zipit
        LoaderTest.setUp(self)
        zipit(self.parent, self.parent+'.zip')
        self.parent += '.zip'
        self.mangleSysPath(self.oldPath+[self.parent])



class PackageOrderingTest(packages.SysPathManglingTest):
    if sys.version_info < (2, 4):
        skip = (
            "Python 2.3 import semantics make this behavior incorrect on that "
            "version of Python as well as difficult to test.  The second "
            "import of a package which raised an exception the first time it "
            "was imported will succeed on Python 2.3, whereas it will fail on "
            "later versions of Python.  Trial does not account for this, so "
            "this test fails with inconsistencies between the expected and "
            "the received loader errors.")

    def setUp(self):
        self.loader = runner.TestLoader()
        self.topDir = self.mktemp()
        parent = os.path.join(self.topDir, "uberpackage")
        os.makedirs(parent)
        file(os.path.join(parent, "__init__.py"), "wb").close()
        packages.SysPathManglingTest.setUp(self, parent)
        self.mangleSysPath(self.oldPath + [self.topDir])

    def _trialSortAlgorithm(self, sorter):
        """
        Right now, halfway by accident, trial sorts like this:

            1. all modules are grouped together in one list and sorted.

            2. within each module, the classes are grouped together in one list
               and sorted.

            3. finally within each class, each test method is grouped together
               in a list and sorted.

        This attempts to return a sorted list of testable thingies following
        those rules, so that we can compare the behavior of loadPackage.

        The things that show as 'cases' are errors from modules which failed to
        import, and test methods.  Let's gather all those together.
        """
        pkg = getModule('uberpackage')
        testModules = []
        for testModule in pkg.walkModules():
            if testModule.name.split(".")[-1].startswith("test_"):
                testModules.append(testModule)
        sortedModules = sorted(testModules, key=sorter) # ONE
        for modinfo in sortedModules:
            # Now let's find all the classes.
            module = modinfo.load(None)
            if module is None:
                yield modinfo
            else:
                testClasses = []
                for attrib in modinfo.iterAttributes():
                    if runner.isTestCase(attrib.load()):
                        testClasses.append(attrib)
                sortedClasses = sorted(testClasses, key=sorter) # TWO
                for clsinfo in sortedClasses:
                    testMethods = []
                    for attr in clsinfo.iterAttributes():
                        if attr.name.split(".")[-1].startswith('test'):
                            testMethods.append(attr)
                    sortedMethods = sorted(testMethods, key=sorter) # THREE
                    for methinfo in sortedMethods:
                        yield methinfo


    def loadSortedPackages(self, sorter=runner.name):
        """
        Verify that packages are loaded in the correct order.
        """
        import uberpackage
        self.loader.sorter = sorter
        suite = self.loader.loadPackage(uberpackage, recurse=True)
        # XXX: Work around strange, unexplained Zope crap.
        # jml, 2007-11-15.
        suite = unittest.decorate(suite, ITestCase)
        resultingTests = list(unittest._iterateTests(suite))
        manifest = list(self._trialSortAlgorithm(sorter))
        for number, (manifestTest, actualTest) in enumerate(
            zip(manifest, resultingTests)):
            self.assertEqual(
                 manifestTest.name, actualTest.id(),
                 "#%d: %s != %s" %
                 (number, manifestTest.name, actualTest.id()))
        self.assertEqual(len(manifest), len(resultingTests))


    def test_sortPackagesDefaultOrder(self):
        self.loadSortedPackages()


    def test_sortPackagesSillyOrder(self):
        def sillySorter(s):
            # This has to work on fully-qualified class names and class
            # objects, which is silly, but it's the "spec", such as it is.
#             if isinstance(s, type) or isinstance(s, types.ClassType):
#                 return s.__module__+'.'+s.__name__
            n = runner.name(s)
            d = md5(n).hexdigest()
            return d
        self.loadSortedPackages(sillySorter)
