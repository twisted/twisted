# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Conditional import of C{inlinecb_tests} for Python 2.5 and greater.
"""
import sys

__all__ = ['NonLocalExitTests']

if sys.version_info[:2] >= (2, 5):
    from twisted.internet.test.inlinecb_tests import NonLocalExitTests

