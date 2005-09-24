#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import zope.interface as zi


class ITodo(zi.Interface):
    """I allow for more fine-tuned descriptions of what types of errors or
    failures
    """
    types = zi.Attribute(
        """a tuple of Exception types that we expect the test to have, if the
        ITestMethod's .failures or .errors don't match these types, the test
        is an ERROR""")
    msg = zi.Attribute("""the .todo message""")

    def isExpected(exceptionType):
        """returns True if exceptionType is an expected failure type, False
        otherwise if .types is None, should always return True
        """

    def __add__(other):
        """returns .msg + other, for string concatenation"""


class ITestCase(zi.Interface):
    # when adapting a test method, this interface will give the proper
    # setUp and tearDown methods

    def setUpClass():
        """I am run once per TestCase class before any methods are run"""

    def tearDownClass():
        """I am run once per TestCase class after all methods are run"""

    def setUp():
        """I am run before each method is run"""

    def tearDown():
        """I am run after each method is run"""


class ITrialRoot(zi.Interface):
    """I collect test elements and do a comprehensive test-run"""

    methods = zi.Attribute(
        """@cvar methods: returns an iterator over all of the ITestMethods
                          this roots's ITestRunner objects have generated
                          during the test run
        @note: this attribute is dynamically generated. if you access it
               before the tests have been run, the results are undefined""")

    def addMethod(method):
        """Add a single method of a test case class to this test suite.
        @param method: the method to add to this test suite
        """

    def addTestClass(klass):
        """add a test class to this suite,
        @param klass: any class that implements twisted.trial.itrial.ITestCase
        """

    def addModule(module):
        """add all ITestCase classes from module to this test suite
        @param module: a module containing classes which implement
                       twisted.trial.itrial.ITestCase
        """
        
    def addPackage(package):
        """add all ITestCase classes from package to this test suite
        @param package: a package containing classes which implement
                        twisted.trial.itrial.ITestCase
        """

    def addPackageRecursive(package):
        """same as addPackage but recurse into sub-packages
        """

    def run(output, seed=None):
        """run this TestSuite and report to output"""


class ITestRunner(zi.Interface):
    testCaseInstance = zi.Attribute(
        """@ivar testCaseInstance: the instance of a TestCase subclass that
                                   we're running the tests for
        @type testCaseInstance: types.InstanceType""")

    setUpClass = zi.Attribute(
        """@ivar setUpClass: the setUpClass method of .testClassInstance
        @type setUpClass: types.MethodType""")

    tearDownClass = zi.Attribute(
        """@ivar tearDownClass: the tearDownClass method of .testClassInstance
        @type tearDownClass: types.MethodType""")

    ##########################################################################
    #
    # This will have to change, if modules are going to become adaptable to
    # ITestRunner

    methodNames = zi.Attribute(
        """@ivar methodNames: iteratable of the method names of the TestClass
        @type methodNames: an iterable object""")

    methods = zi.Attribute(
        """@ivar methods: the method objects of the ITestRunner
        @type methods: a list of types.MethodType""")

    methodsWithStatus = zi.Attribute(
        """@ivar methodsWithStatus: a dict of reporter.STATUS-es to lists of
                                    ITestMethods so that
                                    methodsWithStatus[PASS] would return a
                                    list of all tests that passed""")

    ##########################################################################

    def countTestCases():
        """Return the number of test cases in this test runner."""

    def runTests():
        """runs this test class"""

    def run(randomize, result):
        """run this test class but never raise exceptions."""


