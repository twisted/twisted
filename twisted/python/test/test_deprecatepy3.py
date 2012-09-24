# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the parts of L{twisted.python._deprecatepy3}, the parts of
L{twisted.python.deprecate} which have been ported to Python 3.
"""

from __future__ import division, absolute_import

from warnings import simplefilter, catch_warnings

from twisted.trial.unittest import SynchronousTestCase

from twisted.python.versions import Version
from twisted.python._deprecatepy3 import (
    DEPRECATION_WARNING_FORMAT, getDeprecationWarningString, deprecated,
    _appendToDocstring, _getDeprecationDocstring,
    _fullyQualifiedName as fullyQualifiedName)


def dummyCallable():
    """
    Do nothing.

    This is used to test the deprecation decorators.
    """



def dummyReplacementMethod():
    """
    Do nothing.

    This is used to test the replacement parameter to L{deprecated}.
    """



class TestDeprecationWarnings(SynchronousTestCase):
    def test_getDeprecationWarningString(self):
        """
        L{getDeprecationWarningString} returns a string that tells us that a
        callable was deprecated at a certain released version of Twisted.
        """
        version = Version('Twisted', 8, 0, 0)
        self.assertEqual(
            getDeprecationWarningString(self.test_getDeprecationWarningString,
                                        version),
            "%s.TestDeprecationWarnings.test_getDeprecationWarningString "
            "was deprecated in Twisted 8.0.0" % (__name__,))


    def test_getDeprecationWarningStringWithFormat(self):
        """
        L{getDeprecationWarningString} returns a string that tells us that a
        callable was deprecated at a certain released version of Twisted, with
        a message containing additional information about the deprecation.
        """
        version = Version('Twisted', 8, 0, 0)
        format = DEPRECATION_WARNING_FORMAT + ': This is a message'
        self.assertEqual(
            getDeprecationWarningString(self.test_getDeprecationWarningString,
                                        version, format),
            '%s.TestDeprecationWarnings.test_getDeprecationWarningString was '
            'deprecated in Twisted 8.0.0: This is a message' % (__name__,))


    def test_deprecateEmitsWarning(self):
        """
        Decorating a callable with L{deprecated} emits a warning.
        """
        version = Version('Twisted', 8, 0, 0)
        dummy = deprecated(version)(dummyCallable)
        def addStackLevel():
            dummy()
        with catch_warnings(record=True) as caught:
            simplefilter("always")
            addStackLevel()
            self.assertEqual(caught[0].category, DeprecationWarning)
            self.assertEqual(str(caught[0].message), getDeprecationWarningString(dummyCallable, version))
            # rstrip in case .pyc/.pyo
            self.assertEqual(caught[0].filename.rstrip('co'), __file__.rstrip('co'))


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
            "Deprecated in Twisted 8.0.0.",
            _getDeprecationDocstring(version, ''))


    def test_deprecatedUpdatesDocstring(self):
        """
        The docstring of the deprecated function is appended with information
        about the deprecation.
        """

        version = Version('Twisted', 8, 0, 0)
        dummy = deprecated(version)(dummyCallable)

        _appendToDocstring(
            dummyCallable,
            _getDeprecationDocstring(version, ''))

        self.assertEqual(dummyCallable.__doc__, dummy.__doc__)


    def test_versionMetadata(self):
        """
        Deprecating a function adds version information to the decorated
        version of that function.
        """
        version = Version('Twisted', 8, 0, 0)
        dummy = deprecated(version)(dummyCallable)
        self.assertEqual(version, dummy.deprecatedVersion)


    def test_getDeprecationWarningStringReplacement(self):
        """
        L{getDeprecationWarningString} takes an additional replacement parameter
        that can be used to add information to the deprecation.  If the
        replacement parameter is a string, it will be interpolated directly into
        the result.
        """
        version = Version('Twisted', 8, 0, 0)
        warningString = getDeprecationWarningString(
            self.test_getDeprecationWarningString, version,
            replacement="something.foobar")
        self.assertEqual(
            warningString,
            "%s was deprecated in Twisted 8.0.0; please use something.foobar "
            "instead" % (
                fullyQualifiedName(self.test_getDeprecationWarningString),))


    def test_getDeprecationWarningStringReplacementWithCallable(self):
        """
        L{getDeprecationWarningString} takes an additional replacement parameter
        that can be used to add information to the deprecation. If the
        replacement parameter is a callable, its fully qualified name will be
        interpolated into the result.
        """
        version = Version('Twisted', 8, 0, 0)
        warningString = getDeprecationWarningString(
            self.test_getDeprecationWarningString, version,
            replacement=dummyReplacementMethod)
        self.assertEqual(
            warningString,
            "%s was deprecated in Twisted 8.0.0; please use "
            "%s.dummyReplacementMethod instead" % (
                fullyQualifiedName(self.test_getDeprecationWarningString),
                __name__))


    def test_deprecatedReplacement(self):
        """
        L{deprecated} takes an additional replacement parameter that can be used
        to indicate the new, non-deprecated method developers should use.  If
        the replacement parameter is a string, it will be interpolated directly
        into the warning message.
        """
        version = Version('Twisted', 8, 0, 0)
        dummy = deprecated(version, "something.foobar")(dummyCallable)
        self.assertEqual(dummy.__doc__,
            "\n"
            "    Do nothing.\n\n"
            "    This is used to test the deprecation decorators.\n\n"
            "    Deprecated in Twisted 8.0.0; please use "
            "something.foobar"
            " instead.\n"
            "    ")


    def test_deprecatedReplacementWithCallable(self):
        """
        L{deprecated} takes an additional replacement parameter that can be used
        to indicate the new, non-deprecated method developers should use.  If
        the replacement parameter is a callable, its fully qualified name will
        be interpolated into the warning message.
        """
        version = Version('Twisted', 8, 0, 0)
        decorator = deprecated(version, replacement=dummyReplacementMethod)
        dummy = decorator(dummyCallable)
        self.assertEqual(dummy.__doc__,
            "\n"
            "    Do nothing.\n\n"
            "    This is used to test the deprecation decorators.\n\n"
            "    Deprecated in Twisted 8.0.0; please use "
            "%s.dummyReplacementMethod instead.\n"
            "    " % (__name__,))



class TestAppendToDocstring(SynchronousTestCase):
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
