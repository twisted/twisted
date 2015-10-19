# -*- test-case-name: twisted.trial.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Things likely to be used by writers of unit tests.
"""

from __future__ import division, absolute_import

# Define the public API from the two implementation modules
from twisted.trial._synctest import (
    FailTest, SkipTest, SynchronousTestCase, UnittestResultAdapter, Todo,
    makeTodo)
from twisted.trial._asynctest import TestCase
from twisted.trial._asyncrunner import (
    TestSuite, TestDecorator, decorate)

from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

# Further obscure the origins of these objects, to reduce surprise (and this is
# what the values were before code got shuffled around between files, but was
# otherwise unchanged).
FailTest.__module__ = SkipTest.__module__ = __name__

# For backwards compat
PyUnitResultAdapter = UnittestResultAdapter

deprecatedModuleAttribute(
    Version("Twisted", 15, 5, 0),
    "Use twisted.trial.unittest.UnittestResultAdapter instead.",
    "twisted.trial.unittest",
    "PyUnitResultAdapter")


__all__ = [
    'decorate',
    'FailTest',
    'makeTodo',
    'PyUnitResultAdapter',
    'UnittestResultAdapter',
    'SkipTest',
    'SynchronousTestCase',
    'TestCase',
    'TestDecorator',
    'TestSuite',
    'Todo',
    ]
