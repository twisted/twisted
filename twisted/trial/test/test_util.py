from twisted.internet import defer
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



class TestRunSequentially(unittest.TestCase):
    """
    Sometimes it is useful to be able to run an arbitrary list of callables,
    one after the other.

    When some of those callables can return Deferreds, things become complex.
    """

    def test_emptyList(self):
        """
        When asked to run an empty list of callables, runSequentially returns a
        successful Deferred that fires an empty list.
        """
        d = util._runSequentially([])
        d.addCallback(self.assertEqual, [])
        return d


    def test_singleSynchronousSuccess(self):
        """
        When given a callable that succeeds without returning a Deferred,
        include the return value in the results list, tagged with a SUCCESS
        flag.
        """
        d = util._runSequentially([lambda: None])
        d.addCallback(self.assertEqual, [(defer.SUCCESS, None)])
        return d


    def test_singleSynchronousFailure(self):
        """
        When given a callable that raises an exception, include a Failure for
        that exception in the results list, tagged with a FAILURE flag.
        """
        d = util._runSequentially([lambda: self.fail('foo')])
        def check(results):
            [(flag, fail)] = results
            fail.trap(self.failureException)
            self.assertEqual(fail.getErrorMessage(), 'foo')
            self.assertEqual(flag, defer.FAILURE)
        return d.addCallback(check)


    def test_singleAsynchronousSuccess(self):
        """
        When given a callable that returns a successful Deferred, include the
        result of the Deferred in the results list, tagged with a SUCCESS flag.
        """
        d = util._runSequentially([lambda: defer.succeed(None)])
        d.addCallback(self.assertEqual, [(defer.SUCCESS, None)])
        return d


    def test_singleAsynchronousFailure(self):
        """
        When given a callable that returns a failing Deferred, include the
        failure the results list, tagged with a FAILURE flag.
        """
        d = util._runSequentially([lambda: defer.fail(ValueError('foo'))])
        def check(results):
            [(flag, fail)] = results
            fail.trap(ValueError)
            self.assertEqual(fail.getErrorMessage(), 'foo')
            self.assertEqual(flag, defer.FAILURE)
        return d.addCallback(check)


    def test_callablesCalledInOrder(self):
        """
        Check that the callables are called in the given order, one after the
        other.
        """
        log = []
        deferreds = []

        def append(value):
            d = defer.Deferred()
            log.append(value)
            deferreds.append(d)
            return d

        d = util._runSequentially([lambda: append('foo'),
                                   lambda: append('bar')])

        # runSequentially should wait until the Deferred has fired before
        # running the second callable.
        self.assertEqual(log, ['foo'])
        deferreds[-1].callback(None)
        self.assertEqual(log, ['foo', 'bar'])

        # Because returning created Deferreds makes jml happy.
        deferreds[-1].callback(None)
        return d


    def test_continuesAfterError(self):
        """
        If one of the callables raises an error, then runSequentially continues
        to run the remaining callables.
        """
        d = util._runSequentially([lambda: self.fail('foo'), lambda: 'bar'])
        def check(results):
            [(flag1, fail), (flag2, result)] = results
            fail.trap(self.failureException)
            self.assertEqual(flag1, defer.FAILURE)
            self.assertEqual(fail.getErrorMessage(), 'foo')
            self.assertEqual(flag2, defer.SUCCESS)
            self.assertEqual(result, 'bar')
        return d.addCallback(check)


    def test_stopOnFirstError(self):
        """
        If the C{stopOnFirstError} option is passed to C{runSequentially}, then
        no further callables are called after the first exception is raised.
        """
        d = util._runSequentially([lambda: self.fail('foo'), lambda: 'bar'],
                                  stopOnFirstError=True)
        def check(results):
            [(flag1, fail)] = results
            fail.trap(self.failureException)
            self.assertEqual(flag1, defer.FAILURE)
            self.assertEqual(fail.getErrorMessage(), 'foo')
        return d.addCallback(check)


    def test_stripFlags(self):
        """
        If the C{stripFlags} option is passed to C{runSequentially} then the
        SUCCESS / FAILURE flags are stripped from the output. Instead, the
        Deferred fires a flat list of results containing only the results and
        failures.
        """
        d = util._runSequentially([lambda: self.fail('foo'), lambda: 'bar'],
                                  stripFlags=True)
        def check(results):
            [fail, result] = results
            fail.trap(self.failureException)
            self.assertEqual(fail.getErrorMessage(), 'foo')
            self.assertEqual(result, 'bar')
        return d.addCallback(check)
    test_stripFlags.todo = "YAGNI"
