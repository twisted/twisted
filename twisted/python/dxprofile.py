# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Utility functions for reporting bytecode frequencies to Skip Montanaro's
stat collector.

This module requires a version of Python build with DYNAMIC_EXCUTION_PROFILE,
and optionally DXPAIRS, defined to be useful.
"""

import sys, types, xmlrpclib

def rle(iterable):
    """Run length encode a list"""
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
