# -*- test-case-name: twisted.python.test.test_bytes -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utility for converting between L{unicode} and L{bytes}
"""

from __future__ import division, absolute_import, print_function

from twisted.python.compat import unicode


def ensureBytes(s, encoding="ascii", errors="strict"):
    """
    Convert L{unicode} string to L{bytes}.

    @param s: The string to convert.
    @type s: L{unicode} or L{bytes}
    @param encoding: The encoding to pass to L{str.encode}.
    @param errors: The error handling scheme to pass to L{str.encode}.

    @raise TypeError: The input is not L{unicode} or L{bytes}.

    @return: The encoded string.  If I{s} is L{bytes} just return I{s}.
    @rtype: L{bytes}
    """
    if isinstance(s, unicode):
        return s.encode(encoding=encoding, errors=errors)
    return s



__all__ = ['ensureBytes']
