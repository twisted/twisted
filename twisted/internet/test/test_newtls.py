# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet._newtls}.
"""

from twisted.trial import unittest
try:
    from twisted.internet import _newtls
except ImportError:
    _newtls = None


class BypassTLSTests(unittest.TestCase):
    """
    Tests for the L{_newtls._BypassTLS} class.
    """

    if not _newtls:
        skip = "Couldn't import _newtls, perhaps pyOpenSSL is old or missing"

    def test_loseConnectionPassThrough(self):
        """
        C{_BypassTLS.loseConnection} calls C{loseConnection} on the base
        class, while preserving any default argument in the base class'
        C{loseConnection} implementation.
        """
        default = object()
        result = []

        class FakeTransport(object):
            def loseConnection(self, _connDone=default):
                result.append(_connDone)

        bypass = _newtls._BypassTLS(FakeTransport, FakeTransport())

        # The default from FakeTransport is used:
        bypass.loseConnection()
        self.assertEqual(result, [default])

        # And we can pass our own:
        notDefault = object()
        bypass.loseConnection(notDefault)
        self.assertEqual(result, [default, notDefault])
