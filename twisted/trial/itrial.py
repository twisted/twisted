#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import zope.interface as zi
import sys


class IMethodInfo(zi.Interface):
    klass = zi.Attribute(
        """@ivar klass: the class instance this method is bound to
        @type klass: types.InstanceType""")

    setUp = zi.Attribute(
        """@ivar setUp: the setUp method of the class that this method is
                        bound to
        @type setUp: types.MethodType""")

    tearDown = zi.Attribute(
        """@ivar tearDown: the tearDown of the class this method is bound to
        @type tearDown: types.MethodType""")

    method = zi.Attribute("""@ivar method: the test method in question
                             @type method: types.MethodType""")

    name = zi.Attribute("""@ivar name: the test method's name
                           @type name: string""")

    fullName = zi.Attribute("""@ivar fullName: the fully-qualified test-name
                               @type fullName: string""")

    errors = zi.Attribute(
        """@ivar errors: a list of all errors that occured during the run(s)
                         of this test method
        @type errors: list of failure.Failures""")


class IUserMethod(zi.Interface):
    """A wrapper around user-defined methods to allow for 'safe' execution
    and response to errors."""

    failure = zi.Attribute(
        """@ivar failure: a L{twisted.python.failure.Failure} object
        raised during the user-defined method's run""")

    def call(*a, **kw):
        """call the user-defined method with arguments (*a, **kw)
        if the user method returns a deferred, this method will wait for the
        result, or will call any registered errorHandlers.
        @return: self
        """
        
    def addErrback(callable, *a, **kw):
        """a method that will be called if and when an error occurs in the
        user-defined-method. It will be called callable(fail, *a, **kw),
        where fail is a L{twisted.python.failure.Failure} object.

        @return: self
        """


class IJanitor(zi.Interface):
    """I perform and handle cleanup operations for the test framework"""

    logErrCheck = zi.Attribute(
        """@cvar doLogErrCheck: perform check and cleanup of log.errs
        @type doLogErrCheck: Boolean""")

    cleanPending = zi.Attribute(
        """@cvar cleanPending: check and cleanup of left-over
                               reactor.DelayedCalls
        @type cleanPending: Boolean""")

    cleanThreads = zi.Attribute(
        """@cvar cleanThreads: perform cleanup of the reactor threadpool
        @type cleanThreads: Boolean""")

    cleanReactor = zi.Attribute(
        """@cvar cleanReactor: perform cleanup of reactor connections
        @type cleanReactor: Boolean""")

    postCase = zi.Attribute(
        """@cvar postCase: perform indicated cleanup after each TestCase has
                           run
        @type postCase: Boolean""")

    postMethod = zi.Attribute(
        """@cvar postMethod: perform indicated cleanup after each TestMethod
                             has run
        @type postMethod: Boolean""")

    def postMethodCleanup():
        """perform cleanup operations that were specified in my constructor
        for running after each ITestMethod
        @return: a sequence of L{twisted.python.failure.Failure} objects 
        """

    def postCaseCleanup():
        """perform cleanup operations that were specified in my constructor
        for running after each ITestCase
        @return: a sequence of L{twisted.python.failure.Failure} objects 
        """
        
class IBenchmark(zi.Interface):
    """an interface for running performance tests on a given TestCase"""
    pass

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


class ITestCaseFactory(zi.Interface):
    pass


class IPyUnitTCFactory(zi.Interface):
    pass



class ITimed(zi.Interface):
    startTime = zi.Attribute(
        """@ivar startTime: the time this event started
        @type startTime: types.FloatType in seconds-since-the-epoch""")

    endTime = zi.Attribute(
        """@ivar endTime: the time this event ended
        @type endTime: types.FloatType in seconds-since-the-epoch""")


