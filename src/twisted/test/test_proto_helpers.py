# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest


class DeprecationTests(unittest.TestCase):
    """
    Deprecations in L{twisted.test.proto_helpers}.
    """
    def test_accumlatingProtocol(self):
        """
        L{proto_helpers.AccumlatingProtocol} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import AccumulatingProtocol
        warnings = self.flushWarnings(
            [self.test_accumlatingProtocol])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.AccumulatingProtocol was "
            "deprecated in Twisted 19.3.0: Please use "
            "twisted.protocols.utils.AccumulatingProtocol instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))

