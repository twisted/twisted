# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for failure module.
"""
from __future__ import division, absolute_import

import re
import sys
import traceback
import pdb

from twisted.python.compat import NativeStringIO, _PY3
from twisted.internet import defer

from twisted.trial.unittest import SynchronousTestCase

from twisted.python import failure

try:
    from twisted.test import raiser
except ImportError:
    raiser = None


def getDivisionFailure(*args, **kwargs):
    """
    Make a C{Failure} of a divide-by-zero error.

    @param args: Any C{*args} are passed to Failure's constructor.
    @param kwargs: Any C{**kwargs} are passed to Failure's constructor.
    """
    try:
        1/0
    except:
        f = failure.Failure(*args, **kwargs)
    return f


class FailureTestCase(SynchronousTestCase):

    def testFailAndTrap(self):
        """Trapping a failure."""
        try:
            raise NotImplementedError('test')
        except:
            f = failure.Failure()
        error = f.trap(SystemExit, RuntimeError)
        self.assertEqual(error, RuntimeError)
        self.assertEqual(f.type, NotImplementedError)


    def test_notTrapped(self):
        """Making sure trap doesn't trap what it shouldn't."""
        exception = ValueError()
        try:
            raise exception
        except:
            f = failure.Failure()

        # On Python 2, the same failure is reraised:
        if not _PY3:
            untrapped = self.assertRaises(failure.Failure, f.trap, OverflowError)
            self.assertIdentical(f, untrapped)

        # On both Python 2 and Python 3, the underlying exception is passed
        # on:
        try:
            f.trap(OverflowError)
        except:
            untrapped = failure.Failure()
            self.assertIdentical(untrapped.value, exception)
        else:
            self.fail("Exception was not re-raised.")


    def assertStartsWith(self, s, prefix):
        """
        Assert that s starts with a particular prefix.
        """
        self.assertTrue(s.startswith(prefix),
                        '%r is not the start of %r' % (prefix, s))


    def test_printingSmokeTest(self):
        """
        None of the print* methods fail when called.
        """
        f = getDivisionFailure()
        out = NativeStringIO()
        f.printDetailedTraceback(out)
        self.assertStartsWith(out.getvalue(), '*--- Failure')
        out = NativeStringIO()
        f.printBriefTraceback(out)
        self.assertStartsWith(out.getvalue(), 'Traceback')
        out = NativeStringIO()
        f.printTraceback(out)
        self.assertStartsWith(out.getvalue(), 'Traceback')


    def test_printingCapturedVarsSmokeTest(self):
        """
        None of the print* methods fail when called on a L{Failure} constructed
        with C{captureVars=True}.

        Local variables on the stack can be seen in the detailed traceback.
        """
        exampleLocalVar = 'xyzzy'
        f = getDivisionFailure(captureVars=True)
        out = NativeStringIO()
        f.printDetailedTraceback(out)
        self.assertStartsWith(out.getvalue(), '*--- Failure')
        self.assertNotEqual(None, re.search('exampleLocalVar.*xyzzy',
                                            out.getvalue()))
        out = NativeStringIO()
        f.printBriefTraceback(out)
        self.assertStartsWith(out.getvalue(), 'Traceback')
        out = NativeStringIO()
        f.printTraceback(out)
        self.assertStartsWith(out.getvalue(), 'Traceback')


    def test_printingCapturedVarsCleanedSmokeTest(self):
        """
        C{printDetailedTraceback} includes information about local variables on
        the stack after C{cleanFailure} has been called.
        """
        exampleLocalVar = 'xyzzy'
        f = getDivisionFailure(captureVars=True)
        f.cleanFailure()
        out = NativeStringIO()
        f.printDetailedTraceback(out)
        self.assertNotEqual(None, re.search('exampleLocalVar.*xyzzy',
                                            out.getvalue()))


    def test_printingNoVars(self):
        """
        Calling C{Failure()} with no arguments does not capture any locals or
        globals, so L{printDetailedTraceback} cannot show them in its output.
        """
        out = NativeStringIO()
        f = getDivisionFailure()
        f.printDetailedTraceback(out)
        # There should be no variables in the detailed output.  Variables are
        # printed on lines with 2 leading spaces.
        linesWithVars = [line for line in out.getvalue().splitlines()
                         if line.startswith('  ')]
        self.assertEqual([], linesWithVars)
        self.assertIn(
            'Capture of Locals and Globals disabled', out.getvalue())


    def test_printingCaptureVars(self):
        """
        Calling C{Failure(captureVars=True)} captures the locals and globals
        for its stack frames, so L{printDetailedTraceback} will show them in
        its output.
        """
        out = NativeStringIO()
        f = getDivisionFailure(captureVars=True)
        f.printDetailedTraceback(out)
        # Variables are printed on lines with 2 leading spaces.
        linesWithVars = [line for line in out.getvalue().splitlines()
                         if line.startswith('  ')]
        self.assertNotEqual([], linesWithVars)


    def testExplictPass(self):
        e = RuntimeError()
        f = failure.Failure(e)
        f.trap(RuntimeError)
        self.assertEqual(f.value, e)


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
        f = getDivisionFailure()
        innerline = self._getInnermostFrameLine(f)
        self.assertEqual(innerline, '1/0')


    def testLackOfTB(self):
        f = getDivisionFailure()
        f.cleanFailure()
        innerline = self._getInnermostFrameLine(f)
        self.assertEqual(innerline, '1/0')

    testLackOfTB.todo = "the traceback is not preserved, exarkun said he'll try to fix this! god knows how"
    if _PY3:
        del testLackOfTB # fix in ticket #6008


    def test_stringExceptionConstruction(self):
        """
        Constructing a C{Failure} with a string as its exception value raises
        a C{TypeError}, as this is no longer supported as of Python 2.6.
        """
        exc = self.assertRaises(TypeError, failure.Failure, "ono!")
        self.assertIn("Strings are not supported by Failure", str(exc))


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
        returns the traceback object that captured in its constructor.
        """
        f = getDivisionFailure()
        self.assertEqual(f.getTracebackObject(), f.tb)


    def test_getTracebackObjectFromCaptureVars(self):
        """
        C{captureVars=True} has no effect on the result of
        C{getTracebackObject}.
        """
        try:
            1/0
        except ZeroDivisionError:
            noVarsFailure = failure.Failure()
            varsFailure = failure.Failure(captureVars=True)
        self.assertEqual(noVarsFailure.getTracebackObject(), varsFailure.tb)


    def test_getTracebackObjectFromClean(self):
        """
        If the Failure has been cleaned, then C{getTracebackObject} returns an
        object that looks the same to L{traceback.extract_tb}.
        """
        f = getDivisionFailure()
        expected = traceback.extract_tb(f.getTracebackObject())
        f.cleanFailure()
        observed = traceback.extract_tb(f.getTracebackObject())
        self.assertNotEqual(None, expected)
        self.assertEqual(expected, observed)


    def test_getTracebackObjectFromCaptureVarsAndClean(self):
        """
        If the Failure was created with captureVars, then C{getTracebackObject}
        returns an object that looks the same to L{traceback.extract_tb}.
        """
        f = getDivisionFailure(captureVars=True)
        expected = traceback.extract_tb(f.getTracebackObject())
        f.cleanFailure()
        observed = traceback.extract_tb(f.getTracebackObject())
        self.assertEqual(expected, observed)


    def test_getTracebackObjectWithoutTraceback(self):
        """
        L{failure.Failure}s need not be constructed with traceback objects. If
        a C{Failure} has no traceback information at all, C{getTracebackObject}
        just returns None.

        None is a good value, because traceback.extract_tb(None) -> [].
        """
        f = failure.Failure(Exception("some error"))
        self.assertEqual(f.getTracebackObject(), None)


    def test_tracebackFromExceptionInPython3(self):
        """
        If a L{failure.Failure} is constructed with an exception but no
        traceback in Python 3, the traceback will be extracted from the
        exception's C{__traceback__} attribute.
        """
        try:
            1/0
        except:
            klass, exception, tb = sys.exc_info()
        f = failure.Failure(exception)
        self.assertIdentical(f.tb, tb)


    def test_cleanFailureRemovesTracebackInPython3(self):
        """
        L{failure.Failure.cleanFailure} sets the C{__traceback__} attribute of
        the exception to C{None} in Python 3.
        """
        f = getDivisionFailure()
        self.assertNotEqual(f.tb, None)
        self.assertIdentical(f.value.__traceback__, f.tb)
        f.cleanFailure()
        self.assertIdentical(f.value.__traceback__, None)

    if not _PY3:
        test_tracebackFromExceptionInPython3.skip = "Python 3 only."
        test_cleanFailureRemovesTracebackInPython3.skip = "Python 3 only."



