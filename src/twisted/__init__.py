# -*- test-case-name: twisted -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted: The Framework Of Your Internet.
"""

def _checkRequirements():
    # Don't allow the user to run a version of Python we don't support.
    import sys

    version = getattr(sys, "version_info", (0,))
    if version < (2, 7):
        raise ImportError("Twisted requires Python 2.7 or later.")
    elif version >= (3, 0) and version < (3, 3):
        raise ImportError("Twisted on Python 3 requires Python 3.3 or later.")

_checkRequirements()

# setup version
from twisted._version import __version__ as version
__version__ = version.short()
