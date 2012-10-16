#!/usr/bin/env python3.3

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# This is a temporary helper to be able to build and install distributions of
# Twisted on/for Python 3.  Once all of Twisted has been ported, it should go
# away and setup.py should work for either Python 2 or Python 3.

from __future__ import division, absolute_import

import sys, os.path

sys.path.insert(0, '.')

from distutils.core import setup

from twisted.python.dist import STATIC_PACKAGE_METADATA

args = STATIC_PACKAGE_METADATA.copy()
args['classifiers'] = ["Programming Language :: Python :: 3.3"]

ported = {}
exec(open("admin/_twistedpython3.py").read(), ported)
args['py_modules'] = ported['modules'] + ported['testModules'] + ported['almostModules']

if 'sdist' in sys.argv:
    args['data_files'] = [
        ('admin', ['admin/_twistedpython3.py', 'admin/run-python3-tests'])]

setup(**args)
