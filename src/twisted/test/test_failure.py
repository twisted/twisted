# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for the L{twisted.python.failure} module.
"""
from __future__ import annotations

import linecache
import pdb
import pickle
import re
import sys
import traceback
from dis import distb
from io import StringIO
from traceback import FrameSummary
from types import TracebackType
from typing import Any, Generator, cast
from unittest import skipIf

from cython_test_exception_raiser import raiser

from twisted.python import failure, reflect
from twisted.trial.unittest import SynchronousTestCase


class ComparableException(Exception):
    """An exception that can be compared by value."""

    def __eq__(self, other: object) -> bool:
        return (self.__class__ == other.__class__) and (
            self.args == cast(ComparableException, other).args
        )


def getDivisionFailure(*, captureVars: bool = False) -> failure.Failure:
    """
    Make a C{Failure} of a divide-by-zero error.
    """
    if captureVars:
        exampleLocalVar = "xyz"
        # Silence the linter as this variable is checked via
        # the traceback.
        exampleLocalVar

    try:
        1 / 0
    except BaseException:
        f = failure.Failure(captureVars=captureVars)
    return f


class FailureTests(SynchronousTestCase):
    """
    Tests for L{failure.Failure}.
    """

    def test_failAndTrap(self) -> None:
        """
        Trapping a L{Failure}.
        """
        try:
            raise NotImplementedError("test")
        except BaseException:
            f = failure.Failure()
        error = f.trap(SystemExit, RuntimeError)
        self.assertEqual(error, RuntimeError)
        self.assertEqual(f.type, NotImplementedError)

    def test_trapRaisesWrappedException(self) -> None:
        """
        If the wrapped C{Exception} is not a subclass of one of the
        expected types, L{failure.Failure.trap} raises the wrapped
        C{Exception}.
        """
        exception = ValueError()
        try:
            raise exception
        except BaseException:
            f = failure.Failure()

        untrapped = self.assertRaises(ValueError, f.trap, OverflowError)
        self.assertIs(exception, untrapped)

    def test_failureValueFromFailure(self) -> None:
        """
        A L{failure.Failure} constructed from another
        L{failure.Failure} instance, has its C{value} property set to
        the value of that L{failure.Failure} instance.
        """
        exception = ValueError()
        f1 = failure.Failure(exception)
        f2 = failure.Failure(f1)
        self.assertIs(f2.value, exception)

    def test_failureValueFromFoundFailure(self) -> None:
        """
        A L{failure.Failure} constructed without a C{exc_value}
        argument, will search for an "original" C{Failure}, and if
        found, its value will be used as the value for the new
        C{Failure}.
        """
        exception = ValueError()
        f1 = failure.Failure(exception)
        try:
            f1.trap(OverflowError)
        except BaseException:
            f2 = failure.Failure()

        self.assertIs(f2.value, exception)

    def assertStartsWith(self, s: str, prefix: str) -> None:
        """
        Assert that C{s} starts with a particular C{prefix}.

        @param s: The input string.
        @type s: C{str}
        @param prefix: The string that C{s} should start with.
        @type prefix: C{str}
        """
        self.assertTrue(s.startswith(prefix), f"{prefix!r} is not the start of {s!r}")

    def assertEndsWith(self, s: str, suffix: str) -> None:
        """
        Assert that C{s} end with a particular C{suffix}.

        @param s: The input string.
        @type s: C{str}
        @param suffix: The string that C{s} should end with.
        @type suffix: C{str}
        """
        self.assertTrue(s.endswith(suffix), f"{suffix!r} is not the end of {s!r}")

    def assertTracebackFormat(self, tb: str, prefix: str, suffix: str) -> None:
        """
        Assert that the C{tb} traceback contains a particular C{prefix} and
        C{suffix}.

        @param tb: The traceback string.
        @type tb: C{str}
        @param prefix: The string that C{tb} should start with.
        @type prefix: C{str}
        @param suffix: The string that C{tb} should end with.
        @type suffix: C{str}
        """
        self.assertStartsWith(tb, prefix)
        self.assertEndsWith(tb, suffix)

    def assertDetailedTraceback(
        self, captureVars: bool = False, cleanFailure: bool = False
    ) -> None:
        """
        Assert that L{printDetailedTraceback} produces and prints a detailed
        traceback.

        The detailed traceback consists of a header::

          *--- Failure #20 ---

        The body contains the stacktrace::

          /twisted/test/test_failure.py:39: getDivisionFailure(...)

        If C{captureVars} is enabled the body also includes a list of
        globals and locals::

           [ Locals ]
             exampleLocalVar : 'xyz'
             ...
           ( Globals )
             ...

        Or when C{captureVars} is disabled::

           [Capture of Locals and Globals disabled (use captureVars=True)]

        When C{cleanFailure} is enabled references to other objects are removed
        and replaced with strings.

        And finally the footer with the L{Failure}'s value::

          exceptions.ZeroDivisionError: float division
          *--- End of Failure #20 ---

        @param captureVars: Enables L{Failure.captureVars}.
        @type captureVars: C{bool}
        @param cleanFailure: Enables L{Failure.cleanFailure}.
        @type cleanFailure: C{bool}
        """
        f = getDivisionFailure(captureVars=captureVars)
        out = StringIO()
        if cleanFailure:
            f.cleanFailure()
        f.printDetailedTraceback(out)

        tb = out.getvalue()
        start = "*--- Failure #%d%s---\n" % (
            f.count,
            (f.pickled and " (pickled) ") or " ",
        )
        end = "{}: {}\n*--- End of Failure #{} ---\n".format(
            reflect.qual(f.type),
            reflect.safe_str(f.value),
            f.count,
        )
        self.assertTracebackFormat(tb, start, end)

        # Variables are printed on lines with 2 leading spaces.
        linesWithVars = [line for line in tb.splitlines() if line.startswith("  ")]

        if captureVars:
            self.assertNotEqual([], linesWithVars)
            if cleanFailure:
                line = "  exampleLocalVar : \"'xyz'\""
            else:
                line = "  exampleLocalVar : 'xyz'"
            self.assertIn(line, linesWithVars)
        else:
            self.assertEqual([], linesWithVars)
            self.assertIn(
                " [Capture of Locals and Globals disabled (use " "captureVars=True)]\n",
                tb,
            )

    def assertBriefTraceback(self, captureVars: bool = False) -> None:
        """
        Assert that L{printBriefTraceback} produces and prints a brief
        traceback.

        The brief traceback consists of a header::

          Traceback: <type 'exceptions.ZeroDivisionError'>: float division

        And the footer::

          /twisted/test/test_failure.py:39:getDivisionFailure

        @param captureVars: Enables L{Failure.captureVars}.
        @type captureVars: C{bool}
        """
        if captureVars:
            exampleLocalVar = "abcde"
            # Silence the linter as this variable is checked via
            # the traceback.
            exampleLocalVar

        f = getDivisionFailure()
        out = StringIO()
        f.printBriefTraceback(out)
        tb = out.getvalue()
        stack = ""
        for method, filename, lineno, localVars, globalVars in f.frames:
            stack += f"{filename}:{lineno}:{method}\n"

        zde = repr(ZeroDivisionError)
        self.assertTracebackFormat(
            tb,
            f"Traceback: {zde}: ",
            f"{stack}",
        )

        if captureVars:
            self.assertIsNone(re.search("exampleLocalVar.*abcde", tb))

    def assertDefaultTraceback(self, captureVars: bool = False) -> None:
        """
        Assert that L{printTraceback} produces and prints a default traceback.

        The default traceback consists of a header::

          Traceback (most recent call last):

        And the footer::

            File "twisted/test/test_failure.py", line 39, in getDivisionFailure
              1 / 0
            exceptions.ZeroDivisionError: float division

        @param captureVars: Enables L{Failure.captureVars}.
        @type captureVars: C{bool}
        """
        if captureVars:
            exampleLocalVar = "xyzzy"
            # Silence the linter as this variable is checked via
            # the traceback.
            exampleLocalVar

        f = getDivisionFailure(captureVars=captureVars)
        out = StringIO()
        f.printTraceback(out)
        tb = out.getvalue()
        stack = ""
        for method, filename, lineno, localVars, globalVars in f.frames:
            stack += f'  File "{filename}", line {lineno}, in {method}\n'
            stack += f"    {linecache.getline(filename, lineno).strip()}\n"

        self.assertTracebackFormat(
            tb,
            "Traceback (most recent call last):",
            "%s%s: %s\n"
            % (
                stack,
                reflect.qual(f.type),
                reflect.safe_str(f.value),
            ),
        )

        if captureVars:
            self.assertIsNone(re.search("exampleLocalVar.*xyzzy", tb))

    def test_printDetailedTraceback(self) -> None:
        """
        L{printDetailedTraceback} returns a detailed traceback including the
        L{Failure}'s count.
        """
        self.assertDetailedTraceback()

    def test_printBriefTraceback(self) -> None:
        """
        L{printBriefTraceback} returns a brief traceback.
        """
        self.assertBriefTraceback()

    def test_printTraceback(self) -> None:
        """
        L{printTraceback} returns a traceback.
        """
        self.assertDefaultTraceback()

    def test_printDetailedTracebackCapturedVars(self) -> None:
        """
        L{printDetailedTraceback} captures the locals and globals for its
        stack frames and adds them to the traceback, when called on a
        L{Failure} constructed with C{captureVars=True}.
        """
        self.assertDetailedTraceback(captureVars=True)

    def test_printBriefTracebackCapturedVars(self) -> None:
        """
        L{printBriefTraceback} returns a brief traceback when called on a
        L{Failure} constructed with C{captureVars=True}.

        Local variables on the stack can not be seen in the resulting
        traceback.
        """
        self.assertBriefTraceback(captureVars=True)

    def test_printTracebackCapturedVars(self) -> None:
        """
        L{printTraceback} returns a traceback when called on a L{Failure}
        constructed with C{captureVars=True}.

        Local variables on the stack can not be seen in the resulting
        traceback.
        """
        self.assertDefaultTraceback(captureVars=True)

    def test_printDetailedTracebackCapturedVarsCleaned(self) -> None:
        """
        C{printDetailedTraceback} includes information about local variables on
        the stack after C{cleanFailure} has been called.
        """
        self.assertDetailedTraceback(captureVars=True, cleanFailure=True)

    def test_invalidFormatFramesDetail(self) -> None:
        """
        L{failure.format_frames} raises a L{ValueError} if the supplied
        C{detail} level is unknown.
        """
        self.assertRaises(
            ValueError, failure.format_frames, None, None, detail="noisia"
        )

    def test_ExplictPass(self) -> None:
        e = RuntimeError()
        f = failure.Failure(e)
        f.trap(RuntimeError)
        self.assertEqual(f.value, e)

    def _getInnermostFrameLine(self, f: failure.Failure) -> str | None:
        try:
            f.raiseException()
        except ZeroDivisionError:
            tb = traceback.extract_tb(sys.exc_info()[2])
            return tb[-1].line
        else:
            raise Exception("f.raiseException() didn't raise ZeroDivisionError!?")

    def test_RaiseExceptionWithTB(self) -> None:
        f = getDivisionFailure()
        innerline = self._getInnermostFrameLine(f)
        self.assertEqual(innerline, "1 / 0")

    def test_ConstructionFails(self) -> None:
        """
        Creating a Failure with no arguments causes it to try to discover the
        current interpreter exception state.  If no such state exists, creating
        the Failure should raise a synchronous exception.
        """
        self.assertRaises(failure.NoCurrentExceptionError, failure.Failure)

    def test_getTracebackObject(self) -> None:
        """
        If the C{Failure} has not been cleaned, then C{getTracebackObject}
        returns the traceback object that captured in its constructor.
        """
        f = getDivisionFailure()
        self.assertEqual(f.getTracebackObject(), f.tb)

    def test_getTracebackObjectFromCaptureVars(self) -> None:
        """
        C{captureVars=True} has no effect on the result of
        C{getTracebackObject}.
        """
        try:
            1 / 0
        except ZeroDivisionError:
            noVarsFailure = failure.Failure()
            varsFailure = failure.Failure(captureVars=True)
        self.assertEqual(noVarsFailure.getTracebackObject(), varsFailure.tb)

    def test_getTracebackObjectFromClean(self) -> None:
        """
        If the Failure has been cleaned, then C{getTracebackObject} returns an
        object that looks the same to L{traceback.extract_tb}.
        """
        f = getDivisionFailure()
        expected = traceback.extract_tb(f.getTracebackObject())
        f.cleanFailure()
        observed = traceback.extract_tb(f.getTracebackObject())
        self.assertIsNotNone(expected)
        self.assertEqual(expected, observed)

    def test_getTracebackObjectFromCaptureVarsAndClean(self) -> None:
        """
        If the Failure was created with captureVars, then C{getTracebackObject}
        returns an object that looks the same to L{traceback.extract_tb}.
        """
        f = getDivisionFailure(captureVars=True)
        expected = traceback.extract_tb(f.getTracebackObject())
        f.cleanFailure()
        observed = traceback.extract_tb(f.getTracebackObject())
        self.assertEqual(expected, observed)

    def test_getTracebackObjectWithoutTraceback(self) -> None:
        """
        L{failure.Failure}s need not be constructed with traceback objects. If
        a C{Failure} has no traceback information at all, C{getTracebackObject}
        just returns None.

        None is a good value, because traceback.extract_tb(None) -> [].
        """
        f = failure.Failure(Exception("some error"))
        self.assertIsNone(f.getTracebackObject())

    def test_tracebackFromExceptionInPython3(self) -> None:
        """
        If a L{failure.Failure} is constructed with an exception but no
        traceback in Python 3, the traceback will be extracted from the
        exception's C{__traceback__} attribute.
        """
        try:
            1 / 0
        except BaseException:
            klass, exception, tb = sys.exc_info()
        f = failure.Failure(exception)
        self.assertIs(f.tb, tb)

    def test_cleanFailureRemovesTracebackInPython3(self) -> None:
        """
        L{failure.Failure.cleanFailure} sets the C{__traceback__} attribute of
        the exception to L{None} in Python 3.
        """
        f = getDivisionFailure()
        self.assertIsNotNone(f.tb)
        self.assertIs(f.value.__traceback__, f.tb)
        f.cleanFailure()
        self.assertIsNone(f.value.__traceback__)

    def test_distb(self) -> None:
        """
        The traceback captured by a L{Failure} is compatible with the stdlib
        L{dis.distb} function as used in post-mortem debuggers. Specifically,
        it doesn't cause that function to raise an exception.
        """
        f = getDivisionFailure()
        buf = StringIO()
        distb(f.getTracebackObject(), file=buf)
        # The bytecode details vary across Python versions, so we only check
        # that the arrow pointing at the source of the exception is present.
        self.assertIn(" --> ", buf.getvalue())

    def test_repr(self) -> None:
        """
        The C{repr} of a L{failure.Failure} shows the type and string
        representation of the underlying exception.
        """
        f = getDivisionFailure()
        typeName = reflect.fullyQualifiedName(ZeroDivisionError)
        self.assertEqual(
            repr(f),
            "<twisted.python.failure.Failure " "%s: division by zero>" % (typeName,),
        )

    def test_stackDeprecation(self) -> None:
        """
        C{Failure.stack} is gettable and settable, but depreacted.
        """
        f = getDivisionFailure()
        f.stack = f.stack  # type: ignore[method-assign]
        warnings = self.flushWarnings()
        self.assertTrue(len(warnings) >= 1)
        for w in warnings[-2:]:
            self.assertEqual(
                "twisted.python.failure.Failure.stack was deprecated in Twisted 24.10.0rc1",
                w["message"],
            )

    def test_failureWithoutTraceback(self) -> None:
        """
        C{Failure._withoutTraceback(exc)} gives the same result as
        C{Failure(exc)}.
        """
        exc = ZeroDivisionError("hello")
        dict1 = failure.Failure(exc).__dict__.copy()
        failure2 = failure.Failure._withoutTraceback(exc)
        self.assertIsInstance(failure2, failure.Failure)
        dict2 = failure2.__dict__.copy()

        # count increments with each new Failure constructed:
        self.assertEqual(dict1.pop("count") + 1, dict2.pop("count"))

        # The rest of the attributes should be identical:
        self.assertEqual(dict1, dict2)

    def test_failurePickling(self) -> None:
        """
        C{Failure(exc)} and C{Failure._withoutTraceback(exc)} can be pickled
        and unpickled.
        """
        exc = ComparableException("hello")
        failure1 = failure.Failure(exc)
        self.assertPicklingRoundtrips(failure1)

        # You would think this test is unnecessary, since it's just a
        # C{Failure}, but actually the behavior of pickling can sometimes be
        # different because of the way the constructor works!
        failure2 = failure.Failure._withoutTraceback(exc)
        self.assertPicklingRoundtrips(failure2)

        # Here we test a Failure with a traceback:
        try:
            raise ComparableException("boo")
        except BaseException:
            failure3 = failure.Failure()
        self.assertPicklingRoundtrips(failure3)

    def assertPicklingRoundtrips(self, original_failure: failure.Failure) -> None:
        """
        The failure can be pickled and unpickled, and the C{parents} attribute
        is included in the pickle.
        """
        failure2 = pickle.loads(pickle.dumps(original_failure))
        expected = original_failure.__dict__.copy()
        expected["pickled"] = 1
        expected["tb"] = None
        result = failure2.__dict__.copy()
        self.assertEqual(expected, result)
        self.assertEqual(failure2.frames, original_failure.frames)

    def test_failurePicklingIncludesParents(self) -> None:
        """
        C{Failure.parents} is included in the pickle.
        """
        f = failure.Failure(ComparableException("hello"))
        self.assertEqual(f.__getstate__()["parents"], f.parents)

    def test_settableFrames(self) -> None:
        """
        C{Failure.frames} can be set, both before and after pickling.
        """
        original_failure = failure.Failure(getDivisionFailure())
        original_failure.frames = original_failure.frames[:]
        failure2 = pickle.loads(pickle.dumps(original_failure))
        failure2.frames = failure2.frames[:-1]
        self.assertEqual(failure2.frames, original_failure.frames[:-1])

    def test_settableParents(self) -> None:
        """
        C{Failure.parents} can be set, both before and after pickling.

        This is used by Foolscap.
        """
        original_failure = failure.Failure(ComparableException("hello"))
        original_failure.parents = original_failure.parents[:]
        failure2 = pickle.loads(pickle.dumps(original_failure))
        failure2.parents = failure2.parents[:]


class BrokenStr(Exception):
    """
    An exception class the instances of which cannot be presented as strings
    via L{str}.
    """

    def __str__(self) -> str:
        # Could raise something else, but there's no point as yet.
        raise self


class BrokenExceptionMetaclass(type):
    """
    A metaclass for an exception type which cannot be presented as a string via
    L{str}.
    """

    def __str__(self) -> str:
        raise ValueError("You cannot make a string out of me.")


class BrokenExceptionType(Exception, metaclass=BrokenExceptionMetaclass):

    """
    The aforementioned exception type which cannot be presented as a string via
    L{str}.
    """


class GetTracebackTests(SynchronousTestCase):
    """
    Tests for L{Failure.getTraceback}.
    """

    def _brokenValueTest(self, detail: str) -> None:
        """
        Construct a L{Failure} with an exception that raises an exception from
        its C{__str__} method and then call C{getTraceback} with the specified
        detail and verify that it returns a string.
        """
        x = BrokenStr()
        f = failure.Failure(x)
        traceback = f.getTraceback(detail=detail)
        self.assertIsInstance(traceback, str)

    def test_brokenValueBriefDetail(self) -> None:
        """
        A L{Failure} might wrap an exception with a C{__str__} method which
        raises an exception.  In this case, calling C{getTraceback} on the
        failure with the C{"brief"} detail does not raise an exception.
        """
        self._brokenValueTest("brief")

    def test_brokenValueDefaultDetail(self) -> None:
        """
        Like test_brokenValueBriefDetail, but for the C{"default"} detail case.
        """
        self._brokenValueTest("default")

    def test_brokenValueVerboseDetail(self) -> None:
        """
        Like test_brokenValueBriefDetail, but for the C{"default"} detail case.
        """
        self._brokenValueTest("verbose")

    def _brokenTypeTest(self, detail: str) -> None:
        """
        Construct a L{Failure} with an exception type that raises an exception
        from its C{__str__} method and then call C{getTraceback} with the
        specified detail and verify that it returns a string.
        """
        f = failure.Failure(BrokenExceptionType())
        traceback = f.getTraceback(detail=detail)
        self.assertIsInstance(traceback, str)

    def test_brokenTypeBriefDetail(self) -> None:
        """
                A L{Failure} might wrap an
                newPublisher(evt)
        xception the type object of which has a
                C{__str__} method which raises an exception.  In this case, calling
                C{getTraceback} on the failure with the C{"brief"} detail does not raise
                an exception.
        """
        self._brokenTypeTest("brief")

    def test_brokenTypeDefaultDetail(self) -> None:
        """
        Like test_brokenTypeBriefDetail, but for the C{"default"} detail case.
        """
        self._brokenTypeTest("default")

    def test_brokenTypeVerboseDetail(self) -> None:
        """
        Like test_brokenTypeBriefDetail, but for the C{"verbose"} detail case.
        """
        self._brokenTypeTest("verbose")


class FindFailureTests(SynchronousTestCase):
    """
    Tests for functionality related to identifying the C{Failure}.
    """

    @skipIf(raiser is None, "raiser extension not available")
    def test_failureConstructionWithMungedStackSucceeds(self) -> None:
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


# On Python 3.5, extract_tb returns "FrameSummary" objects, which are almost
# like the old tuples. This being different does not affect the actual tests
# as we are testing that the input works, and that extract_tb returns something
# reasonable.
def _tb(fn: str, lineno: int, name: str, text: None) -> FrameSummary:
    return FrameSummary(fn, lineno, name)


class FormattableTracebackTests(SynchronousTestCase):
    """
    Whitebox tests that show that L{failure._Traceback} constructs objects that
    can be used by L{traceback.extract_tb}.

    If the objects can be used by L{traceback.extract_tb}, then they can be
    formatted using L{traceback.format_tb} and friends.
    """

    def test_singleFrame(self) -> None:
        """
        A C{_Traceback} object constructed with a single frame should be able
        to be passed to L{traceback.extract_tb}, and we should get a singleton
        list containing a (filename, lineno, methodname, line) tuple.
        """
        tb = failure._Traceback([["method", "filename.py", 123, {}, {}]])
        # Note that we don't need to test that extract_tb correctly extracts
        # the line's contents. In this case, since filename.py doesn't exist,
        # it will just use None.
        self.assertEqual(
            traceback.extract_tb(tb), [_tb("filename.py", 123, "method", None)]
        )

    def test_manyFrames(self) -> None:
        """
        A C{_Traceback} object constructed with multiple frames should be able
        to be passed to L{traceback.extract_tb}, and we should get a list
        containing a tuple for each frame.
        """
        tb = failure._Traceback(
            [
                ["method1", "filename.py", 123, {}, {}],
                ["method2", "filename.py", 235, {}, {}],
            ],
        )
        self.assertEqual(
            traceback.extract_tb(tb),
            [
                _tb("filename.py", 123, "method1", None),
                _tb("filename.py", 235, "method2", None),
            ],
        )

        # We should also be able to extract_stack on it
        self.assertEqual(
            traceback.extract_stack(tb.tb_frame),
            [
                _tb("filename.py", 123, "method1", None),
            ],
        )


class FakeAttributesTests(SynchronousTestCase):
    """
    _Frame, _Code and _TracebackFrame objects should possess some basic
    attributes that qualify them as fake python objects, allowing the return of
    _Traceback to be used as a fake traceback. The attributes that have zero or
    empty values are there so that things expecting them find them (e.g. post
    mortem debuggers).
    """

    def test_fakeFrameAttributes(self) -> None:
        """
        L{_Frame} instances have the C{f_globals} and C{f_locals} attributes
        bound to C{dict} instance.  They also have the C{f_code} attribute
        bound to something like a code object.
        """
        back_frame = failure._Frame(
            (
                "dummyparent",
                "dummyparentfile",
                111,
                None,
                None,
            ),
            None,
        )
        fake_locals = {"local_var": 42}
        fake_globals = {"global_var": 100}
        frame = failure._Frame(
            (
                "dummyname",
                "dummyfilename",
                42,
                fake_locals,
                fake_globals,
            ),
            back_frame,
        )
        self.assertEqual(frame.f_globals, fake_globals)
        self.assertEqual(frame.f_locals, fake_locals)
        self.assertIsInstance(frame.f_code, failure._Code)
        self.assertEqual(frame.f_back, back_frame)
        self.assertIsInstance(frame.f_builtins, dict)
        self.assertIsInstance(frame.f_lasti, int)
        self.assertEqual(frame.f_lineno, 42)
        self.assertIsInstance(frame.f_trace, type(None))

    def test_fakeCodeAttributes(self) -> None:
        """
        See L{FakeAttributesTests} for more details about this test.
        """
        code = failure._Code("dummyname", "dummyfilename")
        self.assertEqual(code.co_name, "dummyname")
        self.assertEqual(code.co_filename, "dummyfilename")
        self.assertIsInstance(code.co_argcount, int)
        self.assertIsInstance(code.co_code, bytes)
        self.assertIsInstance(code.co_cellvars, tuple)
        self.assertIsInstance(code.co_consts, tuple)
        self.assertIsInstance(code.co_firstlineno, int)
        self.assertIsInstance(code.co_flags, int)
        self.assertIsInstance(code.co_lnotab, bytes)
        self.assertIsInstance(code.co_freevars, tuple)
        self.assertIsInstance(code.co_posonlyargcount, int)
        self.assertIsInstance(code.co_kwonlyargcount, int)
        self.assertIsInstance(code.co_names, tuple)
        self.assertIsInstance(code.co_nlocals, int)
        self.assertIsInstance(code.co_stacksize, int)
        self.assertIsInstance(code.co_varnames, list)
        self.assertIsInstance(code.co_positions(), tuple)

    def test_fakeTracebackFrame(self) -> None:
        """
        See L{FakeAttributesTests} for more details about this test.
        """
        frame = failure._Frame(
            ("dummyname", "dummyfilename", 42, {}, {}),
            None,
        )
        traceback_frame = failure._TracebackFrame(frame)
        self.assertEqual(traceback_frame.tb_frame, frame)
        self.assertEqual(traceback_frame.tb_lineno, 42)
        self.assertIsInstance(traceback_frame.tb_lasti, int)
        self.assertTrue(hasattr(traceback_frame, "tb_next"))


class DebugModeTests(SynchronousTestCase):
    """
    Failure's debug mode should allow jumping into the debugger.
    """

    def setUp(self) -> None:
        """
        Override pdb.post_mortem so we can make sure it's called.
        """
        # Make sure any changes we make are reversed:
        post_mortem = pdb.post_mortem
        origInit = failure.Failure.__init__

        def restore() -> None:
            pdb.post_mortem = post_mortem
            failure.Failure.__init__ = origInit  # type: ignore[method-assign]

        self.addCleanup(restore)

        self.result: list[TracebackType | None] = []

        def logging_post_mortem(t: TracebackType | None = None) -> None:
            self.result.append(t)

        pdb.post_mortem = logging_post_mortem
        failure.startDebugMode()

    def test_regularFailure(self) -> None:
        """
        If startDebugMode() is called, calling Failure() will first call
        pdb.post_mortem with the traceback.
        """
        try:
            1 / 0
        except BaseException:
            typ, exc, tb = sys.exc_info()
            f = failure.Failure()
        self.assertEqual(self.result, [tb])
        self.assertFalse(f.captureVars)

    def test_captureVars(self) -> None:
        """
        If startDebugMode() is called, passing captureVars to Failure() will
        not blow up.
        """
        try:
            1 / 0
        except BaseException:
            typ, exc, tb = sys.exc_info()
            f = failure.Failure(captureVars=True)
        self.assertEqual(self.result, [tb])
        self.assertTrue(f.captureVars)


class ExtendedGeneratorTests(SynchronousTestCase):
    """
    Tests C{failure.Failure} support for generator features added in Python 2.5
    """

    def _throwIntoGenerator(
        self, f: failure.Failure, g: Generator[Any, Any, Any]
    ) -> None:
        try:
            f.throwExceptionIntoGenerator(g)
        except StopIteration:
            pass
        else:
            self.fail("throwExceptionIntoGenerator should have raised " "StopIteration")

    def test_throwExceptionIntoGenerator(self) -> None:
        """
        It should be possible to throw the exception that a Failure
        represents into a generator.
        """
        stuff = []

        def generator() -> Generator[None, None, None]:
            try:
                yield
            except BaseException:
                stuff.append(sys.exc_info())
            else:
                self.fail("Yield should have yielded exception.")

        g = generator()
        f = getDivisionFailure()
        next(g)
        self._throwIntoGenerator(f, g)

        self.assertEqual(stuff[0][0], ZeroDivisionError)
        self.assertIsInstance(stuff[0][1], ZeroDivisionError)

        self.assertEqual(traceback.extract_tb(stuff[0][2])[-1][-1], "1 / 0")

    def test_failureConstructionFindsOriginalFailure(self) -> None:
        """
        When a Failure is constructed in the context of an exception
        handler that is handling an exception raised by
        throwExceptionIntoGenerator, the new Failure should be chained to that
        original Failure.
        """
        f = getDivisionFailure()
        f.cleanFailure()
        original_failure_str = f.getTraceback()

        newFailures = []

        def generator() -> Generator[None, None, None]:
            try:
                yield
            except BaseException:
                newFailures.append(failure.Failure())
            else:
                self.fail("No exception sent to generator")

        g = generator()
        next(g)
        self._throwIntoGenerator(f, g)

        self.assertEqual(len(newFailures), 1)

        # The original failure should not be changed.
        self.assertEqual(original_failure_str, f.getTraceback())

        # The new failure should be different and contain stack info for
        # our generator.
        self.assertNotEqual(newFailures[0].getTraceback(), f.getTraceback())
        self.assertIn("generator", newFailures[0].getTraceback())
        self.assertNotIn("generator", f.getTraceback())

    def test_ambiguousFailureInGenerator(self) -> None:
        """
        When a generator reraises a different exception, creating a L{Failure}
        inside the generator should find the reraised exception rather than
        original one.
        """

        def generator() -> Generator[None, None, None]:
            try:
                try:
                    yield
                except BaseException:
                    [][1]
            except BaseException:
                self.assertIsInstance(failure.Failure().value, IndexError)

        g = generator()
        next(g)
        f = getDivisionFailure()
        self._throwIntoGenerator(f, g)

    def test_ambiguousFailureFromGenerator(self) -> None:
        """
        When a generator reraises a different exception, creating a L{Failure}
        above the generator should find the reraised exception rather than
        original one.
        """

        def generator() -> Generator[None, None, None]:
            try:
                yield
            except BaseException:
                [][1]

        g = generator()
        next(g)
        f = getDivisionFailure()
        try:
            self._throwIntoGenerator(f, g)
        except BaseException:
            self.assertIsInstance(failure.Failure().value, IndexError)
