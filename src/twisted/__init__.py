# -*- test-case-name: twisted -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted: The Framework Of Your Internet.
"""

# setup version
from twisted._version import __version__ as version
__version__ = version.short()



from incremental import Version
from twisted.python.deprecate import deprecatedModuleAttribute
deprecatedModuleAttribute(
    Version("Twisted", "NEXT", 0, 0),
    "morituri nolumus mori",
    "twisted",
    "news"
)
