# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet._baseprocess} which implements process-related
functionality that is useful in all platforms supporting L{IReactorProcess}.
"""

from twisted.internet._baseprocess import BaseProcess
from twisted.trial.unittest import TestCase


class BaseProcessTests(TestCase):
    """
    Tests for L{BaseProcess}, a parent class for other classes which represent
    processes which implements functionality common to many different process
    implementations.
    """

    def test_callProcessExited(self):
        """
        L{BaseProcess._callProcessExited} calls the C{processExited} method of
        its C{proto} attribute and passes it a L{Failure} wrapping the given
        exception.
        """

        class FakeProto:
            reason = None

            def processExited(self, reason):
                self.reason = reason

        reason = RuntimeError("fake reason")
        process = BaseProcess(FakeProto())
        process._callProcessExited(reason)
        process.proto.reason.trap(RuntimeError)
        self.assertIs(reason, process.proto.reason.value)
