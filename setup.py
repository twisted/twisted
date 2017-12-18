#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Setuptools installer for Twisted.
"""

import os
import sys
import setuptools

if __name__ == "__main__":

    _checkRequirements = {}
    with open('src/twisted/_checkrequirements.py') as f:
        exec(f.read(), _checkRequirements)
    _checkRequirements["_checkRequirements"]()

    _setup = {}
    with open('src/twisted/python/_setup.py') as f:
        exec(f.read(), _setup)

    try:
        setuptools.setup(**_setup["getSetupArgs"]())
    except KeyboardInterrupt:
        sys.exit(1)
