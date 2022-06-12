# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Hamcrest matchers useful throughout the test suite.
"""

from hamcrest import equal_to, has_length, has_properties
from hamcrest.core.matcher import Matcher


def matches_result(
    successes: Matcher = equal_to(0),
    errors: Matcher = has_length(0),
    failures: Matcher = has_length(0),
    skips: Matcher = has_length(0),
    expectedFailures: Matcher = has_length(0),
    unexpectedSuccesses: Matcher = has_length(0),
) -> Matcher:
    """
    Match a L{TestCase} instances with matching attributes.
    """
    return has_properties(
        {
            "successes": successes,
            "errors": errors,
            "failures": failures,
            "skips": skips,
            "expectedFailures": expectedFailures,
            "unexpectedSuccesses": unexpectedSuccesses,
        }
    )
