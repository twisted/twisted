"""
Tests for L{twisted.trial.test.matchers}.
"""
from zope.interface import Interface, implementer

from hamcrest import anything, assert_that, contains_string, equal_to, not_
from hamcrest.core.core.allof import AllOf
from hamcrest.core.string_description import StringDescription
from hypothesis import given
from hypothesis.strategies import just, sampled_from, text

from twisted.python.filepath import FilePath
from twisted.trial.unittest import SynchronousTestCase
from .matchers import fileContents, provides


class FileContentsTests(SynchronousTestCase):
    """
    Tests for L{fileContents}.
    """

    @given(text(), just("utf-8"))
    def test_matches(self, contents: str, encoding: str) -> None:
        """
        L{fileContents} matches a L{IFilePath} that refers to a file that
        contains a string that is matched by the parameterized matcher.

        :param contents: The text string to place in the file and match
            against.

        :param encoding: The text encoding to use to encode C{contents} when
            writing to the file.
        """
        p = FilePath(self.mktemp())
        p.setContent(contents.encode(encoding))

        description = StringDescription()
        assert_that(
            fileContents(equal_to(contents)).matches(p, description), equal_to(True)
        )
        assert_that(str(description), equal_to(""))

    @given(
        just("some text, it doesn't matter what"),
        sampled_from(["ascii", "latin-1", "utf-8"]),
    )
    def test_mismatches(self, contents: str, encoding: str) -> None:
        """
        L{fileContents} does not match an L{IFilePath} that refers to a
        file that contains a string that is not matched by the parameterized
        matcher.

        :param contents: The text string to place in the file and match
            against.

        :param encoding: The text encoding to use to encode C{contents} when
            writing to the file.
        """
        p = FilePath(self.mktemp())
        p.setContent(contents.encode(encoding))

        description = StringDescription()
        assert_that(
            fileContents(not_(anything())).matches(p, description), equal_to(False)
        )
        assert_that(str(description), equal_to(f"was <{p}>"))

    def test_ioerror(self) -> None:
        """
        L{fileContents} reports details of any I/O error encountered while
        attempting to match.
        """
        p = FilePath(self.mktemp())

        description = StringDescription()
        assert_that(fileContents(anything()).matches(p, description), equal_to(False))
        assert_that(
            str(description),
            # It must contain at least ...
            AllOf(
                # the name of the matcher.
                contains_string("fileContents"),
                # the name of the exception raised.
                contains_string("FileNotFoundError"),
                # the repr (so weird values are escaped) of the path being
                # matched against.
                contains_string(repr(p.path)),
            ),
        )


class EmptyInterface(Interface):
    ...


class NonemptyInterface(Interface):
    def required_method() -> None:
        ...


class ProvidesTests(SynchronousTestCase):
    """
    Tests for L{fileContents}.
    """

    def test_matches_an_implementer_instance(self) -> None:
        @implementer(EmptyInterface)
        class EmptyClass:
            ...

        assert_that(provides(EmptyInterface).matches(EmptyClass()), equal_to(True))

    def test_rejects_a_blank_object(self) -> None:
        assert_that(provides(NonemptyInterface).matches(object()), equal_to(False))

    def test_rejects_if_implementer_decorator_missing(self) -> None:
        class MissingDecorator:
            """Implements NonemptyInterface, but is not marked as doing so."""

            def required_method(self) -> None:
                ...

        assert_that(
            provides(NonemptyInterface).matches(MissingDecorator()), equal_to(False)
        )
