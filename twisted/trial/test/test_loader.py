import sys, os
from twisted.python import util
from twisted.trial import unittest
from twisted.trial import runner


class FinderTest(unittest.TestCase):
    def setUp(self):
        self.loader = runner.TestLoader()

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
        
        
class FileTest(unittest.TestCase):
    samplePath = util.sibpath(__file__, 'foo')

    def tearDown(self):
        importedModules = ['goodpackage',
                           'goodpackage.test_sample',
                           'test_sample',
                           'sample']
        for moduleName in importedModules:
            if sys.modules.has_key(moduleName):
                del sys.modules[moduleName]

    def test_notFile(self):
        self.failUnlessRaises(ValueError,
                              runner.filenameToModule, 'doesntexist')

    def test_moduleInPath(self):
        sample1 = runner.filenameToModule(util.sibpath(__file__, 'sample.py'))
        import sample as sample2
        self.failUnlessEqual(sample2, sample1)

    def test_moduleNotInPath(self):
        sample1 = runner.filenameToModule(os.path.join(self.samplePath,
                                                       'goodpackage',
                                                       'test_sample.py'))
        sys.path.append(self.samplePath)
        from goodpackage import test_sample as sample2
        try:
            self.failUnlessEqual(os.path.splitext(sample2.__file__)[0],
                                 os.path.splitext(sample1.__file__)[0])
        finally:
            sys.path.remove(self.samplePath)

    def test_packageInPath(self):
        sys.path.append(self.samplePath)
        try:
            package1 = runner.filenameToModule(os.path.join(self.samplePath,
                                                            'goodpackage'))
            import goodpackage
            self.failUnlessEqual(goodpackage, package1)
        finally:
            sys.path.remove(self.samplePath)

    def test_packageNotInPath(self):
        package1 = runner.filenameToModule(os.path.join(self.samplePath,
                                                        'goodpackage'))
        sys.path.append(self.samplePath)
        import goodpackage
        sys.path.remove(self.samplePath)
        self.failUnlessEqual(os.path.splitext(goodpackage.__file__)[0],
                             os.path.splitext(package1.__file__)[0])

    def test_directoryNotPackage(self):
        self.failUnlessRaises(ValueError, runner.filenameToModule,
                              self.samplePath)

    def test_filenameNotPython(self):
        self.failUnlessRaises(ValueError, runner.filenameToModule,
                              util.sibpath(__file__, 'notpython.py'))
    

class LoaderTest(unittest.TestCase):

    ## FIXME -- Need tests for:
    ## * loading packages that contain modules with errors
    ## * loading package recursively for packages that contain modules with
    ##   errors
    ## * loading with custom sorter
    ## * the default sort order (alphabetic)
    ## * loading doctests

    ## FIXME -- Need tests (and implementations) for:
    ## * Loading from a string
    ##   * could be a file / directory
    ##   * could be name of a python object

    samplePath = util.sibpath(__file__, 'foo')
    
    def setUp(self):
        self.loader = runner.TestLoader()
        sys.path.append(self.samplePath)

    def tearDown(self):
        sys.path.remove(self.samplePath)

    def test_loadMethod(self):
        import sample
        suite = self.loader.loadMethod(sample.FooTest.test_foo)
        self.failUnlessEqual(1, suite.countTestCases())
        self.failUnlessEqual(['test_foo'],
                             [test._testMethodName for test in suite._tests])
        self.failUnless(isinstance(suite, runner.ClassSuite),
                        "%r must be a runner.ClassSuite instance"
                        % (suite,))

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
        self.failUnless(isinstance(suite, runner.ClassSuite),
                        "%r must be a runner.ClassSuite instance"
                        % (suite,))

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
        self.failUnless(isinstance(suite, runner.ModuleSuite),
                        "%r must be a runner.ModuleSuite instance"
                        % (suite,))

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

    def test_loadPackageWithBadModules(self):
        import package
        suite = self.loader.loadPackage(package, recurse=True)
        importErrors = list(zip(*self.loader.getImportErrors())[0])
        importErrors.sort()
        self.failUnlessEqual(importErrors,
                             ['test_bad_module.py', 'test_import_module.py'])

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
        self.failUnless(isinstance(suite, self.loader.moduleSuiteFactory))
        self.failUnlessEqual(suite.original, sample)

    def test_loadAnythingOnClass(self):
        import sample
        suite = self.loader.loadAnything(sample.FooTest)
        self.failUnless(isinstance(suite, self.loader.classSuiteFactory),
                        '%r is not an instance of ClassSuite' % (suite,))
        self.failUnlessEqual(suite.original, sample.FooTest)
        self.failUnlessEqual(2, suite.countTestCases())
        
    def test_loadAnythingOnMethod(self):
        import sample
        suite = self.loader.loadAnything(sample.FooTest.test_foo)
        self.failUnless(isinstance(suite, self.loader.classSuiteFactory),
                        '%r is not an instance of ClassSuite' % (suite,))
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

