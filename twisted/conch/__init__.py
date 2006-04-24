# -*- test-case-name: twisted.conch.test -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#


"""Twisted.Conch: The Twisted Shell. Terminal emulation, SSHv2 and telnet.

Currently this contains the SSHv2 implementation, but it may work over other protocols in the future. (i.e. Telnet)

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""


from twisted.python import versions

version = versions.Version(__name__, 0, 6, 0)
__version__ = version.short()

del versions
