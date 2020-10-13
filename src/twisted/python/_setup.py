# -*- test-case-name: twisted.python.test.test_setup -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# pylint: disable=I0011,C0103,C9302,W9401,W9402

"""
Setuptools convenience functionality.

This file must not import anything from Twisted, as it is loaded by C{exec} in
C{setup.py}. If you need compatibility functions for this code, duplicate them
here.

@var _EXTENSIONS: The list of L{ConditionalExtension} used by the setup
    process.
"""

import os
import pathlib
import platform
import re
import sys
from typing import Any, Dict, List, cast

from distutils.command import build_ext
from distutils.errors import CompileError
from setuptools import Extension


class ConditionalExtension(Extension):
    """
    An extension module that will only be compiled if certain conditions are
    met.

    @param condition: A callable of one argument which returns True or False to
        indicate whether the extension should be built. The argument is an
        instance of L{build_ext_twisted}, which has useful methods for checking
        things about the platform.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.condition = kwargs.pop("condition", lambda builder: True)
        Extension.__init__(self, *args, **kwargs)


def _checkCPython(platform: Any = platform) -> bool:
    """
    Checks if this implementation is CPython.

    This uses C{platform.python_implementation}.

    This takes C{sys} and C{platform} kwargs that by default use the real
    modules. You shouldn't care about these -- they are for testing purposes
    only.

    @return: C{False} if the implementation is definitely not CPython, C{True}
        otherwise.
    """
    return cast(bool, platform.python_implementation() == "CPython")


_isCPython = _checkCPython()  # type: bool


# The C extensions used for Twisted.
_EXTENSIONS = (
    [
        ConditionalExtension(
            "twisted.internet.iocpreactor.iocpsupport",
            sources=[
                "src/twisted/internet/iocpreactor/iocpsupport/iocpsupport.c",
                "src/twisted/internet/iocpreactor/iocpsupport/winsock_pointers.c",
            ],
            libraries=["ws2_32"],
            condition=lambda _: True,
        ),
    ]
    if _isCPython and sys.platform == "win32"
    else []  # avoid adding ext_modules kwarg, to prevent platform tags
)


def getSetupArgs(
    extensions: List[ConditionalExtension] = _EXTENSIONS,
    readme: pathlib.Path = pathlib.Path("README.rst"),
) -> Dict[str, Any]:
    """
    Generate arguments for C{setuptools.setup()}

    @param extensions: C extension modules to maybe build. This argument is to
        be used for testing.
    @param readme: Path to the readme reStructuredText file. This argument is
        to be used for testing.

    @return: The keyword arguments to be used by the setup method.
    """

    # Use custome class to build the extensions.
    class my_build_ext(build_ext_twisted):
        conditionalExtensions = extensions

    def _extension_kwargs() -> Dict[str, object]:
        if not extensions:
            return {}

        # This is a workaround for distutils behavior; ext_modules isn't
        # actually used by our custom builder.  distutils deep-down checks
        # to see if there are any ext_modules defined before invoking
        # the build_ext command.  We need to trigger build_ext regardless
        # because it is the thing that does the conditional checks to see
        # if it should build any extensions.  The reason we have to delay
        # the conditional checks until then is that the compiler objects
        # are not yet set up when this code is executed.
        return {
            "ext_modules": extensions,
            "cmdclass": {"build_ext": my_build_ext},
        }

    return {
        # Munge links of the form `NEWS <NEWS.rst>`_ to point at the appropriate
        # location on GitHub so that they function when the long description is
        # displayed on PyPI.
        "long_description": re.sub(
            r"`([^`]+)\s+<(?!https?://)([^>]+)>`_",
            r"`\1 <https://github.com/twisted/twisted/blob/trunk/\2>`_",
            readme.read_text(encoding="utf8"),
            flags=re.I,
        ),
        **_extension_kwargs(),
    }


# Helpers and distutil tweaks


class build_ext_twisted(build_ext.build_ext):  # type: ignore[name-defined]
    """
    Allow subclasses to easily detect and customize Extensions to
    build at install-time.
    """

    def prepare_extensions(self) -> None:
        """
        Prepare the C{self.extensions} attribute (used by
        L{build_ext.build_ext}) by checking which extensions in
        I{conditionalExtensions} should be built.  In addition, if we are
        building on NT, define the WIN32 macro to 1.
        """
        # always define WIN32 under Windows
        if os.name == "nt":
            self.define_macros = [("WIN32", 1)]
        else:
            self.define_macros = []

        # On Solaris 10, we need to define the _XOPEN_SOURCE and
        # _XOPEN_SOURCE_EXTENDED macros to build in order to gain access to
        # the msg_control, msg_controllen, and msg_flags members in
        # sendmsg.c. (according to
        # https://stackoverflow.com/questions/1034587).  See the documentation
        # of X/Open CAE in the standards(5) man page of Solaris.
        if sys.platform.startswith("sunos"):
            self.define_macros.append(("_XOPEN_SOURCE", 1))
            self.define_macros.append(("_XOPEN_SOURCE_EXTENDED", 1))

        self.extensions = [x for x in self.conditionalExtensions if x.condition(self)]

        for ext in self.extensions:
            ext.define_macros.extend(self.define_macros)

    def build_extensions(self) -> None:
        """
        Check to see which extension modules to build and then build them.
        """
        self.prepare_extensions()
        build_ext.build_ext.build_extensions(self)  # type: ignore[attr-defined]

    def _remove_conftest(self) -> None:
        for filename in ("conftest.c", "conftest.o", "conftest.obj"):
            try:
                os.unlink(filename)
            except EnvironmentError:
                pass

    def _compile_helper(self, content: str) -> bool:
        conftest = open("conftest.c", "w")
        try:
            with conftest:
                conftest.write(content)

            try:
                self.compiler.compile(["conftest.c"], output_dir="")
            except CompileError:
                return False
            return True
        finally:
            self._remove_conftest()

    def _check_header(self, header_name: str) -> bool:
        """
        Check if the given header can be included by trying to compile a file
        that contains only an #include line.
        """
        self.compiler.announce("checking for {} ...".format(header_name), 0)
        return self._compile_helper("#include <{}>\n".format(header_name))