class BrokenStr(Exception):
    """
    An exception class the instances of which cannot be presented as strings via
    C{str}.
    """
    def __str__(self):
        # Could raise something else, but there's no point as yet.
        raise self



class BrokenExceptionMetaclass(type):
    """
    A metaclass for an exception type which cannot be presented as a string via
    C{str}.
    """
    def __str__(self):
        raise ValueError("You cannot make a string out of me.")



class BrokenExceptionType(Exception, object):
    """
    The aforementioned exception type which cnanot be presented as a string via
    C{str}.
    """
    __metaclass__ = BrokenExceptionMetaclass



class GetTracebackTests(SynchronousTestCase):
    """
    Tests for L{Failure.getTraceback}.
    """
    def _brokenValueTest(self, detail):
        """
        Construct a L{Failure} with an exception that raises an exception from
        its C{__str__} method and then call C{getTraceback} with the specified
        detail and verify that it returns a string.
        """
        x = BrokenStr()
        f = failure.Failure(x)
        traceback = f.getTraceback(detail=detail)
        self.assertIsInstance(traceback, str)


    def test_brokenValueBriefDetail(self):
        """
        A L{Failure} might wrap an exception with a C{__str__} method which
        raises an exception.  In this case, calling C{getTraceback} on the
        failure with the C{"brief"} detail does not raise an exception.
        """
        self._brokenValueTest("brief")


    def test_brokenValueDefaultDetail(self):
        """
        Like test_brokenValueBriefDetail, but for the C{"default"} detail case.
        """
        self._brokenValueTest("default")


    def test_brokenValueVerboseDetail(self):
        """
        Like test_brokenValueBriefDetail, but for the C{"default"} detail case.
        """
        self._brokenValueTest("verbose")


    def _brokenTypeTest(self, detail):
        """
        Construct a L{Failure} with an exception type that raises an exception
        from its C{__str__} method and then call C{getTraceback} with the
        specified detail and verify that it returns a string.
        """
        f = failure.Failure(BrokenExceptionType())
        traceback = f.getTraceback(detail=detail)
        self.assertIsInstance(traceback, str)


    def test_brokenTypeBriefDetail(self):
        """
        A L{Failure} might wrap an exception the type object of which has a
        C{__str__} method which raises an exception.  In this case, calling
        C{getTraceback} on the failure with the C{"brief"} detail does not raise
        an exception.
        """
        self._brokenTypeTest("brief")


    def test_brokenTypeDefaultDetail(self):
        """
        Like test_brokenTypeBriefDetail, but for the C{"default"} detail case.
        """
        self._brokenTypeTest("default")


    def test_brokenTypeVerboseDetail(self):
        """
        Like test_brokenTypeBriefDetail, but for the C{"verbose"} detail case.
        """
        self._brokenTypeTest("verbose")



