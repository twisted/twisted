# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Python: Utilities and Enhancements for Python.
"""

from __future__ import absolute_import, division

# Deprecating twisted.python.constants/deprecate.
from .compat import unicode
from .versions import Version
from eventually import deprecatedModuleAttribute

deprecatedModuleAttribute(
    Version("Twisted", 16, 5, 0),
    "Please use constantly from PyPI instead.",
    "twisted.python", "constants")

deprecatedModuleAttribute(
    Version("Twisted", "NEXT", 0, 0),
    "Please use eventually from PyPI instead.",
    "twisted.python", "deprecate")

del Version
del deprecatedModuleAttribute
del unicode
