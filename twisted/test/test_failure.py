
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.



"""
Test cases for failure module.
"""

import sys
import StringIO
import traceback

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
            tb = traceback.extract_tb(sys.exc_info()[2])
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
    testStringExceptions.suppress = [
        util.suppress(message='raising a string exception is deprecated')]

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

    def testConstructionFails(self):
        """
        Creating a Failure with no arguments causes it to try to discover the
        current interpreter exception state.  If no such state exists, creating
        the Failure should raise a synchronous exception.
        """
        self.assertRaises(failure.NoCurrentExceptionError, failure.Failure)

    def test_getTracebackObject(self):
        """
        If the C{Failure} has not been cleaned, then C{getTracebackObject}
        should return the traceback object that it was given in the
        constructor.
        """
        f = self._getDivisionFailure()
        self.assertEqual(f.getTracebackObject(), f.tb)

    def test_getTracebackObjectFromClean(self):
        """
        If the Failure has been cleaned, then C{getTracebackObject} should
        return an object that looks the same to L{traceback.extract_tb}.
        """
        f = self._getDivisionFailure()
        expected = traceback.extract_tb(f.getTracebackObject())
        f.cleanFailure()
        observed = traceback.extract_tb(f.getTracebackObject())
        self.assertEqual(expected, observed)

    def test_getTracebackObjectWithoutTraceback(self):
        """
        L{failure.Failure}s need not be constructed with traceback objects. If
        a C{Failure} has no traceback information at all, C{getTracebackObject}
        should just return None.

        None is a good value, because traceback.extract_tb(None) -> [].
        """
        f = failure.Failure(Exception("some error"))
        self.assertEqual(f.getTracebackObject(), None)


class TestFormattableTraceback(unittest.TestCase):
    """
    Whitebox tests that show that L{failure._Traceback} constructs objects that
    can be used by L{traceback.extract_tb}.

    If the objects can be used by L{traceback.extract_tb}, then they can be
    formatted using L{traceback.format_tb} and friends.
    """

    def test_singleFrame(self):
        """
        A C{_Traceback} object constructed with a single frame should be able
        to be passed to L{traceback.extract_tb}, and we should get a singleton
        list containing a (filename, lineno, methodname, line) tuple.
        """
        tb = failure._Traceback([['method', 'filename.py', 123, {}, {}]])
        # Note that we don't need to test that extract_tb correctly extracts
        # the line's contents. In this case, since filename.py doesn't exist,
        # it will just use None.
        self.assertEqual(traceback.extract_tb(tb),
                         [('filename.py', 123, 'method', None)])

    def test_manyFrames(self):
        """
        A C{_Traceback} object constructed with multiple frames should be able
        to be passed to L{traceback.extract_tb}, and we should get a list
        containing a tuple for each frame.
        """
        tb = failure._Traceback([
            ['method1', 'filename.py', 123, {}, {}],
            ['method2', 'filename.py', 235, {}, {}]])
        self.assertEqual(traceback.extract_tb(tb),
                         [('filename.py', 123, 'method1', None),
                          ('filename.py', 235, 'method2', None)])
