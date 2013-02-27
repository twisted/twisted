# -*- test-case-name: twisted.trial.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Things likely to be used by writers of unit tests.
"""

from __future__ import division, absolute_import

# Define the public API from the two implementation modules
from twisted.trial._synctest import (
    FailTest, SkipTest, SynchronousTestCase, PyUnitResultAdapter, Todo,
    makeTodo)
from twisted.trial._asynctest import TestCase

from twisted.python.compat import _PY3

if not _PY3:
    from twisted.trial._asyncrunner import (
        TestSuite, TestDecorator, decorate)
    from twisted.trial._asyncrunner import (
        _ForceGarbageCollectionDecorator, _iterateTests, _clearSuite)

# Further obscure the origins of these objects, to reduce surprise (and this is
# what the values were before code got shuffled around between files, but was
# otherwise unchanged).
FailTest.__module__ = SkipTest.__module__ = __name__


# Grab some implementation details so tests can continue to import them from
# here, rather than being concerned with which implementation module they come
# from (is this a good idea?)
from twisted.trial._synctest import (
    _LogObserver, _logObserver, _collectWarnings, _setWarningRegistryToNone)


__all__ = [
    'FailTest', 'SkipTest', 'SynchronousTestCase', 'Todo', 'makeTodo',

    'TestCase', 'TestSuite', 'decorate']
