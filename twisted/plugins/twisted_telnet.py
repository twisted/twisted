# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedTelnet = _tapHelper(
    "Twisted Telnet Shell Server",
    "twisted.tap.telnet",
    "A simple, telnet-based remote debugging service.",
    "telnet")
