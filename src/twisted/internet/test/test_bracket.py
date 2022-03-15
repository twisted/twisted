# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for ``twisted.internet.defer.bracket``.
"""

from functools import partial
from typing import Any

from hamcrest import assert_that, equal_to, instance_of, is_

from ...trial.unittest import SynchronousTestCase
from ..defer import bracket, fail, succeed


class _BracketTestMixin:
    """
    Tests for ``bracket``.
    """

    def wrap_success(self, result: Any) -> Any:
        """
        :see: ``make_bracket_test``
        """
        raise NotImplementedError()

    def wrap_failure(self, exception: Any) -> Any:
        """
        :see: ``make_bracket_test``
        """
        raise NotImplementedError()

    def test_success(self) -> None:
        """
        ``bracket`` calls ``first`` then ``between`` then ``last`` and returns a
        ``Deferred`` that fires with the result of ``between``.
        """
        expected = object()
        actions: list[str] = []
        first = partial(actions.append, "first")

        def between():
            actions.append("between")
            return self.wrap_success(expected)

        last = partial(actions.append, "last")
        actual = self.successResultOf(bracket(first, last, between))
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

        actions = []
        first = partial(actions.append, "first")

        def between():
            actions.append("between")
            return self.wrap_failure(SomeException())

        last = partial(actions.append, "last")
        result = self.failureResultOf(bracket(first, last, between)).value
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

        actions = []
        first = partial(actions.append, "first")

        def between():
            actions.append("between")
            return self.wrap_success(None)

        def last():
            actions.append("last")
            return self.wrap_failure(SomeException())

        result = self.failureResultOf(bracket(first, last, between)).value
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

        actions = []
        first = partial(actions.append, "first")

        def between():
            actions.append("between")
            return self.wrap_failure(SomeException())

        def last():
            actions.append("last")
            return self.wrap_failure(AnotherException())

        result = self.failureResultOf(bracket(first, last, between)).value
        assert_that(
            result,
            instance_of(AnotherException),
        )
        assert_that(
            actions,
            equal_to(["first", "between", "last"]),
        )

    def test_first_failure(self):
        """
        If the ``first`` action fails then ``bracket`` fails the same way and
        runs neither the ``between`` nor ``last`` actions.
        """

        class SomeException(Exception):
            pass

        actions = []

        def first():
            actions.append("first")
            return self.wrap_failure(SomeException())

        between = partial(actions.append, "between")
        last = partial(actions.append, "last")

        value = self.failureResultOf(bracket(first, last, between)).value
        assert_that(
            value,
            instance_of(SomeException),
        )
        assert_that(
            actions,
            equal_to(["first"]),
        )


class BracketTests(_BracketTestMixin, SynchronousTestCase):
    """
    Tests for ``bracket`` when used with actions that return a value or raise
    an exception directly.
    """

    def wrap_success(self, result):
        return result

    def wrap_failure(self, exception):
        raise exception


class SynchronousDeferredBracketTests(_BracketTestMixin, SynchronousTestCase):
    """
    Tests for ``bracket`` when used with actions that return a value or raise
    an exception wrapped in a ``Deferred``.
    """

    def wrap_success(self, result):
        return succeed(result)

    def wrap_failure(self, exception):
        return fail(exception)
