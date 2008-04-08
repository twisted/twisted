# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.application.service import ServiceMaker

TwistedManhole = ServiceMaker(
    "Twisted Manhole (old)",
    "twisted.tap.manhole",
    "An interactive remote debugger service.",
    "manhole-old")
