#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Setuptools installer for Twisted.
"""

import pathlib
import platform
import re
import sys

import setuptools


setuptools.setup(
    # Munge links of the form `NEWS <NEWS.rst>`_ to point at the appropriate
    # location on GitHub so that they function when the long description is
    # displayed on PyPI.
    long_description=re.sub(
        r"`([^`]+)\s+<(?!https?://)([^>]+)>`_",
        r"`\1 <https://github.com/twisted/twisted/blob/trunk/\2>`_",
        pathlib.Path("README.rst").read_text(encoding="utf8"),
        flags=re.I,
    ),
    ext_modules=[
        setuptools.Extension(
            "twisted.internet.iocpreactor.iocpsupport",
            sources=[
                "src/twisted/internet/iocpreactor/iocpsupport/iocpsupport.c",
                "src/twisted/internet/iocpreactor/iocpsupport/winsock_pointers.c",
            ],
            libraries=["ws2_32"],
        )
    ]
    if sys.platform == "win32" and platform.python_implementation() == "CPython"
    else [],
)
