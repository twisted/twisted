# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedSSH = _tapHelper(
    "Twisted Conch Server",
    "twisted.conch.tap",
    "A Conch SSH service.",
    "conch")

TwistedManhole = _tapHelper(
    "Twisted Manhole (new)",
    "twisted.conch.manhole_tap",
    ("An interactive remote debugger service accessible via telnet "
     "and ssh and providing syntax coloring and basic line editing "
     "functionality."),
    "manhole")
