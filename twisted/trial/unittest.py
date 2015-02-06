# -*- test-case-name: twisted.trial.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Things likely to be used by writers of unit tests.
"""

from __future__ import division, absolute_import

__all__ = [
    'FailTest',
    'makeTodo',
    'PyUnitResultAdapter',
    'SkipTest',
    'SynchronousTestCase',
    'TestCase',
    'Todo',
    ]

# Define the public API from the two implementation modules
from twisted.trial._synctest import (
    FailTest, SkipTest, SynchronousTestCase, PyUnitResultAdapter, Todo,
    makeTodo)
from twisted.trial._asynctest import TestCase

from twisted.python.compat import _PY3

if not _PY3:
    from twisted.trial._asyncrunner import (
        TestSuite, TestDecorator, decorate)
    __all__.extend([
        'decorate',
        'TestDecorator',
        'TestSuite',
        ])

# Further obscure the origins of these objects, to reduce surprise (and this is
# what the values were before code got shuffled around between files, but was
# otherwise unchanged).
FailTest.__module__ = SkipTest.__module__ = __name__
