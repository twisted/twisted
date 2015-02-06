# -*- test-case-name: twisted.trial.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Private API used by trial and its unit tests.

This is here to make it clear which components are private.
Public components should go in L{twisted.trial.unittest}.
"""

from twisted.python.compat import _PY3

if not _PY3:
    from twisted.trial._asyncrunner import (
        _ForceGarbageCollectionDecorator,
        _iterateTests,
        )

from twisted.trial._synctest import (
    _logObserver,
    )

__all__ = [
    '_ForceGarbageCollectionDecorator',
    '_iterateTests',
    '_logObserver',
    ]
