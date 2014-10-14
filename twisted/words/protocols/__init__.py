# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Chat protocols.
"""

from twisted.python import deprecate, versions

deprecate.deprecatedModuleAttribute(
    versions.Version("Twisted", 14, 1, 0), "MSN has shutdown.", __name__,
    "msn")
