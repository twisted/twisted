# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for parts of our release automation system.
"""

import os
import pathlib
import textwrap

from setuptools.dist import Distribution
from twisted.trial.unittest import SynchronousTestCase

from twisted.python import _setup
from twisted.python._setup import (
    getSetupArgs,
    ConditionalExtension,
)


class SetupTests(SynchronousTestCase):
    """
    Tests for L{getSetupArgs}.
    """

    def test_conditionalExtensions(self):
        """
        Will return the arguments with a custom build_ext which knows how to
        check whether they should be built.
        """
        good_ext = ConditionalExtension(
            "whatever", ["whatever.c"], condition=lambda b: True
        )
        bad_ext = ConditionalExtension(
            "whatever", ["whatever.c"], condition=lambda b: False
        )

        path = pathlib.Path(self.mktemp())
        path.touch(exist_ok=False)
        args = getSetupArgs(extensions=[good_ext, bad_ext], readme=path)

        # ext_modules should be set even though it's not used.  See comment
        # in getSetupArgs
        self.assertEqual(args["ext_modules"], [good_ext, bad_ext])
        cmdclass = args["cmdclass"]
        build_ext = cmdclass["build_ext"]
        builder = build_ext(Distribution())
        builder.prepare_extensions()
        self.assertEqual(builder.extensions, [good_ext])

    def test_win32Definition(self):
        """
        When building on Windows NT, the WIN32 macro will be defined as 1 on
        the extensions.
        """
        ext = ConditionalExtension(
            "whatever", ["whatever.c"], define_macros=[("whatever", 2)]
        )

        path = pathlib.Path(self.mktemp())
        path.touch(exist_ok=False)
        args = getSetupArgs(extensions=[ext], readme=path)

        builder = args["cmdclass"]["build_ext"](Distribution())
        self.patch(os, "name", "nt")
        builder.prepare_extensions()
        self.assertEqual(ext.define_macros, [("whatever", 2), ("WIN32", 1)])


class FakeModule:
    """
    A fake module, suitable for dependency injection in testing.
    """

    def __init__(self, attrs):
        """
        Initializes a fake module.

        @param attrs: The attrs that will be accessible on the module.
        @type attrs: C{dict} of C{str} (Python names) to objects
        """
        self._attrs = attrs

    def __getattr__(self, name):
        """
        Gets an attribute of this fake module from its attrs.

        @raise AttributeError: When the requested attribute is missing.
        """
        try:
            return self._attrs[name]
        except KeyError:
            raise AttributeError()


fakeCPythonPlatform = FakeModule({"python_implementation": lambda: "CPython"})
fakeOtherPlatform = FakeModule({"python_implementation": lambda: "lvhpy"})


class WithPlatformTests(SynchronousTestCase):
    """
    Tests for L{_checkCPython} when used with a (fake) C{platform} module.
    """

    def test_cpython(self):
        """
        L{_checkCPython} returns C{True} when C{platform.python_implementation}
        says we're running on CPython.
        """
        self.assertTrue(_setup._checkCPython(platform=fakeCPythonPlatform))

    def test_other(self):
        """
        L{_checkCPython} returns C{False} when C{platform.python_implementation}
        says we're not running on CPython.
        """
        self.assertFalse(_setup._checkCPython(platform=fakeOtherPlatform))

    """
    Tests for C{_getLongDescriptionArgs()}

    Note that the validity of the reStructuredText syntax is tested separately
    using L{twine check} in L{tox.ini}.
    """

    def test_generate(self):
        """
        L{getSetupArgs()} outputs a L{long_description} in
        reStructuredText format. Local links are transformed into absolute ones
        that point at the Twisted GitHub repository.
        """
        path = pathlib.Path(self.mktemp())
        path.write_text(
            textwrap.dedent(
                """\
                Twisted
                =======

                Changes: `NEWS <NEWS.rst>`_.
                Read `the docs <https://twistedmatrix.com/documents/>`_.
                """
            ),
            encoding="utf8",
        )

        self.assertEqual(
            textwrap.dedent(
                """\
                Twisted
                =======

                Changes: `NEWS <https://github.com/twisted/twisted/blob/trunk/NEWS.rst>`_.
                Read `the docs <https://twistedmatrix.com/documents/>`_.
                """
            ),
            getSetupArgs(extensions=[], readme=path)["long_description"],
        )
