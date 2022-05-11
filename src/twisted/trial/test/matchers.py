# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Hamcrest matchers useful throughout the test suite.
"""

from typing import Callable, TypeVar

from hamcrest.core.base_matcher import BaseMatcher
from hamcrest.core.description import Description
from hamcrest.core.matcher import Matcher

_A = TypeVar("_A")
_B = TypeVar("_B")


class _MatchAfter(BaseMatcher[_A]):
    """
    The implementation of L{after}.

    @ivar f: The function to apply.
    @ivar m: The matcher to use on the result.
    """

    def __init__(self, f: Callable[[_A], _B], m: Matcher[_B]):
        self.f = f
        self.m = m

    def _matches(self, item: _A) -> bool:
        """
        Apply the function and delegate matching on the result.
        """
        return self.m.matches(self.f(item))

    def describe_to(self, description: Description) -> None:
        """
        Create a text description of the match requirement.
        """
        description.append_text(f"[after {self.f}] ")
        self.m.describe_to(description)


def after(f: Callable[[_A], _B], m: Matcher[_B]) -> Matcher[_A]:
    """
    Create a matcher which calls C{f} and uses C{m} to match the result.
    """
    return _MatchAfter(f, m)
