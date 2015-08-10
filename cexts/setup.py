# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import os
import sys

from setuptools import find_packages

if os.path.exists('twisted/_c'):
    sys.path.insert(0, '.') # So we can import twisted._c

from twisted._c._dist import ConditionalExtension, setup
from twisted._c._dist import _isCPython
from twisted._c import __version__


extensions = [
    ConditionalExtension(
        "twisted._c.raiser",
        ["twisted/_c/raiser.c"],
        condition=lambda _: _isCPython),

    ConditionalExtension(
        "twisted._c.iocpsupport",
        ["twisted/_c/iocpsupport/iocpsupport.c",
         "twisted/_c/iocpsupport/winsock_pointers.c"],
        libraries=["ws2_32"],
        condition=lambda _: _isCPython and sys.platform == "win32"),

    ConditionalExtension(
        "twisted._c.sendmsg",
        sources=["twisted/_c/sendmsg.c"],
        condition=lambda _: sys.platform != "win32"),

    ConditionalExtension(
        "twisted._c.portmap",
        ["twisted/_c/portmap.c"],
        condition=lambda builder: builder._check_header("rpc/rpc.h")),
]


setup(
    name='twisted._c',
    description='C Extensions for Twisted',
    version=__version__,
    author='Twisted Matrix Laboratories',
    author_email="twisted-python@twistedmatrix.com",
    url="http://twistedmatrix.com/",
    packages=find_packages(),
    license='MIT',
    long_description=file('README.rst').read(),
    conditionalExtensions=extensions,
    namespace_packages = ['twisted']
)
