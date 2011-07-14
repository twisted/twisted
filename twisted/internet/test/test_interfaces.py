# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.interfaces}.
"""

from twisted.trial import unittest


class TestIFinishableConsumer(unittest.TestCase):
    """
    L{IFinishableConsumer} is deprecated.
    """

    def lookForDeprecationWarning(self, testmethod):
        """
        Importing C{testmethod} emits a deprecation warning.
        """
        warningsShown = self.flushWarnings([testmethod])
        self.assertEqual(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            "twisted.internet.interfaces.IFinishableConsumer "
            "was deprecated in Twisted 11.1.0: Please use IConsumer "
            "(and IConsumer.unregisterProducer) instead.")


    def test_deprecationWithDirectImport(self):
        """
        Importing L{IFinishableConsumer} causes a deprecation warning
        """
        from twisted.internet.interfaces import IFinishableConsumer
        self.lookForDeprecationWarning(
            TestIFinishableConsumer.test_deprecationWithDirectImport)


    def test_deprecationWithIndirectImport(self):
        """
        Importing L{interfaces} and implementing
        L{interfaces.IFinishableConsumer} causes a deprecation warning
        """
        from zope.interface import implements
        from twisted.internet import interfaces

        class FakeIFinishableConsumer:
            implements(interfaces.IFinishableConsumer)
            def finish(self):
                pass

        self.lookForDeprecationWarning(
            TestIFinishableConsumer.test_deprecationWithIndirectImport)
