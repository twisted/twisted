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


    def noDefaultTest(self, methodName):
        """
        The given method name has stateful dispath, with no default
        implementation.
        """
        class TestFD(FileDescriptor):
            _state = "NEW"
        def method(self):
            return "hello"
        setattr(TestFD, "_%s_NEW" % (methodName,), method)

        # State dispatch happens:
        fd = TestFD(None)
        self.assertEqual(getattr(fd, methodName)(), "hello")

        # And there is no default implementation:
        fd._state = "SOMEOTHER"
        self.assertRaises(RuntimeError, getattr(fd, methodName))


    def test_fileno(self):
        """
        L{FileDescriptor} provides a stateful implementation of its C{fileno}
        method.
        """
        self.noDefaultTest("fileno")


    def test_doWrite(self):
        """
        L{FileDescriptor} provides a stateful dispatch of its C{doWrite}
        method.
        """
        self.noDefaultTest("doWrite")


    def test_doRead(self):
        """
        L{FileDescriptor} provides a stateful dispatch of its C{doRead}
        method.
        """
        self.noDefaultTest("doRead")


    def test_connectionLost(self):
        """
        L{FileDescriptor} provides a stateful dispatch of its C{connectionLost}
        method.
        """
        self.noDefaultTest("connectionLost")


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
