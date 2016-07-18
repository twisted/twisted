#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Setuptools installer for Twisted.
"""

import os
import sys
import setuptools
from setuptools.command.build_py import build_py

# Tell Twisted not to enforce zope.interface requirement on import, since
# we're going to have to import twisted.python.dist and can rely on
# setuptools to install dependencies.
setuptools._TWISTED_NO_CHECK_REQUIREMENTS = True


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



def main(args):
    """
    Invoke twisted.python.dist with the appropriate metadata about the
    Twisted package.
    """
    if os.path.exists('twisted'):
        sys.path.insert(0, '.')

    if sys.version_info[0] >= 3:
        requirements = ["zope.interface >= 4.0.2"]
    else:
        requirements = ["zope.interface >= 3.6.0"]

    from twisted.python.dist import (
        STATIC_PACKAGE_METADATA, getExtensions, getConsoleScripts,
        setup, _EXTRAS_REQUIRE)

    setup_args = STATIC_PACKAGE_METADATA.copy()

    setup_args.update(dict(
        packages=setuptools.find_packages(),
        install_requires=requirements,
        conditionalExtensions=getExtensions(),
        entry_points={
            'console_scripts':  getConsoleScripts()
        },
        include_package_data=True,
        zip_safe=False,
        extras_require=_EXTRAS_REQUIRE,
    ))

    if sys.version_info[0] >= 3:
        setup_args.update(dict(
            cmdclass={
                'build_py': PickyBuildPy,
            }
         ))

    setup(**setup_args)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)
