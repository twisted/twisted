# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module is a legacy compatibility alias for L{twisted.internet.gireactor}.
See that module instead.
"""

from twisted.internet import gireactor

Gtk3Reactor = gireactor.GIReactor
PortableGtk3Reactor = gireactor.PortableGIReactor

install = gireactor.install

__all__ = ["install"]
