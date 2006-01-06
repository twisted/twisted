import sys, os
from twisted.python import util
from twisted.trial.test import packages
from twisted.trial import unittest
from twisted.trial import runner, reporter


class FinderTest(packages.PackageTest):
    def setUp(self):
        packages.PackageTest.setUp(self)
        self.loader = runner.TestLoader()

    def tearDown(self):
        packages.PackageTest.tearDown(self)

    def test_findPackage(self):
        sample1 = self.loader.findByName('twisted')
        import twisted as sample2
        self.failUnlessEqual(sample1, sample2)
    
    def test_findModule(self):
        sample1 = self.loader.findByName('twisted.trial.test.sample')
        import sample as sample2
        self.failUnlessEqual(sample1, sample2)

    def test_findFile(self):
        path = util.sibpath(__file__, 'sample.py')
        sample1 = self.loader.findByName(path)
        import sample as sample2
        self.failUnlessEqual(sample1, sample2)

    def test_findObject(self):
        sample1 = self.loader.findByName('twisted.trial.test.sample.FooTest')
        import sample
        self.failUnlessEqual(sample.FooTest, sample1)

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
        
        
class FileTest(packages.PackageTest):
    parent = '_test_loader_FileTest'
    
    def setUp(self):
        self.oldPath = sys.path[:]
        sys.path.append(self.parent)
        packages.PackageTest.setUp(self, self.parent)

    def tearDown(self):
        packages.PackageTest.tearDown(self, self.parent)
        sys.path = self.oldPath

    def test_notFile(self):
        self.failUnlessRaises(ValueError,
                              runner.filenameToModule, 'doesntexist')

    def test_moduleInPath(self):
        sample1 = runner.filenameToModule(util.sibpath(__file__, 'sample.py'))
        import sample as sample2
        self.failUnlessEqual(sample2, sample1)

    def test_moduleNotInPath(self):
        sys.path, newPath = self.oldPath, sys.path
        sample1 = runner.filenameToModule(os.path.join(self.parent,
                                                       'goodpackage',
                                                       'test_sample.py'))
        sys.path = newPath
        from goodpackage import test_sample as sample2
        self.failUnlessEqual(os.path.splitext(sample2.__file__)[0],
                             os.path.splitext(sample1.__file__)[0])

    def test_packageInPath(self):
        package1 = runner.filenameToModule(os.path.join(self.parent,
                                                        'goodpackage'))
        import goodpackage
        self.failUnlessEqual(goodpackage, package1)

    def test_packageNotInPath(self):
        sys.path, newPath = self.oldPath, sys.path
        package1 = runner.filenameToModule(os.path.join(self.parent,
                                                        'goodpackage'))
        sys.path = newPath
        import goodpackage
        self.failUnlessEqual(os.path.splitext(goodpackage.__file__)[0],
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
            self.failUnlessEqual(filename, module.__file__)
        finally:
            os.remove(filename)


class LoaderTest(packages.PackageTest):
    parent = '_test_loader'
    
    def setUp(self):
        self.loader = runner.TestLoader()
        self.oldPath = sys.path[:]
        sys.path.append(self.parent)
        packages.PackageTest.setUp(self, self.parent)

    def tearDown(self):
        sys.path = self.oldPath
        packages.PackageTest.tearDown(self, self.parent)

    def test_sortCases(self):
        import sample
        suite = self.loader.loadClass(sample.AlphabetTest)
        self.failUnlessEqual(['test_a', 'test_b', 'test_c'],
                             [test._testMethodName for test in suite._tests])
        newOrder = ['test_b', 'test_c', 'test_a']
        sortDict = dict(zip(newOrder, range(3)))
        self.loader.sorter = lambda x : sortDict.get(x.shortDescription(), -1)
        suite = self.loader.loadClass(sample.AlphabetTest)
        self.failUnlessEqual(newOrder,
                             [test._testMethodName for test in suite._tests])

    def test_loadMethod(self):
        import sample
        suite = self.loader.loadMethod(sample.FooTest.test_foo)
        self.failUnlessEqual(1, suite.countTestCases())
        self.failUnlessEqual('test_foo', suite._testMethodName)

    def test_loadFailingMethod(self):
        # test added for issue1353
        from twisted.trial import reporter
        import erroneous
        suite = self.loader.loadMethod(erroneous.TestRegularFail.test_fail)
        result = reporter.TestResult()
        suite.run(result)
        self.failUnlessEqual(result.testsRun, 1)
        self.failUnlessEqual(len(result.failures), 1)

    def test_loadNonMethod(self):
        import sample
        self.failUnlessRaises(TypeError, self.loader.loadMethod, sample)
        self.failUnlessRaises(TypeError,
                              self.loader.loadMethod, sample.FooTest)
        self.failUnlessRaises(TypeError, self.loader.loadMethod, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadMethod, ('foo', 'bar'))

    def test_loadClass(self):
        import sample
        suite = self.loader.loadClass(sample.FooTest)
        self.failUnlessEqual(2, suite.countTestCases())
        self.failUnlessEqual(['test_bar', 'test_foo'],
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
        self.failUnlessEqual(7, suite.countTestCases())

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
        self.failUnlessEqual(7, suite.countTestCases())

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
        self.failUnlessEqual(14, suite.countTestCases())

    def test_loadAnythingOnModule(self):
        import sample
        suite = self.loader.loadAnything(sample)
        self.failUnlessEqual(sample.__name__,
                             suite._tests[0]._tests[0].__class__.__module__)

    def test_loadAnythingOnClass(self):
        import sample
        suite = self.loader.loadAnything(sample.FooTest)
        self.failUnlessEqual(2, suite.countTestCases())
        
    def test_loadAnythingOnMethod(self):
        import sample
        suite = self.loader.loadAnything(sample.FooTest.test_foo)
        self.failUnlessEqual(1, suite.countTestCases())

    def test_loadAnythingOnPackage(self):
        import goodpackage
        suite = self.loader.loadAnything(goodpackage)
        self.failUnless(isinstance(suite, self.loader.suiteFactory))
        self.failUnlessEqual(7, suite.countTestCases())
        
    def test_loadAnythingOnPackageRecursive(self):
        import goodpackage
        suite = self.loader.loadAnything(goodpackage, recurse=True)
        self.failUnless(isinstance(suite, self.loader.suiteFactory))
        self.failUnlessEqual(14, suite.countTestCases())
        
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
        self.failUnlessEqual(False, result.wasSuccessful())
        self.failUnlessEqual(2, len(result.errors))
        errors = [test.id() for test, error in result.errors]
        errors.sort()
        self.failUnlessEqual(errors, ['package.test_bad_module',
                                      'package.test_import_module'])
