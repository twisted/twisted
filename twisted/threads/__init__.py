# -*- test-case-name: twisted.test.test_paths -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted integration with operating system threads.
"""

from ._threadworker import ThreadWorker
from ._ithreads import IWorker
from ._team import Team

__all__ = [
    "ThreadWorker",
    "IWorker",
    "Team",
]
