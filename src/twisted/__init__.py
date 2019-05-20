# -*- test-case-name: twisted -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted: The Framework Of Your Internet.
"""

# setup version
from twisted._version import __version__ as version
__version__ = version.short()


from twisted.python.compat import _PY3

if _PY3:
    from incremental import Version
    from twisted.python.deprecate import deprecatedModuleAttribute
    deprecatedModuleAttribute(
        Version("Twisted", "NEXT", 0, 0),
        "Will not be ported to Python 3.",
        "twisted",
        "news"
    )
