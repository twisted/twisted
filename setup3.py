#!/usr/bin/env python3

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# This is a temporary helper to be able to build and install distributions of
# Twisted on/for Python 3.  Once all of Twisted has been ported, it should go
# away and setup.py should work for either Python 2 or Python 3.

from __future__ import division, absolute_import

import sys
import os

from setuptools import find_packages
from setuptools.command.build_py import build_py
from distutils.command.build_scripts import build_scripts


class PickyBuildPy(build_py):
    """
    A version of build_py that doesn't install the modules that aren't yet
    ported to Python 3.
    """
    def find_package_modules(self, package, package_dir):
        from twisted.python.dist3 import modulesToInstall, testDataFiles

        modules = [
            module for module
            in super(build_py, self).find_package_modules(package, package_dir)
            if ".".join([module[0], module[1]]) in modulesToInstall or
               ".".join([module[0], module[1]]) in testDataFiles]
        return modules



def main():
    # Make sure the to-be-installed version of Twisted is used, if available,
    # since we're importing from it:
    if os.path.exists('twisted'):
        sys.path.insert(0, '.')

    from twisted.python.dist import (STATIC_PACKAGE_METADATA, _EXTRAS_REQUIRE,
                                     getConsoleScripts, getExtensions, setup)

    args = STATIC_PACKAGE_METADATA.copy()
    args.update(dict(
        cmdclass={
            'build_py': PickyBuildPy,
        },
        packages=find_packages(),
        install_requires=["zope.interface >= 4.0.2"],
        conditionalExtensions=getExtensions(),
        entry_points={
            'console_scripts':  getConsoleScripts()
        },
        include_package_data=True,
        zip_safe=False,
        extras_require=_EXTRAS_REQUIRE,
    ))

    setup(**args)


if __name__ == "__main__":
    main()
