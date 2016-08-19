#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Setuptools installer for Twisted.
"""

import os
import sys
import setuptools


# Tell Twisted not to enforce zope.interface requirement on import, since
# we're going to have to import twisted.python._setup and can rely on
# setuptools to install dependencies.
setuptools._TWISTED_NO_CHECK_REQUIREMENTS = True

if __name__ == "__main__":
    # Make sure we can import the setup helpers.
    if os.path.exists('src/twisted/'):
        sys.path.insert(0, 'src')

    from twisted.python._setup import getSetupArgs
    try:
        setuptools.setup(**getSetupArgs())
    except KeyboardInterrupt:
        sys.exit(1)
