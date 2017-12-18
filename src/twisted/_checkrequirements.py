# -*- test-case-name: twisted -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

def _checkRequirements():
    # Don't allow the user to run a version of Python we don't support.
    import sys

    version = getattr(sys, "version_info", (0,))
    if version < (2, 7):
        raise ImportError("Twisted requires Python 2.7 or later.")
    elif version >= (3, 0) and version < (3, 4):
        raise ImportError("Twisted on Python 3 requires Python 3.4 or later.")
