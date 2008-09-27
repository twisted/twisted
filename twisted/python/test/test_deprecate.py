# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for Twisted's deprecation framework, L{twisted.python.deprecate}.
"""

from twisted.trial.unittest import TestCase

from twisted.python.deprecate import _appendToDocstring
from twisted.python.deprecate import _getDeprecationDocstring
from twisted.python.deprecate import deprecated, getDeprecationWarningString
from twisted.python.reflect import fullyQualifiedName
from twisted.python.versions import Version



def dummyCallable():
    """
    Do nothing.

    This is used to test the deprecation decorators.
    """



class TestDeprecationWarnings(TestCase):

    def test_getDeprecationWarningString(self):
        """
        L{getDeprecationWarningString} returns a string that tells us that a
        callable was deprecated at a certain released version of Twisted.
        """
        version = Version('Twisted', 8, 0, 0)
        self.assertEqual(
            getDeprecationWarningString(self.test_getDeprecationWarningString,
                                        version),
            "twisted.python.test.test_deprecate.TestDeprecationWarnings."
            "test_getDeprecationWarningString was deprecated in "
            "Twisted 8.0.0")


    def test_deprecateEmitsWarning(self):
        """
        Decorating a callable with L{deprecated} emits a warning.
        """
        version = Version('Twisted', 8, 0, 0)
        dummy = deprecated(version)(dummyCallable)
        def addStackLevel():
            dummy()
        self.assertWarns(
            DeprecationWarning,
            getDeprecationWarningString(dummyCallable, version),
            __file__,
            addStackLevel)


    def test_deprecatedPreservesName(self):
        """
        The decorated function has the same name as the original.
        """
        version = Version('Twisted', 8, 0, 0)
        dummy = deprecated(version)(dummyCallable)
        self.assertEqual(dummyCallable.__name__, dummy.__name__)
        self.assertEqual(fullyQualifiedName(dummyCallable),
                         fullyQualifiedName(dummy))


    def test_getDeprecationDocstring(self):
        """
        L{_getDeprecationDocstring} returns a note about the deprecation to go
        into a docstring.
        """
        version = Version('Twisted', 8, 0, 0)
        self.assertEqual(
            "Deprecated in Twisted 8.0.0.", _getDeprecationDocstring(version))


    def test_deprecatedUpdatesDocstring(self):
        """
        The docstring of the deprecated function is appended with information
        about the deprecation.
        """

        version = Version('Twisted', 8, 0, 0)
        dummy = deprecated(version)(dummyCallable)

        _appendToDocstring(
            dummyCallable,
            _getDeprecationDocstring(version))

        self.assertEqual(dummyCallable.__doc__, dummy.__doc__)


    def test_versionMetadata(self):
        """
        Deprecating a function adds version information to the decorated
        version of that function.
        """
        version = Version('Twisted', 8, 0, 0)
        dummy = deprecated(version)(dummyCallable)
        self.assertEqual(version, dummy.deprecatedVersion)



class TestAppendToDocstring(TestCase):
    """
    Test the _appendToDocstring function.

    _appendToDocstring is used to add text to a docstring.
    """

    def test_appendToEmptyDocstring(self):
        """
        Appending to an empty docstring simply replaces the docstring.
        """

        def noDocstring():
            pass

        _appendToDocstring(noDocstring, "Appended text.")
        self.assertEqual("Appended text.", noDocstring.__doc__)


    def test_appendToSingleLineDocstring(self):
        """
        Appending to a single line docstring places the message on a new line,
        with a blank line separating it from the rest of the docstring.

        The docstring ends with a newline, conforming to Twisted and PEP 8
        standards. Unfortunately, the indentation is incorrect, since the
        existing docstring doesn't have enough info to help us indent
        properly.
        """

        def singleLineDocstring():
            """This doesn't comply with standards, but is here for a test."""

        _appendToDocstring(singleLineDocstring, "Appended text.")
        self.assertEqual(
            ["This doesn't comply with standards, but is here for a test.",
             "",
             "Appended text."],
            singleLineDocstring.__doc__.splitlines())
        self.assertTrue(singleLineDocstring.__doc__.endswith('\n'))


    def test_appendToMultilineDocstring(self):
        """
        Appending to a multi-line docstring places the messade on a new line,
        with a blank line separating it from the rest of the docstring.

        Because we have multiple lines, we have enough information to do
        indentation.
        """

        def multiLineDocstring():
            """
            This is a multi-line docstring.
            """

        def expectedDocstring():
            """
            This is a multi-line docstring.

            Appended text.
            """

        _appendToDocstring(multiLineDocstring, "Appended text.")
        self.assertEqual(
            expectedDocstring.__doc__, multiLineDocstring.__doc__)
