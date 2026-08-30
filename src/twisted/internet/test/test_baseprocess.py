# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet._baseprocess} which implements process-related
functionality that is useful in all platforms supporting L{IReactorProcess}.
"""

from twisted.internet._baseprocess import BaseProcess
from twisted.internet.protocol import ProcessProtocol
from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase


class BaseProcessTests(TestCase):
    """
    Tests for L{BaseProcess}, a parent class for other classes which represent
    processes which implements functionality common to many different process
    implementations.
    """

    def test_callProcessExitedWithoutProtocol(self) -> None:
        """
        L{BaseProcess._callProcessExited} does nothing when there is no
        process protocol.
        """
        process = BaseProcess(None)
        process._callProcessExited(RuntimeError("fake reason"))

        # When there is no protocol, there should be no Exception logged
        self.assertEqual(self.flushLoggedErrors(), [])

    def test_callProcessExited(self) -> None:
        """
        L{BaseProcess._callProcessExited} calls the C{processExited} method of
        its C{proto} attribute and passes it a L{Failure} wrapping the given
        exception.
        """

        class FakeProto(ProcessProtocol):
            reason: Failure

            def processExited(self, reason: Failure) -> None:
                self.reason = reason

        reason = RuntimeError("fake reason")
        proto = FakeProto()
        process = BaseProcess(proto)
        process._callProcessExited(reason)
        proto.reason.trap(RuntimeError)
        self.assertIs(reason, proto.reason.value)
