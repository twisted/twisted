import StringIO, sys

from twisted.trial import unittest, runner, reporter, util
from twisted.trial.test import erroneous, suppression
    

class ResultsTestMixin:
    def loadSuite(self, suite):
        self.loader = runner.TestLoader()
        self.suite = self.loader.loadClass(suite)
        self.reporter = reporter.TestResult()

    def test_setUp(self):
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(self.reporter.skips, [])
        
    def assertCount(self, numTests):
        self.failUnlessEqual(self.suite.countTestCases(), numTests)
        self.suite(self.reporter)
        self.failUnlessEqual(self.reporter.testsRun, numTests)


class TestSkipMethods(unittest.TestCase, ResultsTestMixin):
    class SkippingTests(unittest.TestCase):
        def test_skip1(self):
            raise unittest.SkipTest('skip1')

        def test_skip2(self):
            raise RuntimeError("I should not get raised")
        test_skip2.skip = 'skip2'

        def test_skip3(self):
            self.fail('I should not fail')
        test_skip3.skip = 'skip3'

    class SkippingSetUp(unittest.TestCase):
        def setUp(self):
            raise unittest.SkipTest('skipSetUp')

        def test_1(self):
            pass

        def test_2(self):
            pass

    def setUp(self):
        self.loadSuite(TestSkipMethods.SkippingTests)

    def test_counting(self):
        self.assertCount(3)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(len(self.reporter.skips), 3)

    def test_setUp(self):
        self.loadSuite(TestSkipMethods.SkippingSetUp)
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(len(self.reporter.skips), 2)

    def test_reasons(self):
        self.suite(self.reporter)
        prefix = 'test_'
        # whiteboxing reporter 
        for test, reason in self.reporter.skips:
            self.failUnlessEqual(test.shortDescription()[len(prefix):],
                                 str(reason))


class TestSkipClasses(unittest.TestCase, ResultsTestMixin):
    class SkippedClass(unittest.TestCase):
        skip = 'class'
        def setUpClass(self):
            self.__class__._setUpClassRan = True
        def setUp(self):
            self.__class__._setUpRan = True
        def tearDownClass(self):
            self.__class__._tearDownClassRan = True
        def test_skip1(self):
            raise SkipTest('skip1')
        def test_skip2(self):
            raise RuntimeError("Ought to skip me")
        test_skip2.skip = 'skip2'
        def test_skip3(self):
            pass
        def test_skip4(self):
            raise RuntimeError("Skip me too")
        
    def setUp(self):
        self.loadSuite(TestSkipClasses.SkippedClass)
        TestSkipClasses.SkippedClass._setUpRan = False
        TestSkipClasses.SkippedClass._setUpClassRan = False
        TestSkipClasses.SkippedClass._tearDownClassRan = False

    def test_counting(self):
        self.assertCount(4)

    def test_setUpRan(self):
        self.suite(self.reporter)
        self.failUnlessEqual(TestSkipClasses.SkippedClass._setUpRan, False)
        self.failUnlessEqual(TestSkipClasses.SkippedClass._setUpClassRan,
                             False)
        self.failUnlessEqual(TestSkipClasses.SkippedClass._tearDownClassRan,
                             False)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(len(self.reporter.skips), 4)

    def test_reasons(self):
        self.suite(self.reporter)
        expectedReasons = ['class', 'skip2', 'class', 'class']
        # whitebox reporter
        reasonsGiven = [ reason for test, reason in self.reporter.skips ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)


class TestSkipClassesRaised(unittest.TestCase, ResultsTestMixin):
    class SkippedClass(unittest.TestCase):
        def setUpClass(self):
            raise unittest.SkipTest("class")
        def setUp(self):
            self.__class__._setUpRan = True
        def tearDownClass(self):
            self.__class__._tearDownClassRan = True
        def test_skip1(self):
            raise SkipTest('skip1')
        def test_skip2(self):
            raise RuntimeError("Ought to skip me")
        test_skip2.skip = 'skip2'
        def test_skip3(self):
            pass
        def test_skip4(self):
            raise RuntimeError("Skip me too")
        
    def setUp(self):
        if hasattr(TestSkipClassesRaised.SkippedClass, 'skip'):
            delattr(TestSkipClassesRaised.SkippedClass, 'skip')
        self.loadSuite(TestSkipClassesRaised.SkippedClass)
        TestSkipClassesRaised.SkippedClass._setUpRan = False
        TestSkipClassesRaised.SkippedClass._tearDownClassRan = False

    def test_counting(self):
        self.assertCount(4)

    def test_setUpRan(self):
        self.suite(self.reporter)
        self.failUnlessEqual(
            TestSkipClassesRaised.SkippedClass._setUpRan, False)

    def test_tearDownClassRan(self):
        self.suite(self.reporter)
        self.failUnlessEqual(
            TestSkipClassesRaised.SkippedClass._tearDownClassRan, False)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(len(self.reporter.skips), 4)

    def test_reasons(self):
        self.suite(self.reporter)
        expectedReasons = ['class', 'skip2', 'class', 'class']
        # whitebox reporter
        reasonsGiven = [ reason for test, reason in self.reporter.skips ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)


