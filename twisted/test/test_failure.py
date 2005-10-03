
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.



"""
Test cases for failure module.
"""

import sys
import StringIO

from twisted.trial import unittest, util


from twisted.python import failure


class BrokenStr(Exception):
    def __str__(self):
        raise self

class FailureTestCase(unittest.TestCase):

    def testFailAndTrap(self):
        """Trapping a failure."""
        try:
            raise NotImplementedError('test')
        except:
            f = failure.Failure()
        error = f.trap(SystemExit, RuntimeError)
        self.assertEquals(error, RuntimeError)
        self.assertEquals(f.type, NotImplementedError)
    
    def test_notTrapped(self):
        """Making sure trap doesn't trap what it shouldn't."""
        try:
            raise ValueError()
        except:
            f = failure.Failure()
        self.assertRaises(failure.Failure,f.trap,OverflowError)

    def testPrinting(self):
        out = StringIO.StringIO()
        try:
            1/0
        except:
            f = failure.Failure()
        f.printDetailedTraceback(out)
        f.printBriefTraceback(out)
        f.printTraceback(out)

    def testExplictPass(self):
        e = RuntimeError()
        f = failure.Failure(e)
        f.trap(RuntimeError)
        self.assertEquals(f.value, e)


    def _getDivisionFailure(self):
        try:
            1/0
        except:
            f = failure.Failure()
        return f

    def _getInnermostFrameLine(self, f):
        try:
            f.raiseException()
        except ZeroDivisionError:
            tb = util.extract_tb(sys.exc_info()[2])
            return tb[-1][-1]
        else:
            raise Exception(
                "f.raiseException() didn't raise ZeroDivisionError!?")

    def testRaiseExceptionWithTB(self):
        f = self._getDivisionFailure()
        innerline = self._getInnermostFrameLine(f)
        self.assertEquals(innerline, '1/0')

    def testLackOfTB(self):
        f = self._getDivisionFailure()
        f.cleanFailure()
        innerline = self._getInnermostFrameLine(f)
        self.assertEquals(innerline, '1/0')

    testLackOfTB.todo = "the traceback is not preserved, exarkun said he'll try to fix this! god knows how"

    def _getStringFailure(self):
        try:
            raise "bugger off"
        except:
            f = failure.Failure()
        return f

    def testStringExceptions(self):
        # String exceptions used to totally bugged f.raiseException
        f = self._getStringFailure()
        try:
            f.raiseException()
        except:
            self.assertEquals(sys.exc_info()[0], "bugger off")
        else:
            raise AssertionError("Should have raised")

    def testBrokenStr(self):
        x = BrokenStr()
        try:
            str(x)
        except:
            f = failure.Failure()
        self.assertEquals(f.value, x)
        try:
            f.getTraceback()
        except:
            self.fail("getTraceback() shouldn't raise an exception")
