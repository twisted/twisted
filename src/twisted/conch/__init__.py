# -*- test-case-name: twisted.conch.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Conch: The Twisted Shell. Terminal emulation, SSHv2 and telnet.
"""

from incremental import Version
from twisted.python.deprecate import deprecatedModuleAttribute

from twisted._version import __version__ as version
__version__ = version.short()

deprecatedModuleAttribute(
    Version("Twisted", 16, 0, 0),
    "Use twisted.__version__ instead.",
    "twisted.conch", "__version__")
