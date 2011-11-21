# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for C{twisted.internet._fd}.
"""

from twisted.trial.unittest import TestCase
from twisted.internet._fd import FileDescriptor


class FileDescriptorTests(TestCase):
    """
    L{FileDescriptor} provides a stateful basic set of methods.
    """
    class FakeReactor(list):
        def __getattr__(self, name):
            self.append(name)
            return self.append

    def test_fileno(self):
        """
        L{FileDescriptor} provides a stateful implementation of its C{fileno}
        method.
        """
        class TestFD(FileDescriptor):
            _state = "PERPLEXED"
            def _fileno_PERPLEXED(self):
                return "hello"
        fd = TestFD(None)
        self.assertEqual(fd.fileno(), "hello")


    def readWriteTest(self, methodName, expectedReactorCall):
        """
        When the method name is called on the file descriptor, a stateful
        dispatch is done, with the default calling the reactor with the
        C{FileDescriptor} as an argument.
        """
        # Setup class with method overriden in BAR state, but not in FOO
        # state:
        class TestFD(FileDescriptor):
            _state = "FOO"
        def method(self):
            return "bar result"
        setattr(TestFD, "_%s_BAR" % (methodName,), method)

        # In state FOO, it should use default implementation:
        reactor = self.FakeReactor()
        fd = TestFD(reactor)
        getattr(fd, methodName)()
        self.assertEqual(reactor, [expectedReactorCall, fd])

        # In state BAR, is should use overriden implementation:
        fd._state = "BAR"
        self.assertEqual(getattr(fd, methodName)(), "bar result")


    def test_stopReading(self):
        """
        L{FileDescriptor.stopReading} is state-dispatched, and by default
        calls C{reactor.removeReader(self)}.
        """
        self.readWriteTest("stopReading", "removeReader")


    def test_startReading(self):
        """
        L{FileDescriptor.startReading} is state-dispatched, and by default
        calls C{reactor.addReader(self)}.
        """
        self.readWriteTest("startReading", "addReader")


    def test_stopWriting(self):
        """
        L{FileDescriptor.stopWriting} is state-dispatched, and by default
        calls C{reactor.removeWriter(self)}.
        """
        self.readWriteTest("stopWriting", "removeWriter")


    def test_startWriting(self):
        """
        L{FileDescriptor.startWriting} is state-dispatched, and by default
        calls C{reactor.addWriter(self)}.
        """
        self.readWriteTest("startWriting", "addWriter")

