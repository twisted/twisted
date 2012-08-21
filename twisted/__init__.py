# -*- test-case-name: twisted -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Twisted: The Framework Of Your Internet.
"""

# Ensure the user is running the version of python we require.
import sys
if not hasattr(sys, "version_info") or sys.version_info < (2, 6):
    raise RuntimeError("Twisted requires Python 2.6 or later.")
del sys

# Ensure compat gets imported
from twisted.python import compat

# setup version
# temporarily disabled for Python 3; will be re-enabled in ticket #5886:
if not compat._PY3:
    from twisted._version import version
    __version__ = version.short()

del compat
