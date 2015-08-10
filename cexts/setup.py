# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import os
import sys

from setuptools import find_packages

if os.path.exists('twistedextensions'):
    sys.path.insert(0, '.') # So we can import twistedextensions

from twistedextensions._dist import ConditionalExtension as Extension, setup
from twistedextensions._dist import _isCPython
from twistedextensions import __version__


extensions = [
    Extension("twistedextensions.raiser",
              ["twistedextensions/raiser.c"],
              condition=lambda _: _isCPython),

    Extension("twistedextensions.iocpsupport",
              ["twistedextensions/iocpsupport/iocpsupport.c",
               "twistedextensions/iocpsupport/winsock_pointers.c"],
              libraries=["ws2_32"],
              condition=lambda _: _isCPython and sys.platform == "win32"),

    Extension("twistedextensions.sendmsg",
              sources=["twistedextensions/sendmsg.c"],
              condition=lambda _: sys.platform != "win32"),

    Extension("twistedextensions.portmap",
              ["twistedextensions/portmap.c"],
              condition=lambda builder: builder._check_header("rpc/rpc.h")),
]



if sys.version_info[:2] <= (2, 6):
    extensions.append(
        Extension(
            "twisted.python._initgroups",
            ["twisted/python/_initgroups.c"]))



setup(
    name='twistedextensions',
    description='C Extensions for Twisted',
    version=__version__,
    author='Twisted Matrix Laboratories',
    author_email="twisted-python@twistedmatrix.com",
    url="http://twistedmatrix.com/",
    packages=find_packages(),
    license='MIT',
    long_description=file('README.rst').read(),
    conditionalExtensions=extensions
)
