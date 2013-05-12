# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Python: Utilities and Enhancements for Python.
"""

from twisted.python.versions import Version
from twisted.python.deprecate import deprecatedModuleAttribute


deprecatedModuleAttribute(
    Version("Twisted", 13, 1, 0),
    "text has been deprecated.",
    __name__,
    "text")

