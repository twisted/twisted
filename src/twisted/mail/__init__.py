# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Mail: Servers and clients for POP3, ESMTP, and IMAP.
"""

from twisted.python.versions import Version
from twisted.python.deprecate import deprecatedModuleAttribute

from twisted._version import version
__version__ = version.short()

deprecatedModuleAttribute(
    Version("Twisted", 16, 0, 0),
    "Use twisted.__version__ instead.",
    "twisted.mail", "__version__")
