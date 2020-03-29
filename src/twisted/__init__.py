# -*- test-case-name: twisted -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted: The Framework Of Your Internet.
"""

import sys
from twisted._version import __version__ as version

# setup version
__version__ = version.short()


from incremental import Version
from twisted.python.deprecate import deprecatedModuleAttribute
deprecatedModuleAttribute(
    Version('Twisted', 20, 3, 0),
    "morituri nolumus mori",
    "twisted",
    "news"
)

if sys.version_info < (3, 5):
    raise Exception(
        "This version of Twisted is not compatible with Python 3.4 "
        "or below."
    )
