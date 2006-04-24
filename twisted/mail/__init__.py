
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""

Twisted Mail: a Twisted E-Mail Server.

Maintainer: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}

"""

from twisted.python import versions

version = versions.Version(__name__, 0, 2, 0)
__version__ = version.short()

del versions
