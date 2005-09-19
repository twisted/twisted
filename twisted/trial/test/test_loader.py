from twisted.trial import unittest
from twisted.trial import runner, reporter

class LoaderTest(unittest.TestCase):

    ## FIXME -- Need tests for:
    ## * loading package
    ##   * including packages that contain modules with errors
    ## * loading package recursively
    ##   * including packages that contain modules with errors
    ## * loading with custom sorter
    ## * the default sort order (alphabetic)
    ## * loading doctests
    ## * loading individual methods
    ## * the created suites are of the right kind
    ##   (e.g. ModuleSuite for modules)
    ## * Calling loadModule on a non-module
    ## * Calling loadClass on a non-class
    ## * Calling loadClass on a non-TestCase

    ## FIXME -- Need tests (and implementations) for:
    ## * loadAnything loads arbitrary python objects correctly
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

    def test_loadClass(self):
        import sample
        suite = self.loader.loadClass(sample.FooTest)
        self.failUnlessEqual(2, suite.countTestCases())
        self.failUnlessEqual([sample.FooTest.test_bar, sample.FooTest.test_foo],
                             [test.original for test in suite._tests])

    def test_loadModule(self):
        import sample
        suite = self.loader.loadModule(sample)
        self.failUnlessEqual(7, suite.countTestCases())
