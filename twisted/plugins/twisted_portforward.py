# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedPortForward = _tapHelper(
    "Twisted Port-Forwarding",
    "twisted.tap.portforward",
    "A simple port-forwarder.",
    "portforward")
