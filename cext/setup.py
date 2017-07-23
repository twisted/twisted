#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Setuptools installer for Twisted's C extensions.
"""

import os
import sys
import setuptools

if __name__ == "__main__":

    # We need to be in the right directory for this.
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    _setup = {}
    with open('src/_twistedcextensions/_setup.py') as f:
        exec(f.read(), _setup)

    try:
        setuptools.setup(**_setup["getSetupArgs"]())
    except KeyboardInterrupt:
        sys.exit(1)