class FindFailureTests(SynchronousTestCase):
    """
    Tests for functionality related to L{Failure._findFailure}.
    """

    def test_findNoFailureInExceptionHandler(self):
        """
        Within an exception handler, _findFailure should return
        C{None} in case no Failure is associated with the current
        exception.
        """
        try:
            1/0
        except:
            self.assertEqual(failure.Failure._findFailure(), None)
        else:
            self.fail("No exception raised from 1/0!?")


    def test_findNoFailure(self):
        """
        Outside of an exception handler, _findFailure should return None.
        """
        self.assertEqual(sys.exc_info()[-1], None) #environment sanity check
        self.assertEqual(failure.Failure._findFailure(), None)


    def test_findFailure(self):
        """
        Within an exception handler, it should be possible to find the
        original Failure that caused the current exception (if it was
        caused by raiseException).
        """
        f = getDivisionFailure()
        f.cleanFailure()
        try:
            f.raiseException()
        except:
            self.assertEqual(failure.Failure._findFailure(), f)
        else:
            self.fail("No exception raised from raiseException!?")


    def test_failureConstructionFindsOriginalFailure(self):
        """
        When a Failure is constructed in the context of an exception
        handler that is handling an exception raised by
        raiseException, the new Failure should be chained to that
        original Failure.
        """
        f = getDivisionFailure()
        f.cleanFailure()
        try:
            f.raiseException()
        except:
            newF = failure.Failure()
            self.assertEqual(f.getTraceback(), newF.getTraceback())
        else:
            self.fail("No exception raised from raiseException!?")


    def test_failureConstructionWithMungedStackSucceeds(self):
        """
        Pyrex and Cython are known to insert fake stack frames so as to give
        more Python-like tracebacks. These stack frames with empty code objects
        should not break extraction of the exception.
        """
        try:
            raiser.raiseException()
        except raiser.RaiserException:
            f = failure.Failure()
            self.assertTrue(f.check(raiser.RaiserException))
        else:
            self.fail("No exception raised from extension?!")


    if raiser is None:
        skipMsg = "raiser extension not available"
        test_failureConstructionWithMungedStackSucceeds.skip = skipMsg



