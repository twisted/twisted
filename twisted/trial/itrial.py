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

    def setUpReporter():
        """performs reporter setup. DEPRECATED"""

    def tearDownReporter():
        """performs reporter termination. DEPRECATED"""

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

    def stopTest(method):
        """report the status of a single test method
        @param method: an object that is adaptable to ITestMethod
        """

    def startTrial(expectedTests):
        """kick off this trial run
        @param expectedTests: the number of tests we expect to run
        """

    def endTrial(suite):
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

