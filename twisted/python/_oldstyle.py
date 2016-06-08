# -*- test-case-name: twisted.test.test_nooldstyle -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utilities to assist in the "flag day" new-style object transition.
"""

from __future__ import absolute_import, division

import os
import types

from functools import wraps

from twisted.python.compat import _shouldEnableNewStyle, _PY3
from twisted.python.util import _replaceIf


def passthru(arg, **kwargs):
    """
    Return C{arg}. Do nothing.

    @param arg: The arg to return.

    @param kwargs: Ignored keyword arguments.

    @return: C{arg}
    """
    return arg



def _ensureOldClass(cls, **kwargs):
    """
    Ensure that C{cls} is an old-style class.

    @param cls: The class to check.

    @param kwargs: Ignored keyword arguments.

    @return: The class, if it is an old-style class.
    @raises: L{ValueError} if it is a new-style class.
    """
    if not type(cls) is types.ClassType:
        from twisted.python.reflect import fullyQualifiedName

        raise ValueError(
            ("twisted.python._oldstyle._oldStyle is being used to decorate a "
             "new-style class ({cls}). This should only be used to "
             "decorate old-style classes.").format(
                 cls=fullyQualifiedName(cls)))

    return cls



@_replaceIf(_PY3, lambda **k: passthru)
@_replaceIf(not _shouldEnableNewStyle(), lambda **k: _ensureOldClass)
def _oldStyle(bases=(object,)):
    """
    A decorator which conditionally converts old-style classes to new-style
    classes. If it is Python 3, or if the C{TWISTED_NEWSTYLE} environment
    variable has a falsey (C{no}, C{false}, C{False}, or C{0}) value in the
    environment, this decorator is a no-op.

    @param cls: An old-style class to convert to new-style.
    @type cls: L{types.ClassType}

    @param bases: The bases that the converted class will use.
    @type bases: L{tuple}

    @return: A new-style version of C{cls}, with the bases C{bases} if
        upgraded.
    """
    def _old(cls):

        _ensureOldClass(cls)
        return type(cls.__name__, bases, cls.__dict__)

    return _old
