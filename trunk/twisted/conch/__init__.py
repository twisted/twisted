# -*- test-case-name: twisted.conch.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#


"""
Twisted.Conch: The Twisted Shell. Terminal emulation, SSHv2 and telnet.

Currently this contains the SSHv2 implementation, but it may work over other
protocols in the future. (i.e. Telnet)

Maintainer: Paul Swartz
"""

from twisted.conch._version import version
__version__ = version.short()
