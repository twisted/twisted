# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Provide lists of modules ported to Python 3.

Modules listed below have been ported to Python 3. The port may be partial,
with only some functionality available.

run-python3-tests uses this, and in the future it may be used by setup.py and
pydoctor.
"""

from __future__ import division

# A list of modules that have been ported, e.g. "twisted.python.versions"; a
# package name (e.g. "twisted.python") indicates the corresponding __init__.py
# file has been ported (e.g. "twisted/python/__init__.py").
modules = [
    # "twisted" depends on twisted.python.compat and twisted._versions
    ]


# A list of test modules that have been ported, e.g
# "twisted.python.test.test_versions".
testModules = [
    ]
