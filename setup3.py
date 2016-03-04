#!/usr/bin/env python3

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# This is a temporary helper to be able to build and install distributions of
# Twisted on/for Python 3.  Once all of Twisted has been ported, it should go
# away and setup.py should work for either Python 2 or Python 3.

from __future__ import division, absolute_import

import sys
import os

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py
from setuptools.command.install_scripts import install_scripts


class PickyBuildPy(build_py):
    """
    A version of build_py that doesn't install the modules that aren't yet
    ported to Python 3.
    """
    def find_package_modules(self, package, package_dir):
        from twisted.python.dist3 import modulesToInstall, testDataFiles
        return [
            module for module
            in super(build_py, self).find_package_modules(package, package_dir)
            if module in modulesToInstall or module in testDataFiles]



class PickyInstallScripts(install_scripts):

    def write_script(self, script_name, contents, mode="t", *ignored):
        from twisted.python.dist3 import portedScripts
        if script_name in portedScripts:
            return super(PickyInstallScripts, self).write_script(script_name, contents, mode=mode)



def main():
    # Make sure the to-be-installed version of Twisted is used, if available,
    # since we're importing from it:
    if os.path.exists('twisted'):
        sys.path.insert(0, '.')

    from twisted.python.dist import STATIC_PACKAGE_METADATA, getScripts

    args = STATIC_PACKAGE_METADATA.copy()
    args.update(dict(
        cmd_class={
            'build_py': PickyBuildPy,
            'install_scripts': PickyInstallScripts,
        },
        packages=find_packages(),
        install_requires=["zope.interface >= 4.0.2"],
        zip_safe=False,
        include_package_data=True,
        scripts=getScripts(),
    ))

    setup(**args)


if __name__ == "__main__":
    main()
