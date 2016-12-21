# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Runner: Run and monitor processes.
"""

from incremental import Version
from twisted.python.deprecate import deprecatedModuleAttribute

from twisted._version import __version__ as version
__version__ = version.short()

deprecatedModuleAttribute(
    Version("Twisted", 16, 0, 0),
    "Use twisted.__version__ instead.",
    "twisted.runner", "__version__")

deprecatedModuleAttribute(
    Version("Twisted", "NEXT", 0, 0),
    "There is no replacement for this module.",
    "twisted.runner", "portmap")
