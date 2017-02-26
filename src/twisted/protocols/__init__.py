# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Protocols: A collection of internet protocol implementations.
"""

# Deprecating twisted.protocols.mice.
from incremental import Version
from twisted.python.deprecate import deprecatedModuleAttribute

deprecatedModuleAttribute(
    Version("Twisted", 16, 0, 0),
    "There is no replacement for this module.",
    "twisted.protocols", "mice")
