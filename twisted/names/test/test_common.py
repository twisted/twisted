# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names.common}.
"""

from __future__ import division, absolute_import

from twisted.trial.unittest import SynchronousTestCase
from twisted.python.failure import Failure
from twisted.names.common import ResolverBase, prepareIDNName
from twisted.names.dns import EFORMAT, ESERVER, ENAME, ENOTIMP, EREFUSED, Query
from twisted.names.error import DNSFormatError, DNSServerError, DNSNameError
from twisted.names.error import DNSNotImplementedError, DNSQueryRefusedError
from twisted.names.error import DNSUnknownError


class ExceptionForCodeTests(SynchronousTestCase):
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



class QueryTests(SynchronousTestCase):
    """
    Tests for L{ResolverBase.query}.
    """
    def test_typeToMethodDispatch(self):
        """
        L{ResolverBase.query} looks up a method to invoke using the type of the
        query passed to it and the C{typeToMethod} mapping on itself.
        """
        results = []
        resolver = ResolverBase()
        resolver.typeToMethod = {
            12345: lambda query, timeout: results.append((query, timeout))}
        query = Query(name=b"example.com", type=12345)
        resolver.query(query, 123)
        self.assertEqual([(b"example.com", 123)], results)


    def test_typeToMethodResult(self):
        """
        L{ResolverBase.query} returns a L{Deferred} which fires with the result
        of the method found in the C{typeToMethod} mapping for the type of the
        query passed to it.
        """
        expected = object()
        resolver = ResolverBase()
        resolver.typeToMethod = {54321: lambda query, timeout: expected}
        query = Query(name=b"example.com", type=54321)
        queryDeferred = resolver.query(query, 123)
        result = []
        queryDeferred.addBoth(result.append)
        self.assertEqual(expected, result[0])


    def test_unknownQueryType(self):
        """
        L{ResolverBase.query} returns a L{Deferred} which fails with
        L{NotImplementedError} when called with a query of a type not present in
        its C{typeToMethod} dictionary.
        """
        resolver = ResolverBase()
        resolver.typeToMethod = {}
        query = Query(name=b"example.com", type=12345)
        queryDeferred = resolver.query(query, 123)
        result = []
        queryDeferred.addBoth(result.append)
        self.assertIsInstance(result[0], Failure)
        result[0].trap(NotImplementedError)



class PrepareIDNNameTests(SynchronousTestCase):
    """
    Tests for L{common.prepareIDNName}.
    """

    def test_bytestring(self):
        """
        An ASCII-encoded byte string is left as-is.
        """
        name = b"example.com"
        result = prepareIDNName(name)
        self.assertEqual(b"example.com", result)


    def test_unicode(self):
        """
        A unicode all-ASCII name is converted to an ASCII byte string.
        """
        name = u"example.com"
        result = prepareIDNName(name)
        self.assertEqual(b"example.com", result)


    def test_unicodeNonASCII(self):
        """
        A unicode with non-ASCII is converted to its ACE equivalent.
        """
        name = u"\u00e9chec.example.com"
        result = prepareIDNName(name)
        self.assertEqual(b"xn--chec-9oa.example.com", result)


    def test_unicodeHalfwidthIdeographicFullStop(self):
        """
        Exotic dots in unicode names are converted to Full Stop.
        """
        name = u"\u00e9chec.example\uff61com"
        result = prepareIDNName(name)
        self.assertEqual(b"xn--chec-9oa.example.com", result)


    def test_unicodeTrailingDot(self):
        """
        Unicode names with trailing dots retain the trailing dot.

        L{encodings.idna.ToASCII} doesn't allow the empty string as the input,
        hence the implementation needs to strip a trailing dot, and re-add it
        after encoding the labels.
        """
        name = u"example.com."
        result = prepareIDNName(name)
        self.assertEqual(b"example.com.", result)
