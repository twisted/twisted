# -*- Python -*-

from __future__ import nested_scopes

__version__ = "$Revision: 1.4 $"[11:-2]

from twisted.python.compat import *
from twisted.trial import unittest
from StringIO import StringIO
import sys

class TestTraceback(unittest.TestCase):
    def testExtractTB(self):
        """Making sure unittest doesn't show up in traceback."""
        suite = unittest.TestSuite()
        testCase = self.FailingTest()
        reporter = unittest.Reporter()
        suite.runOneTest(testCase.__class__, testCase,
                         testCase.__class__.testThatWillFail,
                         reporter)
        klass, method, (eType, eVal, tb) = reporter.failures[0]
        stackList = unittest.extract_tb(tb)
        self.failUnlessEqual(len(stackList), 1)
        self.failUnlessEqual(stackList[0][2], 'testThatWillFail')

    # Hidden in here so the failing test doesn't get sucked into the bigsuite.
    class FailingTest(unittest.TestCase):
        def testThatWillFail(self):
            self.fail("Broken by design.")


###################
# trial.remote

from twisted.protocols import loopback
from twisted.trial import remote
from twisted.spread import banana, jelly

_negotiate = '\x01\x80\x04\x82none'
_encStart = '\x03\x80\x05\x82tuple\x05\x82start\x02\x80\x05\x82tuple\x01\x81'

class RemoteReporter:
    expectedTests = None
    def __init__(self):
        self.errors = []
        self.importErrors = []
        
    def remote_start(self, expectedTests, times=None):
        self.expectedTests = expectedTests

    def remote_reportResults(self, testClass, methodName, resultType,
                             results, times=None):
        assert resultType == unittest.ERROR
        if resultType == unittest.ERROR:
            self.errors.append((testClass, methodName, results))

    def remote_reportImportError(self, name, failure, times=None):
        self.importErrors.append((name, failure))

class OneShotDecoder(remote.DecodeReport):
    def expressionReceived(self, lst):
        remote.DecodeReport.expressionReceived(self, lst)
        self.transport.loseConnection()

class JellyReporterWithHook(remote.JellyReporter):
    
    def makeConnection(self, transport):
        remote.JellyReporter.makeConnection(self, transport)
        self._runHook()

class TestJellyReporter(unittest.TestCase):
    def setUp(self):
        self.stream = StringIO()
        self.reporter = remote.JellyReporter(self.stream)
        self.reporter.doSendTimes = False
        
    def testStart(self):
        self.reporter.start(1)
        self.failUnlessEqual(_negotiate + _encStart, self.stream.getvalue())

    def testError(self):
        try:
            monkey / 0
        except Exception:
            self.reporter.reportResults("aTestClass", "aMethod",
                                        unittest.ERROR,
                                        sys.exc_info())


class TestRemoteReporter(unittest.TestCase):
    def setUp(self):
        self.reporter = RemoteReporter()
        self.decoder = remote.DecodeReport(self.reporter)
        self.decoder.dataReceived(_negotiate)

    def testStart(self):
        self.decoder.dataReceived(_encStart)
        self.failUnlessEqual(self.reporter.expectedTests, 1)


class LoopbackTests(unittest.TestCase):
    def setUp(self):
        self.sendReporter = JellyReporterWithHook()

        self.reporter = RemoteReporter()
        self.decoder = OneShotDecoder(self.reporter)

    def testStart(self):
        self.sendReporter._runHook = lambda : self.sendReporter.start(1)
        loopback.loopback(self.sendReporter, self.decoder)
        self.failUnlessEqual(self.reporter.expectedTests, 1)

    def testError(self):
        try:
            monkey / 0
        except Exception:
            self.sendReporter._runHook = lambda : (
                self.sendReporter.reportResults("aTestClass", "aMethod",
                                                unittest.ERROR,
                                                sys.exc_info()))            
        loopback.loopback(self.sendReporter, self.decoder)
        self.failUnlessEqual(len(self.reporter.errors), 1)
        self.failUnlessEqual(self.reporter.errors[0][:2], ("aTestClass",
                                                           "aMethod"))
        f = self.reporter.errors[0][-1]
        self.failUnlessEqual(f.type, NameError)

    def testImportError(self):
        try:
            import nosuchmoduleasthis
        except ImportError, exc:
            self.sendReporter._runHook = lambda : (
                self.sendReporter.reportImportError("nosuchmoduleasthis", exc))
        loopback.loopback(self.sendReporter, self.decoder)
        self.failUnlessEqual(len(self.reporter.importErrors), 1)
        f = self.reporter.importErrors[0][-1]
        self.failUnlessEqual(self.reporter.importErrors[0][0],
                             "nosuchmoduleasthis")
        self.failUnlessEqual(f.type, ImportError)
