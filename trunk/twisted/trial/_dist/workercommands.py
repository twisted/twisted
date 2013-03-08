# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Commands for telling a worker to load tests or run tests.

@since: 12.3
"""

from twisted.protocols.amp import Command, String, Boolean



class Run(Command):
    """
    Run a test.
    """
    arguments = [('testCase', String())]
    response = [('success', Boolean())]



class Start(Command):
    """
    Set up the worker process, giving the running directory.
    """
    arguments = [('directory', String())]
    response = [('success', Boolean())]
