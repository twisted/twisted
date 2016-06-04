# -*- test-case-name: twisted.application.runner.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Facilities for running a Twisted application.
"""

__all__ = [
    "exit",
    "ExitStatus",
    "Runner",
    "RunnerOptions",
]

from ._exit import exit, ExitStatus
from ._runner import Runner, RunnerOptions
