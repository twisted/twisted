# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{inetdconf}.
"""

from twisted.runner import inetdconf
from twisted.trial import unittest


class InvalidRPCServicesConfErrorTests(unittest.TestCase):
    """
    Tests for L{inetdconf.InvalidRPCServicesConfError}
    """

    def test_deprecation(self):
        """
        It is deprecated.
        """
        inetdconf.InvalidRPCServicesConfError('any', 'argument')

        message = (
            'twisted.runner.inetdconf.InvalidRPCServicesConfError was '
            'deprecated in Twisted 16.2.0: '
            'The RPC service configuration is no longer maintained.'
            )
        warnings = self.flushWarnings([self.test_deprecation])
        self.assertEqual(1, len(warnings))
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(message, warnings[0]['message'])



class RPCServicesConfTests(unittest.TestCase):
    """
    Tests for L{inetdconf.RPCServicesConf}
    """

    def test_deprecation(self):
        """
        It is deprecated.
        """
        inetdconf.RPCServicesConf()

        message = (
            'twisted.runner.inetdconf.RPCServicesConf was deprecated in '
            'Twisted 16.2.0: '
            'The RPC service configuration is no longer maintained.'
            )
        warnings = self.flushWarnings([self.test_deprecation])
        self.assertEqual(1, len(warnings))
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(message, warnings[0]['message'])
