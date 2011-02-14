# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names.common}.
"""

from twisted.trial.unittest import TestCase
from twisted.names.common import ResolverBase
from twisted.names.dns import EFORMAT, ESERVER, ENAME, ENOTIMP, EREFUSED
from twisted.names.error import DNSFormatError, DNSServerError, DNSNameError
from twisted.names.error import DNSNotImplementedError, DNSQueryRefusedError
from twisted.names.error import DNSUnknownError


class ExceptionForCodeTests(TestCase):
    """
    Tests for L{ResolverBase.exceptionForCode}.
    """
    def setUp(self):
        self.exceptionForCode = ResolverBase().exceptionForCode


    def test_eformat(self):
        """
        L{ResolverBase.exceptionForCode} converts L{EFORMAT} to
        L{DNSFormatError}.
        """
        self.assertIdentical(self.exceptionForCode(EFORMAT), DNSFormatError)


    def test_eserver(self):
        """
        L{ResolverBase.exceptionForCode} converts L{ESERVER} to
        L{DNSServerError}.
        """
        self.assertIdentical(self.exceptionForCode(ESERVER), DNSServerError)


    def test_ename(self):
        """
        L{ResolverBase.exceptionForCode} converts L{ENAME} to L{DNSNameError}.
        """
        self.assertIdentical(self.exceptionForCode(ENAME), DNSNameError)


    def test_enotimp(self):
        """
        L{ResolverBase.exceptionForCode} converts L{ENOTIMP} to
        L{DNSNotImplementedError}.
        """
        self.assertIdentical(
            self.exceptionForCode(ENOTIMP), DNSNotImplementedError)


    def test_erefused(self):
        """
        L{ResolverBase.exceptionForCode} converts L{EREFUSED} to
        L{DNSQueryRefusedError}.
        """
        self.assertIdentical(
            self.exceptionForCode(EREFUSED), DNSQueryRefusedError)


    def test_other(self):
        """
        L{ResolverBase.exceptionForCode} converts any other response code to
        L{DNSUnknownError}.
        """
        self.assertIdentical(
            self.exceptionForCode(object()), DNSUnknownError)
