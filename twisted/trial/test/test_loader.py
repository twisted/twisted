import sys
from twisted.python import util
from twisted.trial import unittest
from twisted.trial import runner, reporter

class LoaderTest(unittest.TestCase):

    ## FIXME -- Need tests for:
    ## * loading packages that contain modules with errors
    ## * loading package recursively for packages that contain modules with
    ##   errors
    ## * loading with custom sorter
    ## * the default sort order (alphabetic)
    ## * loading doctests

    ## FIXME -- Need tests (and implementations) for:
    ## * Loading from a file
    ##   * when it refers to a module (in sys.path and out of sys.path)
    ##   * when it refers to a package (in sys.path and out of sys.path,
    ##     a directory or __init__.py)
    ## * Loading from a string
    ##   * could be a file / directory
    ##   * could be name of a python object
    
    def setUp(self):
        self.reporter = reporter.Reporter()
        self.loader = runner.TestLoader(self.reporter)
        sys.path.append(util.sibpath(__file__, 'foo'))

    def tearDown(self):
        sys.path.pop()

    def test_loadMethod(self):
        import sample
        suite = self.loader.loadMethod(sample.FooTest.test_foo)
        self.failUnlessEqual(1, suite.countTestCases())
        self.failUnlessEqual([sample.FooTest.test_foo],
                             [test.original for test in suite._tests])
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
        self.failUnlessEqual([sample.FooTest.test_bar, sample.FooTest.test_foo],
                             [test.original for test in suite._tests])
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