class TestFormattableTraceback(SynchronousTestCase):
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



class TestFrameAttributes(SynchronousTestCase):
    """
    _Frame objects should possess some basic attributes that qualify them as
    fake python Frame objects.
    """

    def test_fakeFrameAttributes(self):
        """
        L{_Frame} instances have the C{f_globals} and C{f_locals} attributes
        bound to C{dict} instance.  They also have the C{f_code} attribute
        bound to something like a code object.
        """
        frame = failure._Frame("dummyname", "dummyfilename")
        self.assertIsInstance(frame.f_globals, dict)
        self.assertIsInstance(frame.f_locals, dict)
        self.assertIsInstance(frame.f_code, failure._Code)



class TestDebugMode(SynchronousTestCase):
    """
    Failure's debug mode should allow jumping into the debugger.
    """

    def setUp(self):
        """
        Override pdb.post_mortem so we can make sure it's called.
        """
        # Make sure any changes we make are reversed:
        post_mortem = pdb.post_mortem
        if _PY3:
            origInit = failure.Failure.__init__
        else:
            origInit = failure.Failure.__dict__['__init__']
        def restore():
            pdb.post_mortem = post_mortem
            if _PY3:
                failure.Failure.__init__ = origInit
            else:
                failure.Failure.__dict__['__init__'] = origInit
        self.addCleanup(restore)

        self.result = []
        pdb.post_mortem = self.result.append
        failure.startDebugMode()


    def test_regularFailure(self):
        """
        If startDebugMode() is called, calling Failure() will first call
        pdb.post_mortem with the traceback.
        """
        try:
            1/0
        except:
            typ, exc, tb = sys.exc_info()
            f = failure.Failure()
        self.assertEqual(self.result, [tb])
        self.assertEqual(f.captureVars, False)


    def test_captureVars(self):
        """
        If startDebugMode() is called, passing captureVars to Failure() will
        not blow up.
        """
        try:
            1/0
        except:
            typ, exc, tb = sys.exc_info()
            f = failure.Failure(captureVars=True)
        self.assertEqual(self.result, [tb])
        self.assertEqual(f.captureVars, True)



