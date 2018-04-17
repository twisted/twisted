# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Commands for reporting test success of failure to the manager.

@since: 12.3
"""

from twisted.protocols.amp import Command, String, Boolean, ListOf



class AddSuccess(Command):
    """
    Add a success.
    """
    arguments = [(b'testName', String())]
    response = [(b'success', Boolean())]



class AddError(Command):
    """
    Add an error.
    """
    arguments = [(b'testName', String()), (b'error', String()),
                 (b'errorClass', String()), (b'frames', ListOf(String()))]
    response = [(b'success', Boolean())]



class AddFailure(Command):
    """
    Add a failure.
    """
    arguments = [(b'testName', String()), (b'fail', String()),
                 (b'failClass', String()), (b'frames', ListOf(String()))]
    response = [(b'success', Boolean())]



class AddSkip(Command):
    """
    Add a skip.
    """
    arguments = [(b'testName', String()), (b'reason', String())]
    response = [(b'success', Boolean())]



class AddExpectedFailure(Command):
    """
    Add an expected failure.
    """
    arguments = [(b'testName', String()), (b'error', String()),
                 (b'todo', String())]
    response = [(b'success', Boolean())]



class AddUnexpectedSuccess(Command):
    """
    Add an unexpected success.
    """
    arguments = [(b'testName', String()), (b'todo', String())]
    response = [(b'success', Boolean())]



class TestWrite(Command):
    """
    Write test log.
    """
    arguments = [(b'out', String())]
    response = [(b'success', Boolean())]
