# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedWeb = _tapHelper(
    "Twisted Web",
    "twisted.web.tap",
    ("A general-purpose web server which can serve from a "
     "filesystem or application resource."),
    "web")
