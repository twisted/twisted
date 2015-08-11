# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import os
import sys

from setuptools import find_packages

if os.path.exists('_twistedextensions'):
    sys.path.insert(0, '.') # So we can import _twistedextensions

from _twistedextensions._dist import ConditionalExtension, setup
from _twistedextensions._dist import _isCPython
from _twistedextensions import __version__


extensions = [
    ConditionalExtension(
        "_twistedextensions.raiser",
        ["_twistedextensions/raiser.c"],
        condition=lambda _: _isCPython),

    ConditionalExtension(
        "_twistedextensions.iocpsupport",
        ["_twistedextensions/iocpsupport/iocpsupport.c",
         "_twistedextensions/iocpsupport/winsock_pointers.c"],
        libraries=["ws2_32"],
        condition=lambda _: _isCPython and sys.platform == "win32"),

    ConditionalExtension(
        "_twistedextensions.sendmsg",
        sources=["_twistedextensions/sendmsg.c"],
        condition=lambda _: sys.platform != "win32"),

    ConditionalExtension(
        "_twistedextensions.portmap",
        ["_twistedextensions/portmap.c"],
        condition=lambda builder: builder._check_header("rpc/rpc.h")),
]


setup(
    name='_twistedextensions',
    description='C Extensions for Twisted',
    version=__version__,
    author='Twisted Matrix Laboratories',
    author_email="twisted-python@twistedmatrix.com",
    url="http://twistedmatrix.com/",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 2 :: Only",
        "Programming Language :: Python :: Implementation :: CPython"
    ],
    packages=find_packages(),
    license='MIT',
    long_description=file('README.rst').read(),
    conditionalExtensions=extensions,
)
