# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for ``twisted.trial._dist.control.bracket``.
"""

from functools import partial
from typing import Any, Callable, List

from attrs import define
from hamcrest import assert_that, equal_to, instance_of, is_

from ....internet.defer import fail, succeed
from ...runner import TestLoader, TrialSuite
from ...unittest import SynchronousTestCase
from ..control import bracket


@define
class BracketTests:
    """
    Tests for ``bracket``.
    """

    case: SynchronousTestCase
    wrap_success: Callable
    wrap_failure: Callable

    def test_success(self) -> None:
        """
        ``bracket`` calls ``first`` then ``between`` then ``last`` and returns a
        ``Deferred`` that fires with the result of ``between``.
        """
        expected = object()
        actions: List[str] = []
        first = partial(actions.append, "first")

        def between() -> Any:
            actions.append("between")
            return self.wrap_success(expected)

        last = partial(actions.append, "last")
        actual = self.case.successResultOf(bracket(first, last, between))
        assert_that(
            actual,
            is_(expected),
        )
        assert_that(
            actions,
            equal_to(["first", "between", "last"]),
        )

    def test_failure(self) -> None:
        """
        ``bracket`` calls ``first`` then ``between`` then ``last`` and returns a
        ``Deferred`` that fires with the failure result of ``between``.
        """

        class SomeException(Exception):
            pass

        actions: List[str] = []
        first = partial(actions.append, "first")

        def between() -> Any:
            actions.append("between")
            return self.wrap_failure(SomeException())

        last = partial(actions.append, "last")
        result = self.case.failureResultOf(bracket(first, last, between)).value
        assert_that(
            result,
            instance_of(SomeException),
        )
        assert_that(
            actions,
            equal_to(["first", "between", "last"]),
        )

    def test_success_with_failing_last(self) -> None:
        """
        If the ``between`` action succeeds and the ``last`` action fails then
        ``bracket`` fails the same way as the ``last`` action.
        """

        class SomeException(Exception):
            pass

        actions: List[str] = []
        first = partial(actions.append, "first")

        def between() -> Any:
            actions.append("between")
            return self.wrap_success(None)

        def last() -> Any:
            actions.append("last")
            return self.wrap_failure(SomeException())

        result = self.case.failureResultOf(bracket(first, last, between)).value
        assert_that(
            result,
            instance_of(SomeException),
        )
        assert_that(
            actions,
            equal_to(["first", "between", "last"]),
        )

    def test_failure_with_failing_last(self) -> None:
        """
        If both the ``between`` and ``last`` actions fail then ``bracket`` fails
        the same way as the ``last`` action.
        """

        class SomeException(Exception):
            pass

        class AnotherException(Exception):
            pass

        actions: List[str] = []
        first = partial(actions.append, "first")

        def between() -> Any:
            actions.append("between")
            return self.wrap_failure(SomeException())

        def last() -> Any:
            actions.append("last")
            return self.wrap_failure(AnotherException())

        result = self.case.failureResultOf(bracket(first, last, between)).value
        assert_that(
            result,
            instance_of(AnotherException),
        )
        assert_that(
            actions,
            equal_to(["first", "between", "last"]),
        )

    def test_first_failure(self) -> None:
        """
        If the ``first`` action fails then ``bracket`` fails the same way and
        runs neither the ``between`` nor ``last`` actions.
        """

        class SomeException(Exception):
            pass

        actions: List[str] = []

        def first() -> Any:
            actions.append("first")
            return self.wrap_failure(SomeException())

        between = partial(actions.append, "between")
        last = partial(actions.append, "last")

        value = self.case.failureResultOf(bracket(first, last, between)).value
        assert_that(
            value,
            instance_of(SomeException),
        )
        assert_that(
            actions,
            equal_to(["first"]),
        )


class UnwrappedBracketTests(SynchronousTestCase, BracketTests):
    """
    Tests for ``bracket`` when used with actions that return a value or raise
    an exception directly.
    """

    def __init__(self, name: str) -> None:
        def raise_(exc: BaseException) -> None:
            raise exc

        SynchronousTestCase.__init__(self, name)
        BracketTests.__init__(self, self, lambda x: x, raise_)
        return None


class SynchronousDeferredBracketTests(SynchronousTestCase, BracketTests):
    """
    Tests for ``bracket`` when used with actions that return a value or raise
    an exception wrapped in a ``Deferred``.
    """

    def __init__(self, name: str) -> None:
        def raise_(exc: BaseException) -> None:
            raise exc

        SynchronousTestCase.__init__(self, name)
        BracketTests.__init__(self, self, succeed, fail)
        return None


def _loadParameterizedCases(base: type, testCaseClasses: List[type]) -> TrialSuite:
    """
    Discover test case names from a base type and return a suite containing a
    test case for each case for each test case class.
    """
    loader = TestLoader()
    methods = [loader.methodPrefix + name for name in loader.getTestCaseNames(base)]
    cases: List[SynchronousTestCase] = []
    for cls in testCaseClasses:
        cases.extend([cls(name) for name in methods])
    return TrialSuite(cases)


def testSuite() -> TrialSuite:
    """
    Load all permutations of the bracket test cases.
    """
    return _loadParameterizedCases(
        BracketTests,
        [
            UnwrappedBracketTests,
            SynchronousDeferredBracketTests,
        ],
    )
