# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedNames = _tapHelper(
    "Twisted DNS Server",
    "twisted.names.tap",
    "A domain name server.",
    "dns")
