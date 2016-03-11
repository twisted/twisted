# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Application data directory support.
"""

from __future__ import division, absolute_import

import appdirs
import inspect

from twisted.python.compat import currentframe
from twisted.python.reflect import qual


def getDataDirectory(moduleName=None):
    """
    Get a data directory for the caller function, or C{moduleName} if given.

    @returns: A directory for putting data in.
    @rtype: L{str}
    """
    if not moduleName:
        caller = currentframe(1)
        moduleName = inspect.getmodule(caller).__name__

    return appdirs.user_data_dir(moduleName)
