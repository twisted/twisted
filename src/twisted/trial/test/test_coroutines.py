# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.trial.unittest.TestCase} support for async test methods.
"""

from twisted.python.compat import _PY3

if _PY3:
    import sys
    if sys.version_info >= (3, 5):
        from .py3_test_coroutines import CoroutineTests
        CoroutineTests  # shh pyflakes
