# -*- test-case-name: twisted -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Twisted: The Framework Of Your Internet.
"""

def _checkRequirements():
    # Don't allow the user to run a version of Python we don't support.
    import sys

    version = getattr(sys, "version_info", (0,))
    if version < (2, 7):
        raise ImportError("Twisted requires Python 2.7 or later.")
    elif version >= (3, 0) and version < (3, 3):
        raise ImportError("Twisted on Python 3 requires Python 3.3 or later.")
    if version < (3, 0):
        required = "3.6.0"
    else:
        required = "4.0.0"

    # Don't allow the user to run with a version of zope.interface we don't
    # support.
    required = "Twisted requires zope.interface %s or later" % (required,)
    try:
        from zope import interface
    except ImportError:
        # It isn't installed.
        raise ImportError(required + ": no module named zope.interface.")
    except:
        # It is installed but not compatible with this version of Python.
        raise ImportError(required + ".")
    try:
        # Try using the API that we need, which only works right with
        # zope.interface 3.6 (or 4.0 on Python 3)
        class IDummy(interface.Interface):
            pass
        @interface.implementer(IDummy)
        class Dummy(object):
            pass
    except TypeError:
        # It is installed but not compatible with this version of Python.
        raise ImportError(required + ".")

_checkRequirements()

# setup version
from twisted._version import __version__ as version
__version__ = version.short()
