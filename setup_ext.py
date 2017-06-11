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

    _setup = {}
    with open('src/_twisted_c_extensions/_setup.py') as f:
        exec(f.read(), _setup)

    try:
        setuptools.setup(**_setup["getSetupArgs"]())
    except KeyboardInterrupt:
        sys.exit(1)
