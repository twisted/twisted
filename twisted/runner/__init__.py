# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Runner: Run and monitor processes.
"""

from twisted.runner._version import version
__version__ = version.short()

try:
    from _twistedextensions import portmap
except ImportError:
    pass
