# -*- test-case-name: twisted -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted: The Framework Of Your Internet.
"""

import sys
from twisted._version import __version__ as version

__version__ = version.short()

if sys.version_info < (3, 5):
    raise Exception(
        "This version of Twisted is not compatible with Python 3.4 " "or below."
    )
