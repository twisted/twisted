# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for C{twisted.internet._fd}.
"""

__metaclass__ = type

from twisted.trial.unittest import TestCase
from twisted.internet._fd import Descriptor, ReadDescriptor


class DescriptorMixin:
    """
    Utility functions for testing descriptors with stateful dispatch.
    """
    class FakeReactor(list):
        def __getattr__(self, name):
            self.append(name)
            return self.append

    # Override in subclasses:
    Descriptor = None


    def noDefaultTest(self, methodName):
        """
        The given method name has stateful dispath, with no default
        implementation.
        """
        class TestFD(self.Descriptor):
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


    def readWriteTest(self, methodName, expectedReactorCall):
        """
        When the method name is called on the file descriptor, a stateful
        dispatch is done, with the default calling the reactor with the
        C{Descriptor} as an argument.
        """
        # Setup class with method overriden in BAR state, but not in FOO
        # state:
        class TestFD(self.Descriptor):
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



class DescriptorTests(TestCase, DescriptorMixin):
    """
    L{Descriptor} provides a stateful basic set of methods.
    """
    Descriptor = Descriptor

    def test_fileno(self):
        """
        L{Descriptor} provides a stateful implementation of its C{fileno}
        method.
        """
        self.noDefaultTest("fileno")


    def test_connectionLost(self):
        """
        L{Descriptor} provides a stateful dispatch of its C{connectionLost}
        method.
        """
        self.noDefaultTest("connectionLost")



class ReadDescriptorTests(DescriptorTests):
    """
    L{ReadDescriptor} provides a stateful basic set of methods.
    """
    Descriptor = ReadDescriptor

    def test_doRead(self):
        """
        L{ReadDescriptor} provides a stateful dispatch of its C{doRead}
        method.
        """
        self.noDefaultTest("doRead")


    def test_stopReading(self):
        """
        L{ReadDescriptor.stopReading} is state-dispatched, and by default
        calls C{reactor.removeReader(self)}.
        """
        self.readWriteTest("stopReading", "removeReader")


    def test_startReading(self):
        """
        L{ReadDescriptor.startReading} is state-dispatched, and by default
        calls C{reactor.addReader(self)}.
        """
        self.readWriteTest("startReading", "addReader")
