# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.trial._dist.workerreporter}.
"""

from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase, Todo
from twisted.trial._dist.workerreporter import WorkerReporter
from twisted.trial._dist import managercommands


class FakeAMProtocol(object):
    """
    A fake C{AMP} implementations to track C{callRemote} calls.
    """
    id = 0
    lastCall = None

    def callRemote(self, command, **kwargs):
        self.lastCall = command



class WorkerReporterTests(TestCase):
    """
    Tests for L{WorkerReporter}.
    """

    def setUp(self):
        self.fakeAMProtocol = FakeAMProtocol()
        self.workerReporter = WorkerReporter(self.fakeAMProtocol)
        self.test = TestCase()


    def test_addSuccess(self):
        """
        L{WorkerReporter.addSuccess} sends a L{managercommands.AddSuccess}
        command.
        """
        self.workerReporter.addSuccess(self.test)
        self.assertEqual(self.fakeAMProtocol.lastCall,
                         managercommands.AddSuccess)


    def test_addError(self):
        """
        L{WorkerReporter.addError} sends a L{managercommands.AddError} command.
        """
        self.workerReporter.addError(self.test, Failure(RuntimeError('error')))
        self.assertEqual(self.fakeAMProtocol.lastCall,
                         managercommands.AddError)


    def test_addErrorTuple(self):
        """
        Adding an error using L{WorkerReporter.addError} as a
        C{sys.exc_info}-style tuple sends an L{managercommands.AddError}
        command.
        """
        self.workerReporter.addError(
            self.test, (RuntimeError, RuntimeError('error'), None))
        self.assertEqual(self.fakeAMProtocol.lastCall,
                         managercommands.AddError)


    def test_addFailure(self):
        """
        L{WorkerReporter.addFailure} sends a L{managercommands.AddFailure}
        command.
        """
        self.workerReporter.addFailure(self.test,
                                       Failure(RuntimeError('fail')))
        self.assertEqual(self.fakeAMProtocol.lastCall,
                         managercommands.AddFailure)


    def test_addFailureTuple(self):
        """
        Adding a failure using L{WorkerReporter.addFailure} as a
        C{sys.exc_info}-style tuple sends an L{managercommands.AddFailure}
        message.
        """
        self.workerReporter.addFailure(
            self.test, (RuntimeError, RuntimeError('fail'), None))
        self.assertEqual(self.fakeAMProtocol.lastCall,
                         managercommands.AddFailure)


    def test_addSkip(self):
        """
        L{WorkerReporter.addSkip} sends a L{managercommands.AddSkip} command.
        """
        self.workerReporter.addSkip(self.test, 'reason')
        self.assertEqual(self.fakeAMProtocol.lastCall,
                         managercommands.AddSkip)


    def test_addExpectedFailure(self):
        """
        L{WorkerReporter.addExpectedFailure} sends a
        L{managercommands.AddExpectedFailure} command.
        protocol.
        """
        self.workerReporter.addExpectedFailure(
            self.test, Failure(RuntimeError('error')), Todo('todo'))
        self.assertEqual(self.fakeAMProtocol.lastCall,
                         managercommands.AddExpectedFailure)


    def test_addUnexpectedSuccess(self):
        """
        L{WorkerReporter.addUnexpectedSuccess} sends a
        L{managercommands.AddUnexpectedSuccess} command.
        """
        self.workerReporter.addUnexpectedSuccess(self.test, Todo('todo'))
        self.assertEqual(self.fakeAMProtocol.lastCall,
                         managercommands.AddUnexpectedSuccess)
