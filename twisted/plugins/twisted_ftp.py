# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedFTP = _tapHelper(
    "Twisted FTP",
    "twisted.tap.ftp",
    "An FTP server.",
    "ftp")
