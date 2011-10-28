# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Whitebox tests for L{twisted.internet.abstract.FileDescriptor}.
"""

from twisted.internet.abstract import FileDescriptor
from twisted.trial.unittest import TestCase



class FileDescriptorWriteSequenceTests(TestCase):
    """
    Tests for L{FileDescriptor.writeSequence}.
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
