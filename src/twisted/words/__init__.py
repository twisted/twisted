# -*- test-case-name: twisted.words.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Words: Client and server implementations for IRC, XMPP, and other chat
services.

This package is now deprecated.
"""
import warnings

from incremental import Version, getVersionString

warningString = "twisted.words was deprecated at {}".format(
    getVersionString(Version("Twisted", "NEXT", 0, 0))
)
warnings.warn(warningString, DeprecationWarning, stacklevel=3)
