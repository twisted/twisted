# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedSOCKS = _tapHelper(
    "Twisted SOCKS",
    "twisted.tap.socks",
    "A SOCKSv4 proxy service.",
    "socks")
