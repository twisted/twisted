# -*- test-case-name: twisted.test.test_nooldstyle -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utilities to assist in the "flag day" new-style object transition.
"""

from __future__ import absolute_import, division

import os
import types

from twisted.python.compat import _PY3


def _ensureOldClass(cls):
    """
    Ensure that C{cls} is an old-style class.

    @param cls: The class to check.

    @return: C{None} if it is an old-style class.
    @raises: L{ValueError} if it is a new-style class.
    """
    if not type(cls) is types.ClassType:
        from twisted.python.reflect import fullyQualifiedName

        raise ValueError(
            ("twisted.python._oldstyle._oldStyle is being used to decorate a "
             "new-style class ({cls}). This should only be used to "
             "decorate old-style classes.").format(
                 cls=fullyQualifiedName(cls)))


if _PY3:

    def _oldStyle(cls):
        """
        No such thing as an old style class on Python 3.

        @param cls: The class to wrap (or in this case, not wrap).
        @return: C{cls}, unchanged
        """
        return cls

elif int(os.environ.get('TWISTED_NEWSTYLE', 0)) == 0:

    def _oldStyle(cls):
        """
        We don't want to override anything, but throw an exception if a
        new-style class is decorated.

        @param cls: The class to wrap (or in this case, not wrap).
        @type cls: L{types.ClassType}

        @return: C{cls}, unchanged
        @raises: L{ValueError} if C{cls} is a new-style class.
        """
        _ensureOldClass(cls)
        return cls

else:

    def _oldStyle(cls):
        """
        A decorator which converts old-style classes to new-style classes.

        @param cls: An old-style class to convert to new-style.
        @type cls: L{types.ClassType}
        @return: A new-style subclass of C{cls}.
        """
        _ensureOldClass(cls)

        class OverwrittenClass(cls, object):
            __doc__ = cls.__doc__

        OverwrittenClass.__name__ = cls.__name__
        OverwrittenClass.__module__ = cls.__module__

        return OverwrittenClass
