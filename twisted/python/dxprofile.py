# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
DEPRECATED since Twisted 8.0.

Utility functions for reporting bytecode frequencies to Skip Montanaro's
stat collector.

This module requires a version of Python build with DYNAMIC_EXCUTION_PROFILE,
and optionally DXPAIRS, defined to be useful.
"""

import sys, types, xmlrpclib, warnings


warnings.warn("twisted.python.dxprofile is deprecated since Twisted 8.0.",
              category=DeprecationWarning)


def rle(iterable):
    """
    Run length encode a list.
    """
    iterable = iter(iterable)
    runlen = 1
    result = []
    try:
        previous = iterable.next()
    except StopIteration:
        return []
    for element in iterable:
        if element == previous:
            runlen = runlen + 1
            continue
        else:
            if isinstance(previous, (types.ListType, types.TupleType)):
                previous = rle(previous)
            result.append([previous, runlen])
        previous = element
        runlen = 1
    if isinstance(previous, (types.ListType, types.TupleType)):
        previous = rle(previous)
    result.append([previous, runlen])
    return result



def report(email, appname):
    """
    Send an RLE encoded version of sys.getdxp() off to our Top Men (tm)
    for analysis.
    """
    if hasattr(sys, 'getdxp') and appname:
        dxp = xmlrpclib.ServerProxy("http://manatee.mojam.com:7304")
        dxp.add_dx_info(appname, email, sys.version_info[:3], rle(sys.getdxp()))
