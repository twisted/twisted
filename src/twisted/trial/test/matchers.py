# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Hamcrest matchers useful throughout the test suite.
"""

from typing import Any, Callable

from hamcrest.core.base_matcher import BaseMatcher
from hamcrest.core.description import Description
from hamcrest.core.matcher import Matcher


class _MatchAfter(BaseMatcher):
    """
    The implementation of L{after}.

    @ivar f: The function to apply.
    @ivar m: The matcher to use on the result.
    """

    def __init__(self, f: Callable[[Any], Any], m: Matcher):
        self.f = f
        self.m = m

    def _matches(self, item: Any) -> bool:
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


def after(f: Callable[[Any], Any], m: Matcher) -> Matcher:
    """
    Create a matcher which calls C{f} and uses C{m} to match the result.
    """
    return _MatchAfter(f, m)
