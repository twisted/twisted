# -*- test-case-name: twisted.python.test.test_hashlib -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{twisted.python.hashlib} presents a subset of the interface provided by
U{hashlib<http://docs.python.org/library/hashlib.html>}.  The subset is the
interface required by various parts of Twisted.  This allows application code
to transparently use APIs which existed before C{hashlib} was introduced or to
use C{hashlib} if it is available.
"""


try:
    _hashlib = __import__("hashlib")
except ImportError:
    from md5 import md5
    from sha import sha as sha1
else:
    md5  = _hashlib.md5
    sha1 = _hashlib.sha1


__all__ = ["md5", "sha1"]
