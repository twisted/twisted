# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A trivial extension that just raises an exception. See
L{twisted.test.test_failure.test_failureConstructionWithMungedStackSucceeds}.
"""

from _twisted_platform_support._raiser import RaiserException, raiseException

__all__ = ["RaiserException", "raiseException"]