class TestTodo(unittest.TestCase, ResultsTestMixin):
    class TodoTests(unittest.TestCase):
        def test_todo1(self):
            self.fail("deliberate failure")
        test_todo1.todo = "todo1"

        def test_todo2(self):
            raise RuntimeError("deliberate error")
        test_todo2.todo = "todo2"

        def test_todo3(self):
            """unexpected success"""
        test_todo3.todo = 'todo3'

    def setUp(self):
        self.loadSuite(TestTodo.TodoTests)
    
    def test_counting(self):
        self.assertCount(3)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(self.reporter.skips, [])
        self.failUnlessEqual(len(self.reporter.expectedFailures), 2)
        self.failUnlessEqual(len(self.reporter.unexpectedSuccesses), 1)
    
    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['todo1', 'todo2']
        reasonsGiven = [ r.reason
                         for t, e, r in self.reporter.expectedFailures ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)
            
    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = ['todo3']
        reasonsGiven = [ r.reason
                         for t, r in self.reporter.unexpectedSuccesses ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)


class TestTodoClass(unittest.TestCase, ResultsTestMixin):
    class TodoClass(unittest.TestCase):
        def test_todo1(self):
            pass
        test_todo1.todo = "method"
        def test_todo2(self):
            pass
        def test_todo3(self):
            self.fail("Deliberate Failure")
        test_todo3.todo = "method"
        def test_todo4(self):
            self.fail("Deliberate Failure")        
    TodoClass.todo = "class"

    def setUp(self):
        self.loadSuite(TestTodoClass.TodoClass)

    def test_counting(self):
        self.assertCount(4)

    def test_results(self):
        self.suite(self.reporter)
        self.failUnless(self.reporter.wasSuccessful())
        self.failUnlessEqual(self.reporter.errors, [])
        self.failUnlessEqual(self.reporter.failures, [])
        self.failUnlessEqual(self.reporter.skips, [])
        self.failUnlessEqual(len(self.reporter.expectedFailures), 2)
        self.failUnlessEqual(len(self.reporter.unexpectedSuccesses), 2)
    
    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['method', 'class']
        reasonsGiven = [ r.reason
                         for t, e, r in self.reporter.expectedFailures ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)
            
    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = ['method', 'class']
        reasonsGiven = [ r.reason
                         for t, r in self.reporter.unexpectedSuccesses ]
        self.failUnlessEqual(expectedReasons, reasonsGiven)


class TestStrictTodo(unittest.TestCase, ResultsTestMixin):
    class Todos(unittest.TestCase):
        def test_todo1(self):
            raise RuntimeError, "expected failure"
        test_todo1.todo = (RuntimeError, "todo1")
        
        def test_todo2(self):
            raise RuntimeError, "expected failure"
        test_todo2.todo = ((RuntimeError, OSError), "todo2")
        
        def test_todo3(self):
            raise RuntimeError, "we had no idea!"
        test_todo3.todo = (OSError, "todo3")
        
        def test_todo4(self):
            raise RuntimeError, "we had no idea!"
        test_todo4.todo = ((OSError, SyntaxError), "todo4")
        
        def test_todo5(self):
            self.fail("deliberate failure")
        test_todo5.todo = (unittest.FailTest, "todo5")

        def test_todo6(self):
            self.fail("deliberate failure")
        test_todo6.todo = (RuntimeError, "todo6")

        def test_todo7(self):
            pass
        test_todo7.todo = (RuntimeError, "todo7")

    def setUp(self):
        self.loadSuite(TestStrictTodo.Todos)

    def test_counting(self):
        self.assertCount(7)

    def test_results(self):
        self.suite(self.reporter)
        self.failIf(self.reporter.wasSuccessful())
        self.failUnlessEqual(len(self.reporter.errors), 2)
        self.failUnlessEqual(len(self.reporter.failures), 1)
        self.failUnlessEqual(len(self.reporter.expectedFailures), 3)
        self.failUnlessEqual(len(self.reporter.unexpectedSuccesses), 1)
        self.failUnlessEqual(self.reporter.skips, [])

    def test_expectedFailures(self):
        self.suite(self.reporter)
        expectedReasons = ['todo1', 'todo2', 'todo5']
        reasonsGotten = [ r.reason
                          for t, e, r in self.reporter.expectedFailures ]
        self.failUnlessEqual(expectedReasons, reasonsGotten)

    def test_unexpectedSuccesses(self):
        self.suite(self.reporter)
        expectedReasons = [([RuntimeError], 'todo7')]
        reasonsGotten = [ (r.errors, r.reason)
                          for t, r in self.reporter.unexpectedSuccesses ]
        self.failUnlessEqual(expectedReasons, reasonsGotten)


