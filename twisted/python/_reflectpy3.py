# -*- test-case-name: twisted.python.test.test_reflectpy3 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Reflection APIs which have been ported to Python 3.
"""

from __future__ import division, absolute_import

import types

def prefixedMethods(obj, prefix=''):
    """
    A list of methods with a given prefix on a given instance.
    """
    dct = {}
    accumulateMethods(obj, dct, prefix)
    return list(dct.values())


def accumulateMethods(obj, dict, prefix='', curClass=None):
    """
    accumulateMethods(instance, dict, prefix)
    I recurse through the bases of instance.__class__, and add methods
    beginning with 'prefix' to 'dict', in the form of
    {'methodname':*instance*method_object}.
    """
    if not curClass:
        curClass = obj.__class__
    for base in curClass.__bases__:
        accumulateMethods(obj, dict, prefix, base)

    for name, method in curClass.__dict__.items():
        optName = name[len(prefix):]
        if ((type(method) is types.FunctionType)
            and (name[:len(prefix)] == prefix)
            and (len(optName))):
            dict[optName] = getattr(obj, name)
