#!/usr/bin/env python3.3

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# This is a temporary helper to be able to build and install distributions of
# Twisted on/for Python 3.  Once all of Twisted has been ported, it should go
# away and setup.py should work for either Python 2 or Python 3.

from __future__ import division, absolute_import

import sys
import os
from distutils.command.sdist import sdist


class DisabledSdist(sdist):
    """
    A version of the sdist command that does nothing.
    """
    def run(self):
        sys.stderr.write(
            "The sdist command only works with Python 2 at the moment.\n")
        sys.exit(1)



def main():
    from setuptools import setup

    # Make sure the to-be-installed version of Twisted is used, if available,
    # since we're importing from it:
    if os.path.exists('twisted'):
        sys.path.insert(0, '.')

    from twisted.python.dist3 import modulesToInstall
    from twisted.python.dist3 import testDataFiles, _processDataFileList
    from twisted.python.dist import STATIC_PACKAGE_METADATA, getDataFiles

    _dataFiles = _processDataFileList(testDataFiles)
    args = STATIC_PACKAGE_METADATA.copy()
    args['install_requires'] = ["zope.interface >= 4.0.2"]
    args['py_modules'] = modulesToInstall
    args['data_files'] = getDataFiles('twisted') + _dataFiles
    args['zip_safe'] = False
    args['cmdclass'] = {'sdist': DisabledSdist}
    args['scripts'] = ['bin/trial', 'bin/twistd']

    setup(**args)


if __name__ == "__main__":
    main()
