
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Twisted: The Framework Of Your Internet.
"""

# Ensure the user is running the version of python we require.
import sys
if not hasattr(sys, "version_info") or sys.version_info < (2,2):
    raise RuntimeError("Twisted requires Python 2.2 or later.")
del sys

# Ensure compat gets imported
from twisted.python import compat
del compat

# setup version
__version__ = 'SVN-Trunk'
