# -*- test-case-name: twisted.python.test.test_hashlib -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Deprecated in Twisted 13.1.0; please use hashlib from stdlib instead.

L{twisted.python.hashlib} presents a subset of the interface provided by
U{hashlib<http://docs.python.org/library/hashlib.html>}.  The subset is the
interface required by various parts of Twisted.  This allows application code
to transparently use APIs which existed before C{hashlib} was introduced or to
use C{hashlib} if it is available.
"""
from __future__ import absolute_import
from hashlib import md5, sha1
import warnings

__all__ = ["md5", "sha1"]

warnings.warn(
    "twisted.python.hashlib was deprecated in "
    "Twisted 13.1.0: Please use hashlib from stdlib.",
    DeprecationWarning, stacklevel=2)
