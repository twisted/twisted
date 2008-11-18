# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interfaces for Trial.

Maintainer: Jonathan Lange
"""

from zope.interface import Interface, Attribute

from twisted.plugin import IPlugin


class ITestCase(Interface):
    """
    The interface that a test case must implement in order to be used in Trial.
    """

    failureException = Attribute(
        "The exception class that is raised by failed assertions")


    def __call__(result):
        """
        Run the test. Should always do exactly the same thing as run().
        """


    def countTestCases():
        """
        Return the number of tests in this test case. Usually 1.
        """


    def id():
        """
        Return a unique identifier for the test, usually the fully-qualified
        Python name.
        """


    def run(result):
        """
        Run the test, storing the results in C{result}.

        @param result: A L{TestResult}.
        """


    def shortDescription():
        """
        Return a short description of the test.
        """



class IResult(Interface):
    """
    Receives events from tests and reports those results to the user or another
    computer.
    """

    testsRun = Attribute("The number of tests that have been run using this "
                         "reporter.")

    def startTest(test):
        """
        Report that the test C{test} has started to run.

        @param test: A unit test.
        @type test: Generally a L{unittest.TestCase}, but anything that behaves
        like L{TestCase} in the standard library module C{unittest}.
        """


    def stopTest(test):
        """
        Report that the test C{test} has finished running.

        @param test: A unit test.
        @type test: Generally a L{unittest.TestCase}, but anything that behaves
        like L{TestCase} in the standard library module C{unittest}.
        """


    def addSuccess(test):
        """
        Record that C{test} passed.
        """


    def addError(test, error):
        """
        Report that C{test} received an unexpected error.

        @param test: The test that received the error.
        @type test: Generally a L{unittest.TestCase}, but anything that behaves
        like L{TestCase} in the standard library module C{unittest}.

        @param error: The error that occurred.
        @type error: L{failure.Failure} or a L{sys.exc_info} tuple.
        """


    def addFailure(test, error):
        """
        Report that C{test} had a failed assertion.

        @param test: The test that failed.
        @type test: Generally a L{unittest.TestCase}, but anything that behaves
        like L{TestCase} in the standard library module C{unittest}.

        @param error: An error object representing the failed assertion.
        @type error: L{failure.Failure} or a L{sys.exc_info} tuple.
        """


    def addSkip(test, reason):
        """
        Report that the given test was not run at all.

        @param test: The test that failed.
        @type test: Generally a L{unittest.TestCase}, but anything that behaves
        like L{TestCase} in the standard library module C{unittest}.

        @param reason: A string explaining why the test was not run.
        @type reason: L{str}
        """


    def addUnexpectedSuccess(test, todo):
        """
        If C{test} was expected to fail, but succeeded, then this method will
        be called to indicate the unexpected success.

        @param test: The test that failed.
        @type test: Generally a L{unittest.TestCase}, but anything that behaves
        like L{TestCase} in the standard library module C{unittest}.

        # XXX - should just be a string
        @param todo: An object representing the reason for marking the test
        'todo'.
        @type todo: L{unittest.Todo}
        """


    def addExpectedFailure(test, error, todo):
        """
        If C{test} was marked as 'todo' and raised an expected error, then this
        method will be called.

        @param test: The test that failed.
        @type test: Generally a L{unittest.TestCase}, but anything that behaves
        like L{TestCase} in the standard library module C{unittest}.

        @param error: The expected error that was raised.
        @type error: L{failure.Failure} or a L{sys.exc_info} tuple.

        # XXX - should just be a string
        @param todo: An object representing the reason for marking the test
        'todo'.
        @type todo: L{unittest.Todo}
        """


class IResultPrinter(Interface):
    """
    Prints summaries of test results.
    """

    separator = Attribute('A string used to separate test errors.')


    def printErrors():
        """
        Print all non-success results.
        """


    def printSummary():
        """
        Print a summary of the test result, indicating whether it has been
        successful, how many tests passed, how many failed and so forth.
        """


    def write(format, *args):
        """
        Print the given format string using the supplied arguments.
        """


    def writeln(format, *args):
        """
        Print the given format string using the supplied arguments, followed by
        a newline.
        """



class IReporter(Interface):
    """DEPRECATED SINCE Twisted 2.6. DO NOT USE THIS INTERFACE.

    Use L{IResult} or I{IResultPrinter} instead.

    I report results from a run of a test suite.
    """

    stream = Attribute(
        "Deprecated in Twisted 8.0. "
        "The io-stream that this reporter will write to")
    tbformat = Attribute("Either 'default', 'brief', or 'verbose'")
    args = Attribute(
        "Additional string argument passed from the command line")
    shouldStop = Attribute(
        """
        A boolean indicating that this reporter would like the test run to stop.
        """)
    separator = Attribute(
        "Deprecated in Twisted 8.0. "
        "A value which will occasionally be passed to the L{write} method.")
    testsRun = Attribute(
        """
        The number of tests that seem to have been run according to this
        reporter.
        """)


    def startTest(method):
        """
        Report the beginning of a run of a single test method.

        @param method: an object that is adaptable to ITestMethod
        """


    def stopTest(method):
        """
        Report the status of a single test method

        @param method: an object that is adaptable to ITestMethod
        """


    def startSuite(name):
        """
        Deprecated in Twisted 8.0.

        Suites which wish to appear in reporter output should call this
        before running their tests.
        """


    def endSuite(name):
        """
        Deprecated in Twisted 8.0.

        Called at the end of a suite, if and only if that suite has called
        C{startSuite}.
        """


    def cleanupErrors(errs):
        """
        Deprecated in Twisted 8.0.

        Called when the reactor has been left in a 'dirty' state

        @param errs: a list of L{twisted.python.failure.Failure}s
        """


    def upDownError(userMeth, warn=True, printStatus=True):
        """
        Deprecated in Twisted 8.0.

        Called when an error occurs in a setUp* or tearDown* method

        @param warn: indicates whether or not the reporter should emit a
                     warning about the error
        @type warn: Boolean
        @param printStatus: indicates whether or not the reporter should
                            print the name of the method and the status
                            message appropriate for the type of error
        @type printStatus: Boolean
        """


    def addSuccess(test):
        """
        Record that test passed.
        """


    def addError(test, error):
        """
        Record that a test has raised an unexpected exception.

        @param test: The test that has raised an error.
        @param error: The error that the test raised. It will either be a
            three-tuple in the style of C{sys.exc_info()} or a
            L{Failure<twisted.python.failure.Failure>} object.
        """


    def addFailure(test, failure):
        """
        Record that a test has failed with the given failure.

        @param test: The test that has failed.
        @param failure: The failure that the test failed with. It will
            either be a three-tuple in the style of C{sys.exc_info()}
            or a L{Failure<twisted.python.failure.Failure>} object.
        """


    def addExpectedFailure(test, failure, todo):
        """
        Record that the given test failed, and was expected to do so.

        @type test: L{pyunit.TestCase}
        @param test: The test which this is about.
        @type error: L{failure.Failure}
        @param error: The error which this test failed with.
        @type todo: L{unittest.Todo}
        @param todo: The reason for the test's TODO status.
        """


    def addUnexpectedSuccess(test, todo):
        """
        Record that the given test failed, and was expected to do so.

        @type test: L{pyunit.TestCase}
        @param test: The test which this is about.
        @type todo: L{unittest.Todo}
        @param todo: The reason for the test's TODO status.
        """


    def addSkip(test, reason):
        """
        Record that a test has been skipped for the given reason.

        @param test: The test that has been skipped.
        @param reason: An object that the test case has specified as the reason
            for skipping the test.
        """


    def printSummary():
        """
        Deprecated in Twisted 8.0, use L{done} instead.

        Present a summary of the test results.
        """


    def printErrors():
        """
        Deprecated in Twisted 8.0, use L{done} instead.

        Present the errors that have occured during the test run. This method
        will be called after all tests have been run.
        """


    def write(string):
        """
        Deprecated in Twisted 8.0, use L{done} instead.

        Display a string to the user, without appending a new line.
        """


    def writeln(string):
        """
        Deprecated in Twisted 8.0, use L{done} instead.

        Display a string to the user, appending a new line.
        """


    def wasSuccessful():
        """
        Return a boolean indicating whether all test results that were reported
        to this reporter were successful or not.
        """


    def done():
        """
        Called when the test run is complete.

        This gives the result object an opportunity to display a summary of
        information to the user. Once you have called C{done} on an
        L{IReporter} object, you should assume that the L{IReporter} object is
        no longer usable.
        """



class IReporterPlugin(IPlugin):
    """
    This plugin interface allows 'reporters' (i.e. TestResult objects) to be
    added to the Trial command line.
    """

    name = Attribute('A single-word name used to identify the reporter. '
                     'Must be set to a unique string.')
    description = Attribute("A brief description of what the reporter does. "
                            'Ignored if set to None.')


    def makeReporter(options=None):
        """
        Return a new reporter.

        @param options: Options from the command line. By default, assumes there
        were no command-line options.
        @type options: dict

        @return: L{IResult} that can be adapted to L{IResultPrinter}.
        """
