# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedManhole = _tapHelper(
    "Twisted Manhole (old)",
    "twisted.tap.manhole",
    "An interactive remote debugger service.",
    "manhole-old")
