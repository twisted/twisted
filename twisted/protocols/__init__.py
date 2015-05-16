# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Protocols: A collection of internet protocol implementations.
"""

# Deprecating twisted.protocols.gps.
from twisted.python.versions import Version
from twisted.python.deprecate import deprecatedModuleAttribute

deprecatedModuleAttribute(
    Version("Twisted", 15, 2, 0),
    "Use twisted.positioning instead.",
    "twisted.protocols", "gps")
