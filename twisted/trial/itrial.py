#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import zope.interface as zi


class ITestCase(zi.Interface):
    def setUp():
        """I am run before each method is run"""

    def tearDown():
        """I am run after each method is run"""


class IReporter(zi.Interface):
    """I report results from a run of a test suite.

    In all lists below, 'Results' are either a twisted.python.failure.Failure
    object, or a string.
    """

    stream = zi.Attribute("@ivar stream: the io-stream that this reporter will write to")
    tbformat = zi.Attribute("@ivar tbformat: either 'default', 'brief', or 'verbose'")
    args = zi.Attribute("@ivar args: additional string argument passed from the command line")
    shouldStop = zi.Attribute("@ivar shouldStop: a boolean indicating that"
                              " this reporter would like the test run to stop.")

    def startTest(method):
        """report the beginning of a run of a single test method
        @param method: an object that is adaptable to ITestMethod
        """

    def stopTest(method):
        """report the status of a single test method
        @param method: an object that is adaptable to ITestMethod
        """

    def startSuite(name):
        """suites which wish to appear in reporter output should call this
        before running their tests"""

    def endSuite(name):
        """called at the end of a suite, if and only if that suite has called
        'startSuite'
        """

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

    def addSuccess(test):
        """Record that test passed."""