class ITestMethod(zi.Interface):
    """the interface for running a single TestCase test method"""
    status = zi.Attribute(
        """@ivar status: the reporter.STATUS of this test run
           @type status: str
           @notes: Status is determined according to the following rules:
               if the method is marked as todo and there is a failure or an
                  error, the status is EXPECTED_FAILURE
               if the method marked as a skip, the status is SKIP
               if the method's run had an error the status is ERROR
               if FailTest was raised during the method's run, the status is
                  FAILURE
               if the method is marked todo and there were no errors or
                  failures, the status is UNEXPECTED_SUCCESS
               if none of the above are true, then the status is SUCCESS

               these status-symbolic-constants are defined in the reporter
               module""")
                          
    todo = zi.Attribute(
        """@ivar todo: indicates whether or not this method has been marked
                    as 'todo'
        @type todo: this is the value of the .todo attribute, or None""")

    skip = zi.Attribute(
        """@ivar skip: indicates whether or not this method has been skipped,
                    same semantics as .todo
        @type skip: string
        @note: a TestMethod may raise SkipTest with a message, if so, this
               value takes precedence""")

    suppress = zi.Attribute("""XXX: ADD DOCUMENTATION""")

    timeout = zi.Attribute(
        "an integer indicating the maximum number of seconds to "
        "wait for Deferreds return from this method to fire.")

    failures = zi.Attribute(
        """@ivar failures: a list of all failures that occurred during the
                        run(s) of this test method
        @type failures: list of failure.Failures""")

    logevents = zi.Attribute(
        """@ivar logevents: log.msg and log.err events captured during the run
                         of this method
        @type logevents: list of dicts of strings

        Log events are stringified (with str()) in order to prevent bad
        interactions with the garbage collector.""")

    stdout = zi.Attribute("""@ivar stdout: the test method's writes to stdout
                             @type stdout: types.StringType""")

    stderr = zi.Attribute("""@ivar stderr: the test method's writes to stderr
                             @type stderr: types.StringType""")

    runs = zi.Attribute(
        """@ivar runs: the number of times this method has been run
        @type runs: int""")

    hasTbs = zi.Attribute(
        """@ivar hasTbs: True if this test method has errors or failures
        @type: Boolean""")

    # XXX: Update Docs ------------------------------------------
    def run(testCaseInstance):
        """I run the test method"""

    def countTestCases():
        """Return the number of test cases in this composite element."""
    # -----------------------------------------------------------


class IReporter(zi.Interface):
    """I report results from a run of a test suite.

    In all lists below, 'Results' are either a twisted.python.failure.Failure
    object, or a string.

    @note: implementors: methods such as startTest/endTest must perform an
    adaptation on the argument received to the proper interface.
    """
    debugger = zi.Attribute(
        """@ivar debugger: Run the debugger when encountering a failing test.
        @type debugger: bool""")

    stream = zi.Attribute("@ivar stream: the io-stream that this reporter will write to")
    tbformat = zi.Attribute("@ivar tbformat: either 'default', 'brief', or 'verbose'")
    args = zi.Attribute("@ivar args: additional string argument passed from the command line")

    def setUpReporter():
        """performs reporter setup"""

    def tearDownReporter():
        """performs reporter termination"""

    def reportImportError(name, exc):
        """report an import error
        @param name: the name that could not be imported
        @param exc: the exception
        @type exc: L{twisted.python.failure.Failure}
        """

    def startTest(method):
        """report the beginning of a run of a single test method
        @param method: an object that is adaptable to ITestMethod
        """

    def endTest(method):
        """report the status of a single test method
        @param method: an object that is adaptable to ITestMethod
        """

    def startSuite(expectedTests):
        # FIXME should be startTrial
        """kick off this trial run
        @param expectedTests: the number of tests we expect to run
        """

    def endSuite(suite):
        # FIXME should be endTrial
        """at the end of a test run report the overall status and print out
        any errors caught
        @param suite: an object implementing ITrialRoot, can be adapted to
                      ITestStats
        """

    def startClass(klass):
        "called at the beginning of each TestCase with the class"

    def endClass(klass):
        "called at the end of each TestCase with the class"

    def startModule(module):
        "called at the beginning of each module"

    def endModule(module):
        "called at the end of each module"

    def cleanupErrors(errs):
        """called when the reactor has been left in a 'dirty' state
        @param errs: a list of L{twisted.python.failure.Failure}s
        """

    def upDownError(userMeth, warn=True, printStatus=True):
        """called when an error occurs in a setUp* or tearDown* method
        @param warn: indicates whether or not the reporter should emit a
                     warning about the error
        @type warn: Boolean
        @param printStatus: indicates whether or not the reporter should
                            print the name of the method and the status
                            message appropriate for the type of error
        @type printStatus: Boolean
        """


class ITrialDebug(zi.Interface):
    """used internally as an argument to log.msg"""