class _CleanUpReporter(reporter.Reporter):
    def __init__(self):
        super(_CleanUpReporter, self).__init__(StringIO.StringIO(), 'default',
                                               False)

    def cleanupErrors(self, errs):
        self.cleanerrs = errs


class TestCleanup(unittest.TestCase):
    def setUp(self):
        self.result = _CleanUpReporter()
        self.loader = runner.TestLoader()

    def testLeftoverSockets(self):
        suite = self.loader.loadMethod(
            erroneous.SocketOpenTest.test_socketsLeftOpen)
        suite.run(self.result)
        self.assert_(self.result.cleanerrs)
        self.assert_(isinstance(self.result.cleanerrs.value,
                                util.DirtyReactorError))

    def testLeftoverPendingCalls(self):
        suite = erroneous.ReactorCleanupTests('test_leftoverPendingCalls')
        suite.run(self.result)
        self.assert_(self.result.cleanerrs)
        self.assert_(isinstance(self.result.cleanerrs.value,
                                util.PendingTimedCallsError))


class BogusReporter(reporter.Reporter):
    def __init__(self):
        super(BogusReporter, self).__init__(StringIO.StringIO(), 'default',
                                            False)

    def upDownError(self, method, error, warn, printStatus):
        super(BogusReporter, self).upDownError(method, error, False,
                                               printStatus)
        self.udeMethod = method


class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.reporter = BogusReporter()
        self.loader = runner.TestLoader()

    def testBrokenSetUp(self):
        self.loader.loadClass(erroneous.TestFailureInSetUp).run(self.reporter)
        imi = self.reporter.udeMethod
        self.assertEqual(imi, 'setUp')
        self.assert_(len(self.reporter.errors) > 0)
        self.assert_(isinstance(self.reporter.errors[0][1].value,
                                erroneous.FoolishError))

    def testBrokenTearDown(self):
        suite = self.loader.loadClass(erroneous.TestFailureInTearDown)
        suite.run(self.reporter)
        imi = self.reporter.udeMethod
        self.assertEqual(imi, 'tearDown')
        errors = self.reporter.errors
        self.assert_(len(errors) > 0)
        self.assert_(isinstance(errors[0][1].value, erroneous.FoolishError))

    def testBrokenSetUpClass(self):
        suite = self.loader.loadClass(erroneous.TestFailureInSetUpClass)
        suite.run(self.reporter)
        imi = self.reporter.udeMethod
        self.assertEqual(imi, 'setUpClass')
        self.assert_(self.reporter.errors)

    def testBrokenTearDownClass(self):
        suite = self.loader.loadClass(erroneous.TestFailureInTearDownClass)
        suite.run(self.reporter)
        imi = self.reporter.udeMethod
        self.assertEqual(imi, 'tearDownClass')


class FixtureMetaTest(unittest.TestCase):
    def test_testBrokenTearDownClass(self):
        """FixtureTest.testBrokenTearDownClass succeeds when run twice
        """
        test = FixtureTest('testBrokenTearDownClass')
        result = reporter.TestResult()
        test(result)
        self.failUnless(result.wasSuccessful())
        result2 = reporter.TestResult()
        test(result2)
        self.failUnless(result2.wasSuccessful())
        

class SuppressionTest(unittest.TestCase):
    def runTests(self, suite):
        suite.run(reporter.TestResult())
    
    def setUp(self):
        self.stream = StringIO.StringIO()
        self._stdout, sys.stdout = sys.stdout, self.stream
        self.loader = runner.TestLoader()

    def tearDown(self):
        sys.stdout = self._stdout
        self.stream = None
    
    def getIO(self):
        return self.stream.getvalue()

    def testSuppressMethod(self):
        self.runTests(self.loader.loadMethod(
            suppression.TestSuppression.testSuppressMethod))
        self.assertNotSubstring(suppression.METHOD_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.CLASS_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.MODULE_WARNING_MSG, self.getIO())

    def testSuppressClass(self):
        self.runTests(self.loader.loadMethod(
            suppression.TestSuppression.testSuppressClass))
        self.assertSubstring(suppression.METHOD_WARNING_MSG, self.getIO())
        self.assertNotSubstring(suppression.CLASS_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.MODULE_WARNING_MSG, self.getIO())

    def testSuppressModule(self):
        self.runTests(self.loader.loadMethod(
            suppression.TestSuppression2.testSuppressModule))
        self.assertSubstring(suppression.METHOD_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.CLASS_WARNING_MSG, self.getIO())
        self.assertNotSubstring(suppression.MODULE_WARNING_MSG, self.getIO())

    def testOverrideSuppressClass(self):
        self.runTests(self.loader.loadMethod(
            suppression.TestSuppression.testOverrideSuppressClass))
        self.assertSubstring(suppression.CLASS_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.MODULE_WARNING_MSG, self.getIO())
        self.assertSubstring(suppression.METHOD_WARNING_MSG, self.getIO())


