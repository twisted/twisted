# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.



"""

Twisted News: an NNTP-based news service.

"""
from twisted.python import versions

version = versions.Version(__name__, 0, 1, 0)
__version__ = version.short()

del versions

