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
    arguments = [('testName', String())]
    response = [('success', Boolean())]



class AddError(Command):
    """
    Add an error.
    """
    arguments = [('testName', String()), ('error', String()),
                 ('errorClass', String()), ('frames', ListOf(String()))]
    response = [('success', Boolean())]



class AddFailure(Command):
    """
    Add a failure.
    """
    arguments = [('testName', String()), ('fail', String()),
                 ('failClass', String()), ('frames', ListOf(String()))]
    response = [('success', Boolean())]



class AddSkip(Command):
    """
    Add a skip.
    """
    arguments = [('testName', String()), ('reason', String())]
    response = [('success', Boolean())]



class AddExpectedFailure(Command):
    """
    Add an expected failure.
    """
    arguments = [('testName', String()), ('error', String()),
                 ('todo', String())]
    response = [('success', Boolean())]



class AddUnexpectedSuccess(Command):
    """
    Add an unexpected success.
    """
    arguments = [('testName', String()), ('todo', String())]
    response = [('success', Boolean())]



class TestWrite(Command):
    """
    Write test log.
    """
    arguments = [('out', String())]
    response = [('success', Boolean())]
