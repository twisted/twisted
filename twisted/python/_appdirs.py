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


def getDataDirectory(qualname=None):
    """
    Get a data directory for the caller function, or C{qualname} if given.

    @returns: A directory for putting data in.
    @rtype: L{str}
    """
    if not qualname:
        caller = currentframe(1)
        qualname = ".".join([inspect.getmodule(caller).__name__,
                             caller.f_code.co_name])

    return appdirs.user_data_dir(qualname)
