# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Subpackage containing the modules that implement the command line tools.

Note that these are imported by top-level scripts which are intended to be
invoked directly from a shell.
"""

from twisted.python.versions import Version
from twisted.python.deprecate import deprecatedModuleAttribute

deprecatedModuleAttribute(
    Version("Twisted", 11, 1, 0),
    "Seek unzipping software outside of Twisted.",
    __name__,
    "tkunzip")

del Version, deprecatedModuleAttribute
