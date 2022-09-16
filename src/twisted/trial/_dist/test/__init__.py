# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distributed trial test runner tests.
"""

from hypothesis import settings

settings.register_profile("x", max_examples=100000, print_blob=True, report_multiple_bugs=True)
settings.load_profile("x")
