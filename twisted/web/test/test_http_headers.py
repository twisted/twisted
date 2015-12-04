# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.http_headers}.
"""

from __future__ import division, absolute_import

from twisted.trial.unittest import TestCase
from twisted.web.http_headers import Headers

class HeadersTests(TestCase):
    """
    Tests for L{Headers}.
    """
    def test_initializer(self):
        """
        The header values passed to L{Headers.__init__} can be retrieved via
        L{Headers.getRawHeaders}.
        """
        h = Headers({b'Foo': [b'bar']})
        self.assertEqual(h.getRawHeaders(b'foo'), [b'bar'])


    def test_setRawHeaders(self):
        """
        L{Headers.setRawHeaders} sets the header values for the given
        header name to the sequence of byte string values.
        """
        rawValue = [b"value1", b"value2"]
        h = Headers()
        h.setRawHeaders(b"test", rawValue)
        self.assertTrue(h.hasHeader(b"test"))
        self.assertTrue(h.hasHeader(b"Test"))
        self.assertEqual(h.getRawHeaders(b"test"), rawValue)


    def test_rawHeadersTypeChecking(self):
        """
        L{Headers.setRawHeaders} requires values to be of type list.
        """
        h = Headers()
        self.assertRaises(TypeError, h.setRawHeaders, {b'Foo': b'bar'})


    def test_addRawHeader(self):
        """
        L{Headers.addRawHeader} adds a new value for a given header.
        """
        h = Headers()
        h.addRawHeader(b"test", b"lemur")
        self.assertEqual(h.getRawHeaders(b"test"), [b"lemur"])
        h.addRawHeader(b"test", b"panda")
        self.assertEqual(h.getRawHeaders(b"test"), [b"lemur", b"panda"])


    def test_getRawHeadersNoDefault(self):
        """
        L{Headers.getRawHeaders} returns C{None} if the header is not found and
        no default is specified.
        """
        self.assertIdentical(Headers().getRawHeaders(b"test"), None)


    def test_getRawHeadersDefaultValue(self):
        """
        L{Headers.getRawHeaders} returns the specified default value when no
        header is found.
        """
        h = Headers()
        default = object()
        self.assertIdentical(h.getRawHeaders(b"test", default), default)


    def test_getRawHeaders(self):
        """
        L{Headers.getRawHeaders} returns the values which have been set for a
        given header.
        """
        h = Headers()
        h.setRawHeaders(b"test", [b"lemur"])
        self.assertEqual(h.getRawHeaders(b"test"), [b"lemur"])
        self.assertEqual(h.getRawHeaders(b"Test"), [b"lemur"])


    def test_hasHeaderTrue(self):
        """
        Check that L{Headers.hasHeader} returns C{True} when the given header
        is found.
        """
        h = Headers()
        h.setRawHeaders(b"test", [b"lemur"])
        self.assertTrue(h.hasHeader(b"test"))
        self.assertTrue(h.hasHeader(b"Test"))


    def test_hasHeaderFalse(self):
        """
        L{Headers.hasHeader} returns C{False} when the given header is not
        found.
        """
        self.assertFalse(Headers().hasHeader(b"test"))


    def test_removeHeader(self):
        """
        Check that L{Headers.removeHeader} removes the given header.
        """
        h = Headers()

        h.setRawHeaders(b"foo", [b"lemur"])
        self.assertTrue(h.hasHeader(b"foo"))
        h.removeHeader(b"foo")
        self.assertFalse(h.hasHeader(b"foo"))

        h.setRawHeaders(b"bar", [b"panda"])
        self.assertTrue(h.hasHeader(b"bar"))
        h.removeHeader(b"Bar")
        self.assertFalse(h.hasHeader(b"bar"))


    def test_removeHeaderDoesntExist(self):
        """
        L{Headers.removeHeader} is a no-operation when the specified header is
        not found.
        """
        h = Headers()
        h.removeHeader(b"test")
        self.assertEqual(list(h.getAllRawHeaders()), [])


    def test_canonicalNameCaps(self):
        """
        L{Headers._canonicalNameCaps} returns the canonical capitalization for
        the given header.
        """
        h = Headers()
        self.assertEqual(h._canonicalNameCaps(b"test"), b"Test")
        self.assertEqual(h._canonicalNameCaps(b"test-stuff"), b"Test-Stuff")
        self.assertEqual(h._canonicalNameCaps(b"content-md5"), b"Content-MD5")
        self.assertEqual(h._canonicalNameCaps(b"dnt"), b"DNT")
        self.assertEqual(h._canonicalNameCaps(b"etag"), b"ETag")
        self.assertEqual(h._canonicalNameCaps(b"p3p"), b"P3P")
        self.assertEqual(h._canonicalNameCaps(b"te"), b"TE")
        self.assertEqual(h._canonicalNameCaps(b"www-authenticate"),
                          b"WWW-Authenticate")
        self.assertEqual(h._canonicalNameCaps(b"x-xss-protection"),
                          b"X-XSS-Protection")


    def test_getAllRawHeaders(self):
        """
        L{Headers.getAllRawHeaders} returns an iterable of (k, v) pairs, where
        C{k} is the canonicalized representation of the header name, and C{v}
        is a sequence of values.
        """
        h = Headers()
        h.setRawHeaders(b"test", [b"lemurs"])
        h.setRawHeaders(b"www-authenticate", [b"basic aksljdlk="])

        allHeaders = set([(k, tuple(v)) for k, v in h.getAllRawHeaders()])

        self.assertEqual(allHeaders,
                          set([(b"WWW-Authenticate", (b"basic aksljdlk=",)),
                               (b"Test", (b"lemurs",))]))


    def test_headersComparison(self):
        """
        A L{Headers} instance compares equal to itself and to another
        L{Headers} instance with the same values.
        """
        first = Headers()
        first.setRawHeaders(b"foo", [b"panda"])
        second = Headers()
        second.setRawHeaders(b"foo", [b"panda"])
        third = Headers()
        third.setRawHeaders(b"foo", [b"lemur", b"panda"])
        self.assertEqual(first, first)
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)


    def test_otherComparison(self):
        """
        An instance of L{Headers} does not compare equal to other unrelated
        objects.
        """
        h = Headers()
        self.assertNotEqual(h, ())
        self.assertNotEqual(h, object())
        self.assertNotEqual(h, b"foo")


    def test_repr(self):
        """
        The L{repr} of a L{Headers} instance shows the names and values of all
        the headers it contains.
        """
        foo = b"foo"
        bar = b"bar"
        baz = b"baz"
        self.assertEqual(
            repr(Headers({foo: [bar, baz]})),
            "Headers({%r: [%r, %r]})" % (foo, bar, baz))


    def test_subclassRepr(self):
        """
        The L{repr} of an instance of a subclass of L{Headers} uses the name
        of the subclass instead of the string C{"Headers"}.
        """
        foo = b"foo"
        bar = b"bar"
        baz = b"baz"
        class FunnyHeaders(Headers):
            pass
        self.assertEqual(
            repr(FunnyHeaders({foo: [bar, baz]})),
            "FunnyHeaders({%r: [%r, %r]})" % (foo, bar, baz))


    def test_copy(self):
        """
        L{Headers.copy} creates a new independant copy of an existing
        L{Headers} instance, allowing future modifications without impacts
        between the copies.
        """
        h = Headers()
        h.setRawHeaders(b'test', [b'foo'])
        i = h.copy()
        self.assertEqual(i.getRawHeaders(b'test'), [b'foo'])
        h.addRawHeader(b'test', b'bar')
        self.assertEqual(i.getRawHeaders(b'test'), [b'foo'])
        i.addRawHeader(b'test', b'baz')
        self.assertEqual(h.getRawHeaders(b'test'), [b'foo', b'bar'])
