# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Hamcrest matchers useful throughout the test suite.
"""

from typing import IO, Callable, Optional, Type, TypeVar

import zope.interface
from zope.interface import Interface
from zope.interface.verify import verifyObject

from hamcrest.core.base_matcher import BaseMatcher
from hamcrest.core.description import Description
from hamcrest.core.matcher import Matcher

from twisted.python.filepath import IFilePath
from twisted.python.reflect import fullyQualifiedName

_A = TypeVar("_A")
_B = TypeVar("_B")


class _MatchAfter(BaseMatcher[_A]):
    """
    The implementation of L{after}.

    @ivar f: The function to apply.
    @ivar m: The matcher to use on the result.

    @ivar _e: After trying to apply the function fails with an exception, the
        exception that was raised.  This can later be used by
        L{describe_mismatch}.
    """

    def __init__(self, f: Callable[[_A], _B], m: Matcher[_B]) -> None:
        self.f = f
        self.m = m
        self._e: Optional[Exception] = None

    def _matches(self, item: _A) -> bool:
        """
        Apply the function and delegate matching on the result.
        """
        try:
            transformed = self.f(item)
        except Exception as e:
            self._e = e
            return False
        else:
            return self.m.matches(transformed)

    def describe_mismatch(self, item: _A, mismatch_description: Description) -> None:
        """
        Describe the mismatching item or the exception that occurred while
        pre-processing it.

        @note: Since the exception reporting here depends on mutable state it
            will only work as long as PyHamcrest calls methods in the right
            order.  The PyHamcrest Matcher interface doesn't seem to allow
            implementing this functionality in a more reliable way (see the
            implementation of L{assert_that}).
        """
        if self._e is None:
            super().describe_mismatch(item, mismatch_description)
        else:
            mismatch_description.append_text(
                f"{fullyQualifiedName(self.f)}({item!r}) raised\n"
                f"{fullyQualifiedName(self._e.__class__)}: {self._e}"
            )

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


def fileContents(m: Matcher[str], encoding: str = "utf-8") -> Matcher[IFilePath]:
    """
    Create a matcher which matches a L{FilePath} the contents of which are
    matched by L{m}.
    """

    def getContent(p: IFilePath) -> str:
        f: IO[bytes]
        with p.open() as f:
            return f.read().decode(encoding)

    return after(getContent, m)


class _MatchInterfaceProvider(BaseMatcher[object]):
    """
    The implementation of L{provides}.

    @ivar _interface_type: The zope.interface.Interface subclass to check that a given
        object provides.

    @ivar _verify_exception: The details of   This can later be used by
        L{describe_mismatch}.
    """

    def __init__(self, interface_type: Type[Interface]):
        self._interface_type = interface_type
        self._verify_exception: Optional[zope.interface.Invalid] = None

    def _matches(self, item: object) -> bool:
        try:
            verifyObject(self._interface_type, item, tentative=False)
        except zope.interface.Invalid as e:
            self._verify_exception = e
            return False
        return True

    def describe_mismatch(self, item: object, description: Description) -> None:
        if self._verify_exception is None:
            super().describe_mismatch(item, description)
        else:
            description.append_description_of(item).append_text(
                f" does not implement {fullyQualifiedName(self._interface_type)}: "
                f" {self._verify_exception}"
            )

    def describe_to(self, description: Description) -> None:
        description.append_text(f"provides {self._interface_type.__name__}")


def provides(interface_type: Type[Interface]) -> Matcher[object]:
    """
    Create a matcher which matches objects that provide the given L{interface_type}.
    """
    return _MatchInterfaceProvider(interface_type)
