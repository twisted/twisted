# -*- test-case-name: twisted.trial.test.test_util -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
#

"""
A collection of utilities for use with Trial.
"""

from __future__ import division, absolute_import, print_function

import sys

from twisted.python import deprecate, versions

from twisted.trial import _util

__all__ = [
    'DEFAULT_TIMEOUT_DURATION',

    'excInfoOrFailureToExcInfo', 'suppress', 'acquireAttribute']

__deprecated__ = [
    'DEFAULT_TIMEOUT', 'DEFAUILT_TIMEOUT_DURATION',
    'DirtyReactorAggregateError'
    'acquireAttribute', 'excInfoOrFailureToExcInfo'
    ]
for name in __deprecated__:
    globals()[name] = getattr(_util, name)
    deprecate.deprecatedModuleAttribute(
        versions.Version("Twisted", 13, 0, 0),
        "This is an implementation detail of twisted.trial.",
        __name__, name)
del __deprecated__, _util


def suppress(action='ignore', **kwarg):
    """
    Sets up the .suppress tuple properly, pass options to this method as you
    would the stdlib warnings.filterwarnings()

    So, to use this with a .suppress magic attribute you would do the
    following:

      >>> from twisted.trial import unittest, util
      >>> import warnings
      >>>
      >>> class TestFoo(unittest.TestCase):
      ...     def testFooBar(self):
      ...         warnings.warn("i am deprecated", DeprecationWarning)
      ...     testFooBar.suppress = [util.suppress(message='i am deprecated')]
      ...
      >>>

    Note that as with the todo and timeout attributes: the module level
    attribute acts as a default for the class attribute which acts as a default
    for the method attribute. The suppress attribute can be overridden at any
    level by specifying C{.suppress = []}
    """
    return ((action,), kwarg)



def getPythonContainers(meth):
    """Walk up the Python tree from method 'meth', finding its class, its module
    and all containing packages."""
    containers = []
    containers.append(meth.im_class)
    moduleName = meth.im_class.__module__
    while moduleName is not None:
        module = sys.modules.get(moduleName, None)
        if module is None:
            module = __import__(moduleName)
        containers.append(module)
        moduleName = getattr(module, '__module__', None)
    return containers

deprecate.deprecatedModuleAttribute(
    versions.Version("Twisted", 12, 3, 0),
    "This function never worked correctly.  Implement lookup on your own.",
    __name__, "getPythonContainers")
