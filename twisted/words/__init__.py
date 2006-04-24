# -*- test-case-name: twisted.words.test -*-
# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Twisted Words: a Twisted Chat service.
"""

from twisted.python import versions

version = versions.Version(__name__, 0, 3, 0)
__version__ = version.short()

del versions
