# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Whitebox tests for L{twisted.internet.abstract.FileDescriptor}.
"""

from zope.interface.verify import verifyClass

from twisted.internet.abstract import FileDescriptor
from twisted.internet.interfaces import IPushProducer
from twisted.trial.unittest import TestCase



class FileDescriptorTests(TestCase):
    """
    Tests for L{FileDescriptor}.
    """
    def test_writeWithUnicodeRaisesException(self):
        """
        L{FileDescriptor.write} doesn't accept unicode data.
        """
        fileDescriptor = FileDescriptor()
        self.assertRaises(TypeError, fileDescriptor.write, u'foo')


    def test_writeSequenceWithUnicodeRaisesException(self):
        """
        L{FileDescriptor.writeSequence} doesn't accept unicode data.
        """
        fileDescriptor = FileDescriptor()
        self.assertRaises(
            TypeError, fileDescriptor.writeSequence, ['foo', u'bar', 'baz'])


    def test_implementInterfaceIPushProducer(self):
        """
        L{FileDescriptor} should implement L{IPushProducer}.
        """
        self.assertTrue(verifyClass(IPushProducer, FileDescriptor))
