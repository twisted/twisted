# -*- Python -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from __future__ import nested_scopes

__version__ = "$Revision: 1.16 $"[11:-2]

from twisted.python import reflect
from twisted.trial import unittest, reporter, util, runner
from StringIO import StringIO
import sys
import os

class TestTraceback(unittest.TestCase):
    def testExtractTB(self):
        """Making sure unittest doesn't show up in traceback."""
        suite = unittest.TestSuite()
        testCase = self.FailingTest()
        result = unittest.Tester(testCase.__class__, testCase,
                                 testCase.testThatWillFail,
                                 runner.runTest).run()
        failType, (eType, eVal, tb) = result
        stackList = util.extract_tb(tb)
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
        assert resultType == reporter.ERROR
        if resultType == reporter.ERROR:
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
                                        reporter.ERROR,
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
                                                reporter.ERROR,
                                                sys.exc_info()))            
        loopback.loopback(self.sendReporter, self.decoder)
        self.failUnlessEqual(len(self.reporter.errors), 1)
        self.failUnlessEqual(self.reporter.errors[0][:2], ("aTestClass",
                                                           "aMethod"))
        f = self.reporter.errors[0][-1]
        self.failUnlessEqual(f.type, reflect.qual(NameError))

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

class TestTests(unittest.TestCase):
    # first, the things we're going to test
    class Tests(unittest.TestCase):
        def __init__(self):
            self.setupRun = 0
            self.teardownRun = 0
        def setUp(self):
            self.setupRun += 1
        def tearDown(self):
            self.teardownRun += 1
        def testSuccess_pass(self):
            pass
        def testFail_fail(self):
            self.fail("failed")
        def testFailIf_pass(self):
            self.failIf(0, "failed")
        def testFailIf_fail(self):
            self.failIf(1, "failed")
        def testFailUnless_pass(self):
            self.failUnless(1, "failed")
        def testFailUnless_fail(self):
            self.failUnless(0, "failed")
        def testFailUnlessRaises_pass(self):
            def boom():
                raise ValueError
            self.failUnlessRaises(ValueError, boom)
        def testFailUnlessRaises1_fail(self):
            def boom():
                raise IndexError
            self.failUnlessRaises(ValueError, boom)
        def testFailUnlessRaises2_fail(self):
            def boom():
                pass
            self.failUnlessRaises(ValueError, boom)
        def testFailUnlessEqual_pass(self):
            self.failUnlessEqual(1, 1, "failed")
        def testFailUnlessEqual_fail(self):
            self.failUnlessEqual(1, 2, "failed")
        def testFailIfEqual_fail(self):
            self.failIfEqual(1, 1, "failed")
        def testFailIfEqual_pass(self):
            self.failIfEqual(1, 2, "failed")
        def testFailUnlessIdentical_pass(self):
            a = [1,2]
            b = a
            self.failUnlessIdentical(a, b, "failed")
        def testFailUnlessIdentical1_fail(self):
            a = [1,2]
            b = [1,2]
            self.failUnlessIdentical(a, b, "failed")
        def testFailUnlessIdentical2_fail(self):
            a = [1,2]
            b = [3,4]
            self.failUnlessIdentical(a, b, "failed")
        def testApproximates1_pass(self):
            a = 1.0
            b = 1.2
            self.assertApproximates(a, b, .3, "failed")
        def testApproximates2_pass(self):
            a = 1.0
            b = 1.2
            self.assertApproximates(b, a, .3, "failed")
        def testApproximates3_fail(self):
            a = 1.0
            b = 1.2
            self.assertApproximates(a, b, .1, "failed")
        def testApproximates4_fail(self):
            a = 1.0
            b = 1.2
            self.assertApproximates(b, a, .1, "failed")
        def testSkip1_skip(self):
            raise unittest.SkipTest("skip me")
        def testSkip2_skip(self):
            pass
        testSkip2_skip.skip = "skip me"
        def testTodo1_exfail(self):
            self.fail("deliberate failure")
        testTodo1_exfail.todo = "expected to fail"
        def testTodo2_exfail(self):
            raise ValueError
        testTodo2_exfail.todo = "expected to fail"
        def testTodo3_unexpass(self):
            pass # unexpected success
        testTodo3_unexpass.todo = "expected to fail"
        
            
            
    def checkResults(self, rep, method):
        self.failIf(rep.imports, "%s caused import error" % method)
        self.failUnless(rep.numTests == 1,
                        "%s had multiple tests" % method)
        if method[-5:] == "_pass":
            self.failIf(rep.errors)
            self.failIf(rep.failures)
            self.failIf(rep.skips)
            self.failIf(rep.expectedFailures)
            self.failIf(rep.unexpectedSuccesses)
        if method[-5:] == "_fail":
            self.failIf(rep.errors)
            self.failUnless(len(rep.failures) == 1,
                            "%s had %d failures" % (method,
                                                    len(rep.failures)))
            self.failIf(rep.skips)
            self.failIf(rep.expectedFailures)
            self.failIf(rep.unexpectedSuccesses)
        if method[-6:] == "_error":
            self.failUnless(len(rep.errors) == 1,
                            "%s had %d errors" % (method,
                                                  len(rep.errors)))
            self.failIf(rep.failures)
            self.failIf(rep.skips)
            self.failIf(rep.expectedFailures)
            self.failIf(rep.unexpectedSuccesses)
        if method[-5:] == "_skip":
            self.failIf(rep.errors)
            self.failIf(rep.failures)
            self.failUnless(len(rep.skips) == 1,
                            "%s had %d skips" % (method,
                                                 len(rep.skips)))
            self.failIf(rep.expectedFailures)
            self.failIf(rep.unexpectedSuccesses)
        if method[-7:] == "_exfail":
            self.failIf(rep.errors)
            self.failIf(rep.failures)
            self.failIf(rep.skips)
            self.failUnless(len(rep.expectedFailures) == 1,
                            "%s had %d expectedFailures" % \
                            (method, len(rep.expectedFailures)))
            self.failIf(rep.unexpectedSuccesses)
        if method[-9:] == "_unexpass":
            self.failIf(rep.errors)
            self.failIf(rep.failures)
            self.failIf(rep.skips)
            self.failIf(rep.expectedFailures)
            self.failUnless(len(rep.unexpectedSuccesses) == 1,
                            "%s had %d unexpectedSuccesses" % \
                            (method, len(rep.unexpectedSuccesses)))
        
    def testTests(self):
        suite = unittest.TestSuite()
        suffixes = reflect.prefixedMethodNames(TestTests.Tests, "test")
        for suffix in suffixes:
            method = "test" + suffix
            testCase = self.Tests()

            # if one of these test cases fails, switch to TextReporter to
            # see what happened

            rep = reporter.Reporter()
            #reporter = reporter.TextReporter()
            #print "running '%s'" % method

            rep.start(1)

            result = unittest.Tester(testCase.__class__, testCase,
                                     getattr(testCase, method),
                                     lambda x: x()).run()
            rep.reportResults(testCase.__class__, getattr(self.Tests, method),
                              *result)
            # TODO: verify that case.setUp == 1 and case.tearDown == 1
            try:
                self.checkResults(rep, method)
            except unittest.FailTest:
                # with TextReporter, this will show the traceback
                print
                print "problem in method '%s'" % method
                reporter.stop()
                raise
            
class UtilityTestCase(unittest.TestCase):
    def testMktmp(self):
        tmp = self.mktemp()
        tmp1 = self.mktemp()
        exp = os.path.join('twisted.test.test_trial', 'UtilityTestCase', 'testMktmp')
        self.failIfEqual(tmp, tmp1)
        self.failUnless(os.path.exists(exp))
        self.failUnless(os.path.isdir(exp))

        

