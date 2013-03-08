# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.application.service import ServiceMaker

TwistedTelnet = ServiceMaker(
    "Twisted Telnet Shell Server",
    "twisted.tap.telnet",
    "A simple, telnet-based remote debugging service.",
    "telnet")