class ExtendedGeneratorTests(SynchronousTestCase):
    """
    Tests C{failure.Failure} support for generator features added in Python 2.5
    """

    def test_inlineCallbacksTracebacks(self):
        """
        inlineCallbacks that re-raise tracebacks into their deferred
        should not lose their tracebacks.
        """
        f = getDivisionFailure()
        d = defer.Deferred()
        try:
            f.raiseException()
        except:
            d.errback()

        failures = []
        def collect_error(result):
            failures.append(result)

        def ic(d):
            yield d
        ic = defer.inlineCallbacks(ic)
        ic(d).addErrback(collect_error)

        newFailure, = failures
        self.assertEqual(
            traceback.extract_tb(newFailure.getTracebackObject())[-1][-1],
            "1/0"
        )


    def _throwIntoGenerator(self, f, g):
        try:
            f.throwExceptionIntoGenerator(g)
        except StopIteration:
            pass
        else:
            self.fail("throwExceptionIntoGenerator should have raised "
                      "StopIteration")

    def test_throwExceptionIntoGenerator(self):
        """
        It should be possible to throw the exception that a Failure
        represents into a generator.
        """
        stuff = []
        def generator():
            try:
                yield
            except:
                stuff.append(sys.exc_info())
            else:
                self.fail("Yield should have yielded exception.")
        g = generator()
        f = getDivisionFailure()
        next(g)
        self._throwIntoGenerator(f, g)

        self.assertEqual(stuff[0][0], ZeroDivisionError)
        self.assertTrue(isinstance(stuff[0][1], ZeroDivisionError))

        self.assertEqual(traceback.extract_tb(stuff[0][2])[-1][-1], "1/0")


    def test_findFailureInGenerator(self):
        """
        Within an exception handler, it should be possible to find the
        original Failure that caused the current exception (if it was
        caused by throwExceptionIntoGenerator).
        """
        f = getDivisionFailure()
        f.cleanFailure()

        foundFailures = []
        def generator():
            try:
                yield
            except:
                foundFailures.append(failure.Failure._findFailure())
            else:
                self.fail("No exception sent to generator")

        g = generator()
        next(g)
        self._throwIntoGenerator(f, g)

        self.assertEqual(foundFailures, [f])


    def test_failureConstructionFindsOriginalFailure(self):
        """
        When a Failure is constructed in the context of an exception
        handler that is handling an exception raised by
        throwExceptionIntoGenerator, the new Failure should be chained to that
        original Failure.
        """
        f = getDivisionFailure()
        f.cleanFailure()

        newFailures = []

        def generator():
            try:
                yield
            except:
                newFailures.append(failure.Failure())
            else:
                self.fail("No exception sent to generator")
        g = generator()
        next(g)
        self._throwIntoGenerator(f, g)

        self.assertEqual(len(newFailures), 1)
        self.assertEqual(newFailures[0].getTraceback(), f.getTraceback())

    if _PY3:
        test_inlineCallbacksTracebacks.todo = (
            "Python 3 support to be fixed in #5949")
        test_findFailureInGenerator.todo = (
            "Python 3 support to be fixed in #5949")
        test_failureConstructionFindsOriginalFailure.todo = (
            "Python 3 support to be fixed in #5949")
        # Remove these three lines in #6008:
        del test_findFailureInGenerator
        del test_failureConstructionFindsOriginalFailure
        del test_inlineCallbacksTracebacks


    def test_ambiguousFailureInGenerator(self):
        """
        When a generator reraises a different exception,
        L{Failure._findFailure} inside the generator should find the reraised
        exception rather than original one.
        """
        def generator():
            try:
                try:
                    yield
                except:
                    [][1]
            except:
                self.assertIsInstance(failure.Failure().value, IndexError)
        g = generator()
        next(g)
        f = getDivisionFailure()
        self._throwIntoGenerator(f, g)


    def test_ambiguousFailureFromGenerator(self):
        """
        When a generator reraises a different exception,
        L{Failure._findFailure} above the generator should find the reraised
        exception rather than original one.
        """
        def generator():
            try:
                yield
            except:
                [][1]
        g = generator()
        next(g)
        f = getDivisionFailure()
        try:
            self._throwIntoGenerator(f, g)
        except:
            self.assertIsInstance(failure.Failure().value, IndexError)
