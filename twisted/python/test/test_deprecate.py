# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for Twisted's deprecation framework, L{twisted.python.deprecate}.
"""

from datetime import datetime, timedelta

from twisted.trial.unittest import TestCase

from twisted.python.deprecate import _appendToDocstring
from twisted.python.deprecate import _getDeprecationDocstring
from twisted.python.deprecate import deprecated, getDeprecationWarningString
from twisted.python.deprecate import _Release, _DeprecationPolicy
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



class DecoratorTestMixin:
    """
    A mixin for TestCases which tests a number of generic properties which most
    or all decorators should have.
    """
    def decorate(self, callable):
        raise NotImplementedError(
            "%s did not override decorate" % (self.__class__,))


    def test_name(self):
        """
        The C{__name__} and C{func_name} attributes of the object returned by
        the decorator have the same values as those attributes on the original
        function object.
        """
        def foo():
            pass
        bar = self.decorate(foo)
        self.assertEqual(foo.__name__, bar.__name__)
        self.assertEqual(foo.func_name, bar.func_name)


    def test_doc(self):
        """
        The C{__doc__} attribute of the object returned by the decorator has
        the same value as as that attribute of the original function object.
        """
        def foo():
            "bar"
        baz = self.decorate(foo)
        self.assertEqual(foo.__doc__, baz.__doc__)


    def test_attributes(self):
        """
        The decorator returns an object with the same arbitrary additional
        attributes as were present on the original function object at the time
        of decoration.
        """
        def foo():
            pass
        foo.bar = object()
        baz = self.decorate(foo)
        self.assertIdentical(foo.bar, baz.bar)


    def test_result(self):
        """
        The decorator returns a callable which returns the return value of the
        decorated function.
        """
        result = object()
        self.assertIdentical(self.decorate(lambda: result)(), result)


    def test_positional(self):
        """
        The decorator returns a callable which accepts positional arguments and
        passes them on to the decorated function.
        """
        arg = object()
        called = []
        self.decorate(lambda *args: called.extend(args))(arg)
        self.assertEqual(called, [arg])


    def test_keyword(self):
        """
        The decorator returns a callable which accepts keyword arguments and
        passes them on to the decorated function.
        """
        arg = object()
        called = {}
        self.decorate(lambda **kw: called.update(kw))(foo=arg)
        self.assertEqual(called, {'foo': arg})



class AutoDeprecateTests(DecoratorTestMixin, TestCase):
    """
    Tests for L{_DeprecationPolicy.decorator}, the API for creating a decorator
    which emits whichever kind of deprecation warning is appropriate based on
    what versions are released and when.
    """
    def decorate(self, callable):
        """
        Decorate C{callable} with C{_DeprecationPolicy.decorator(release)}.
        """
        v1 = Version('foo', 1, 0, 0)
        r1 = _Release(v1, datetime(2001, 1, 1))
        model = _DeprecationPolicy(
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=0,
            allReleases=[r1])

        return model.decorator(r1)(callable)



class DeprecationPolicyTests(TestCase):
    """
    Tests for L{_DeprecationPolicy}.
    """
    v0 = Version('foo', 0, 9, 0)
    v1 = Version('foo', 1, 0, 0)
    v2 = Version('foo', 1, 1, 0)
    v3 = Version('foo', 2, 0, 0)

    def test_byReleaseCount(self):
        """
        When the L{_Release} passed to L{_DeprecationPolicy.deprecationType} is
        less than C{minimumPendingReleases} releases before the current
        release, L{PendingDeprecationWarning} is returned.
        """
        # The initial release in which nothing was deprecated.
        r0 = _Release(self.v0, datetime(2000, 1, 1))
        # Three new releases all happen on the same day
        r1 = _Release(self.v1, datetime(2001, 1, 1))
        r2 = _Release(self.v2, datetime(2001, 1, 1))
        r3 = _Release(self.v3, datetime(2001, 1, 1))

        # A model which requires 2 releases before a pending deprecation turns
        # into a deprecation.  It has no minimum time change requirement.
        model = _DeprecationPolicy(
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=2,
            allReleases=[r0, r1, r2, r3])

        # A deprecation introduced after the latest release is pending because
        # it has not been part of any releases.
        self.assertIdentical(
            model.deprecationType(r3), PendingDeprecationWarning)

        # A deprecation introduced in the latest release is pending because it
        # has been part of one release, which is not at least the required
        # minimum of two.
        self.assertIdentical(
            model.deprecationType(r2), PendingDeprecationWarning)

        # For the same reason, a deprecation introduced in the release before
        # the latest release is also still pending.
        self.assertIdentical(
            model.deprecationType(r1), PendingDeprecationWarning)

        # A deprecation introduced two releases before the latest release has
        # already been pending in two releases, the required minimum, so it is
        # no longer pending in the latest release.
        self.assertIdentical(
            model.deprecationType(r0), DeprecationWarning)


    def test_byReleaseInterval(self):
        """
        When the L{_Release} passed to L{_DeprecationPolicy.deprecationType} has
        a date less than C{minimumDeprecationPeriod} less than the date of the
        current release, L{PendingDeprecationWarning} is returned.
        """
        # The initial deprecation-free release.
        r0 = _Release(self.v0, datetime(2001, 1, 1))
        # Three days with one release on each day.
        r1 = _Release(self.v1, datetime(2001, 1, 2))
        r2 = _Release(self.v2, datetime(2001, 1, 3))
        r3 = _Release(self.v3, datetime(2001, 1, 4))

        # A model which requires two days before a pending deprecationg turns
        # into a deprecation.  It has no minimum on the number of releases.
        model = _DeprecationPolicy(
            minimumPendingPeriod=timedelta(days=2),
            minimumPendingReleases=0,
            allReleases=[r0, r1, r2, r3])

        # A deprecation introduced after the latest release is pending because
        # it has not been part of any releases.
        self.assertIdentical(
            model.deprecationType(r3), PendingDeprecationWarning)

        # A deprecation introduced in the release one day before the latest
        # release is still pending because it hasn't been pending for more than
        # the minimum required period of two days.
        self.assertIdentical(
            model.deprecationType(r2), PendingDeprecationWarning)

        # Similarly, a deprecation introduced in the release two days before
        # the latest release is also still pending.
        self.assertIdentical(
            model.deprecationType(r1), PendingDeprecationWarning)

        # A deprecation introduced in the first release before the release two
        # days before the latest release is no longer pending.
        self.assertIdentical(
            model.deprecationType(r0), DeprecationWarning)


    def test_misorderedByDate(self):
        """
        If the list of releases passed to L{_DeprecationPolicy} is not in
        ascending order by date, L{ValueError} is raised.
        """
        r1 = _Release(self.v1, datetime(2002, 1, 1))
        r2 = _Release(self.v2, datetime(2001, 1, 1))
        self.assertRaises(
            ValueError,
            _DeprecationPolicy,
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=0,
            allReleases=[r1, r2])

        r1 = _Release(self.v1, datetime(2001, 1, 1))
        r2 = _Release(self.v2, datetime(2002, 1, 1))
        r3 = _Release(self.v3, datetime(2001, 1, 1))
        self.assertRaises(
            ValueError,
            _DeprecationPolicy,
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=0,
            allReleases=[r1, r2, r3])


    def test_misorderedByVersion(self):
        """
        If the list of releases passed to L{_DeprecationPolicy} is not in
        ascending order by version, L{ValueError} is raised.
        """
        r1 = _Release(self.v2, datetime(2001, 1, 1))
        r2 = _Release(self.v1, datetime(2002, 1, 1))
        self.assertRaises(
            ValueError,
            _DeprecationPolicy,
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=0,
            allReleases=[r1, r2])

        r1 = _Release(self.v2, datetime(2001, 1, 1))
        r2 = _Release(self.v3, datetime(2002, 1, 1))
        r3 = _Release(self.v1, datetime(2003, 1, 1))
        self.assertRaises(
            ValueError,
            _DeprecationPolicy,
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=0,
            allReleases=[r1, r2, r3])


    def test_noReleases(self):
        """
        If no releases are passed to L{DeprecationModel}, L{ValueError} is
        raised.
        """
        self.assertRaises(
            ValueError,
            _DeprecationPolicy,
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=0,
            allReleases=[])


    def test_deprecate(self):
        """
        L{_DeprecationPolicy.warn} emits a L{PendingDeprecationWarning} if
        passed a L{_Release} which is in the pending deprecation phase and
        emits a L{DeprecationWarning} if passed a L{_Release} which is not in
        that phase.
        """
        r1 = _Release(self.v1, datetime(2001, 1, 1))
        r2 = _Release(self.v2, datetime(2002, 1, 1))
        model = _DeprecationPolicy(
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=0,
            allReleases=[r1, r2])
        self.assertWarns(
            DeprecationWarning,
            "bar is deprecated.  use baz instead.",
            __file__,
            lambda:
                model.warn(r1, "bar is deprecated.  use baz instead."))
        self.assertWarns(
            PendingDeprecationWarning,
            "bar is deprecated.  use baz instead.",
            __file__,
            lambda:
                model.warn(r2, "bar is deprecated.  use baz instead."))


    def test_decorate(self):
        """
        L{_DeprecationPolicy.decorate} decorates a function so that when it is
        called it emits a L{PendingDeprecationWarning} or a
        L{_DeprecationPolicy} warning.
        """
        def bar():
            pass

        r1 = _Release(self.v1, datetime(2001, 1, 1))
        r2 = _Release(self.v2, datetime(2002, 1, 1))
        model = _DeprecationPolicy(
            minimumPendingPeriod=timedelta(),
            minimumPendingReleases=0,
            allReleases=[r1, r2])
        self.assertWarns(
            DeprecationWarning,
            "%s.bar was deprecated in foo 1.0.0" % (__name__,),
            __file__,
            lambda: model.decorator(r1)(bar)())
        self.assertWarns(
            PendingDeprecationWarning,
            "%s.bar was deprecated in foo 1.1.0" % (__name__,),
            __file__,
            lambda: model.decorator(r2)(bar)())
