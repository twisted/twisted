# -*- test-case-name: twisted.python.test.test_bytes -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utility for converting between L{unicode} and L{bytes}
"""

from __future__ import division, absolute_import, print_function

from twisted.python.compat import unicode


def toBytes(s, encoding="ascii", errors="strict"):
    """
    Convert L{unicode} string to L{bytes}.

    @param s: The string to convert.
    @param encoding: The encoding to pass to L{str.encode}.
    @param errors: The error handling scheme to pass to L{str.encode}.

    @raise TypeError: The input is not L{unicode}, L{bytes} or L{None}.

    @return: The encoded string.  If I{s} is L{bytes} or L{None}, just return
             I{s}.
    @rtype: L{bytes}
    """
    if s is None:
        return s
    elif isinstance(s, bytes):
        return s
    elif isinstance(s, unicode):
        return s.encode(encoding=encoding, errors=errors)
    else:
        raise TypeError("Expected {} to be unicode, bytes, or None not: "
            "{}".format(s, type(s)))



__all__ = ['toBytes']
