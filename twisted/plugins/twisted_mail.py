# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.scripts.mktap import _tapHelper

TwistedMail = _tapHelper(
    "Twisted Mail",
    "twisted.mail.tap",
    "An email service",
    "mail")
