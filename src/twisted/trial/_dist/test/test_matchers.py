"""
Tests for L{twisted.trial._dist.test.matchers}.
"""

from typing import Sequence

from hamcrest import anything, assert_that, contains_string, equal_to, is_, not_
from hamcrest.core.core.allof import AllOf
from hamcrest.core.matcher import Matcher
from hamcrest.core.string_description import StringDescription
from hypothesis import given
from hypothesis.strategies import booleans, integers, just, lists

from twisted.trial.unittest import SynchronousTestCase
from .matchers import HasSum, IsSequenceOf, S


class HasSumTests(SynchronousTestCase):
    """
    Tests for L{HasSum}.
    """

    sequences = lists(integers())
    # For the moment we know we always have integers
    zeros = just(0)

    @given(sequences, zeros)
    def test_matches(self, seq: Sequence[S], zero: S) -> None:
        """
        L{HasSum} matches a sequence if the elements sum to a value matched by
        the parameterized matcher.
        """
        expected = sum(seq, zero)

        description = StringDescription()
        matcher = HasSum(equal_to(expected), zero)
        assert_that(matcher.matches(seq, description), equal_to(True))
        assert_that(str(description), equal_to(""))

    @given(sequences, zeros)
    def test_mismatches(self, seq: Sequence[S], zero: S) -> None:
        """
        L{HasSum} does not match a sequence if the elements do not sum to a
        value matched by the parameterized matcher.
        """
        # A matcher that never matches.
        sumMatcher: Matcher[S] = not_(anything())

        actualDescription = StringDescription()
        matcher = HasSum(sumMatcher, zero)
        assert_that(matcher.matches(seq, actualDescription), equal_to(False))

        sumMatcherDescription = StringDescription()
        sumMatcherDescription.append_description_of(sumMatcher)

        assert_that(
            str(actualDescription),
            is_(
                AllOf(
                    contains_string("a sequence with sum"),
                    contains_string(str(sumMatcherDescription)),
                )
            ),
        )


class IsSequenceOfTests(SynchronousTestCase):
    """
    Tests for L{IsSequenceOf}.
    """

    sequences = lists(booleans())

    @given(integers(min_value=0, max_value=1000))
    def test_matches(self, num_items: int) -> None:
        """
        L{IsSequenceOf} matches a sequence if all of the elements are
        matched by the parameterized matcher.
        """
        seq = [True] * num_items
        matcher = IsSequenceOf(equal_to(True))

        actualDescription = StringDescription()
        assert_that(matcher.matches(seq, actualDescription), equal_to(True))
        assert_that(str(actualDescription), equal_to(""))

    @given(integers(min_value=0, max_value=1000), integers(min_value=0, max_value=1000))
    def test_mismatches(self, num_before: int, num_after: int) -> None:
        """
        L{IsSequenceOf} does not match a sequence if any of the elements
        are not matched by the parameterized matcher.
        """
        # Hide the non-matching value somewhere in the sequence.
        seq = [True] * num_before + [False] + [True] * num_after
        matcher = IsSequenceOf(equal_to(True))

        actualDescription = StringDescription()
        assert_that(matcher.matches(seq, actualDescription), equal_to(False))
        assert_that(
            str(actualDescription),
            is_(
                AllOf(
                    contains_string("a sequence containing only"),
                    contains_string(f"not sequence with element #{num_before}"),
                )
            ),
        )