class ITestSuite(ITimed):
    """I collect test elements and do a comprehensive test-run"""

    methods = zi.Attribute(
        """@cvar methods: returns an iterator over all of the ITestMethods
                          this TestSuite's ITestRunner objects have generated
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



class ITestRunner(ITimed):
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

    def runTests():
        """runs this test class"""

class IDocTestRunner(ITestRunner):
    """locates and runs doctests"""

class IReporterMethod(zi.Interface):
    """the subset of ITestMethod that is necessary for reporting"""

class ITestMethod(ITimed):
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
    # -----------------------------------------------------------

class IReporterFactory(zi.Interface):
    """I create reporters"""
    def __call__(self, stream=sys.stdout, tbformat='plain', args=None):
        """this translates to the Reporter class' __init__ method
        @param stream: the io-stream that this reporter will write to.
                       this is optional depending on the reporter, defaults to
                       L{sys.stdout}
        @param tbformat: either 'plain' or 'emacs'
                         this is also dependent on the reporter, defaults to
                         'plain'
        @param args: argument to the command-line parameter --reporter-arg
        @type args: types.StringType
        """

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

    stream = zi.Attribute("@ivar stream: L{twisted.trial.itrial.IReporterFactory}'s stream parameter")
    tbformat = zi.Attribute("@ivar tbformat: L{twisted.trial.itrial.IReporterFactory}'s tbformat parameter")
    args = zi.Attribute("@ivar args: L{twisted.trial.itrial.IReporterFactory}'s args parameter")

    def setUpReporter():
        """performs reporter setup, for example, connecting to a remote service
        @returns: L{twisted.internet.defer.Deferred}
        """

    def tearDownReporter():
        """performs reporter termination, for example, disconnecting from a
        remote service
        @returns: L{twisted.internet.defer.Deferred}
        """

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
        """kick off this trial run
        @param expectedTests: the number of tests we expect to run
        """

    def endSuite(suite):
        """at the end of a test run report the overall status and print out
        any errors caught
        @param suite: an object implementing ITestSuite, can be adapted to
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


class IRemoteReporter(IReporter):
    def connectToSlave(self):
        """connect to a BuildBot buildslave using pb. makes use of the value
        set in L{twisted.trial.itrial.IReporter.args}
        """

class ITestStats(zi.Interface):
    """data that is important for the reporter after test runs"""
    imports = zi.Attribute(
        """@ivar imports: Import errors encountered while assembling the test
                          suite.
        @type imports: List of objects adaptable to ITestMethod""")

    failures = zi.Attribute(
        """@ivar failures: Tests which have failed.
        @type failures: list of objects adaptable to ITestMethod""")

    numTests = zi.Attribute(
        """@ivar numTests: The number of tests I have reports for.
        @type numTests: int""")

    expectedFailures = zi.Attribute(
        """@ivar expectedFailures: Tests which failed but are marked as 'todo'
        @type expectedFailures: list of objects adaptable to ITestMethod""")

    unexpectedSuccesses = zi.Attribute(
        """@ivar unexpectedSuccesses: Tests which passed but are marked as
                                      'todo'
        @type unexpectedSuccesses: list of objects adaptable to ITestMethod""")

    errors = zi.Attribute(
        """@ivar errors: Tests which have encountered an error.
        @type errors: List of objects adaptable to ITestMethod""")

    skips = zi.Attribute(
        """@ivar skips: Tests which have been skipped.
        @type skips: List of objects adaptable to ITestMethod""")

    runningTime = zi.Attribute(
        """@ivar runningTime: how long this test took to run
        @type runningTime: float""")

    allPassed = zi.Attribute("""@ivar allPassed: did all the tests pass
                                @type allPassed: boolean""")


class IDocTestMethod(ITestMethod):
    """a DocTestMethod, which is basically an ITestMethod with a few extra 
    attributes specific to doctests (i.e. the filename and line number)
    """
    filename = zi.Attribute(
       """@ivar filename: the tail part (os.path.split(name)[1] part) 
       of the originating file name of this doctest""")

    fullname = zi.Attribute(
        """@ivar fullname: the repr() of the original doctest.DocTest object
                           (quite informative)""")
                            
    docstr = zi.Attribute(
        """@ivar docstr: a BIG FAT LIE! this value is what is printed when
        the reporter reports the beginning of this doctest (i.e. startMethod
        is called)
        @note: this HORRID HACK will be fixed sometime in the near future
               with the addition of IDisplayName or some such
        """)
    

class IJellied(zi.Interface):
    pass


class IUnjellied(zi.Interface):
    pass


class ITestError(zi.Interface):
    def __str__():
        """return the properly formatted error given the ITestMethod's
        status"""


class IImportError(ITestError):
    name = zi.Attribute(
        '@ivar name: the name of the module for which exception occured')
    exception = zi.Attribute('@ivar exception: either a twisted.python.failure.Failure or a 3-tuple exception')


class IOldSkoolInfo(zi.Interface):
    """a compatability interface to provide information JellyReporter needs
    from ITestMethods"""
    testClass = zi.Attribute("the test Class")
    method = zi.Attribute("the test method")
    resultType = zi.Attribute("ITestMethod.status")
    results = zi.Attribute("the appropriate results for the status of this test, a failure.Failure")

class IFormattedFailure(zi.Interface):
    """a properly formatted traceback as a string
    @rtype: types.StringType
    """

class IErrorReport(zi.Interface):
    """a fully formatted error report that appears in the summary of the report
    @rtype: types.StringType
    """

class IImportErrorReport(IErrorReport):
    """a fully formatted error report for import errors
    """

class ITrialDebug(zi.Interface):
    """used internally as an argument to log.msg"""

class IFormattedFailure(zi.Interface):
    """returns a string representing a traceback, but without trial's
    internals"""

class IModuleName(zi.Interface):
    """returns a string representing an object's module's fully-qualified name
    in the case of a string, returns just the string
    """

class IClassName(zi.Interface):
    """returns a string representing an object's 'owning' class or
    in the case of a string, returns just the string
    """

class IFQClassName(zi.Interface):
    """returns a string representing an object's 'owning' class'
    fully-qualified name or in the case of a string, returns just the string
    """

class IFQMethodName(zi.Interface):
    """returns a string representing an object's fully-qualified name"""
