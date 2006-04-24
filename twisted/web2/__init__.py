# -*- test-case-name: twisted.web2.test -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""

Twisted Web2: a better Twisted Web Server.

"""

from twisted.python import versions

version = versions.Version(__name__, 0, 1, 0)
__version__ = version.short()

del versions
