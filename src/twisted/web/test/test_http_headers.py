# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.http_headers}.
"""

from __future__ import annotations

from typing import Sequence

from twisted.trial.unittest import SynchronousTestCase, TestCase
from twisted.web.http_headers import Headers, InvalidHeaderName, _nameEncoder
from twisted.web.test.requesthelper import (
    bytesLinearWhitespaceComponents,
    sanitizedBytes,
    textLinearWhitespaceComponents,
)


class NameEncoderTests(SynchronousTestCase):
    """
    Test L{twisted.web.http_headers._NameEncoder}
    """

    def test_encodeName(self) -> None:
        """
        L{_NameEncoder.encode} returns the canonical capitalization for
        the given header.
        """
        self.assertEqual(_nameEncoder.encode(b"test"), b"Test")
        self.assertEqual(_nameEncoder.encode(b"test-stuff"), b"Test-Stuff")
        self.assertEqual(_nameEncoder.encode(b"content-md5"), b"Content-MD5")
        self.assertEqual(_nameEncoder.encode(b"dnt"), b"DNT")
        self.assertEqual(_nameEncoder.encode(b"etag"), b"ETag")
        self.assertEqual(_nameEncoder.encode(b"p3p"), b"P3P")
        self.assertEqual(_nameEncoder.encode(b"te"), b"TE")
        self.assertEqual(_nameEncoder.encode(b"www-authenticate"), b"WWW-Authenticate")
        self.assertEqual(_nameEncoder.encode(b"WWW-authenticate"), b"WWW-Authenticate")
        self.assertEqual(_nameEncoder.encode(b"Www-Authenticate"), b"WWW-Authenticate")
        self.assertEqual(_nameEncoder.encode(b"x-xss-protection"), b"X-XSS-Protection")

    def test_encodeNameStr(self) -> None:
        """
        L{_NameEncoder.encode} returns the canonical capitalization for
        a header name given as a L{str}.
        """
        self.assertEqual(_nameEncoder.encode("test"), b"Test")
        self.assertEqual(_nameEncoder.encode("test-stuff"), b"Test-Stuff")
        self.assertEqual(_nameEncoder.encode("content-md5"), b"Content-MD5")
        self.assertEqual(_nameEncoder.encode("dnt"), b"DNT")
        self.assertEqual(_nameEncoder.encode("etag"), b"ETag")
        self.assertEqual(_nameEncoder.encode("p3p"), b"P3P")
        self.assertEqual(_nameEncoder.encode("te"), b"TE")
        self.assertEqual(_nameEncoder.encode("www-authenticate"), b"WWW-Authenticate")
        self.assertEqual(_nameEncoder.encode("WWW-authenticate"), b"WWW-Authenticate")
        self.assertEqual(_nameEncoder.encode("Www-Authenticate"), b"WWW-Authenticate")
        self.assertEqual(_nameEncoder.encode("x-xss-protection"), b"X-XSS-Protection")

    def test_maxCachedHeaders(self) -> None:
        """
        Only a limited number of HTTP header names get cached.
        """
        headers = Headers()
        for i in range(_nameEncoder._MAX_CACHED_HEADERS + 200):
            headers.addRawHeader(f"hello-{i}", "value")
        self.assertEqual(
            len(_nameEncoder._canonicalHeaderCache), _nameEncoder._MAX_CACHED_HEADERS
        )


def assertSanitized(
    testCase: TestCase, components: Sequence[bytes] | Sequence[str], expected: bytes
) -> None:
    """
    Assert that the components are sanitized to the expected value as
    both a header value, across all of L{Header}'s setters and getters.

    @param testCase: A test case.

    @param components: A sequence of values that contain linear
        whitespace to use as header values; see
        C{textLinearWhitespaceComponents} and
        C{bytesLinearWhitespaceComponents}

    @param expected: The expected sanitized form of the component as
        a header value.
    """
    name = b"Name"
    for component in components:
        headers = []
        headers.append(Headers({name: [component]}))  # type: ignore[misc]

        added = Headers()
        added.addRawHeader(name, component)
        headers.append(added)

        setHeader = Headers()
        setHeader.setRawHeaders(name, [component])
        headers.append(setHeader)

        for header in headers:
            testCase.assertEqual(list(header.getAllRawHeaders()), [(name, [expected])])
            testCase.assertEqual(header.getRawHeaders(name), [expected])


class BytesHeadersTests(TestCase):
    """
    Tests for L{Headers}, using L{bytes} arguments for methods.
    """

    def test_sanitizeLinearWhitespace(self) -> None:
        """
        Linear whitespace in header names or values is replaced with a
        single space.
        """
        assertSanitized(self, bytesLinearWhitespaceComponents, sanitizedBytes)

    def test_initializer(self) -> None:
        """
        The header values passed to L{Headers.__init__} can be retrieved via
        L{Headers.getRawHeaders}.
        """
        h = Headers({b"Foo": [b"bar"]})
        self.assertEqual(h.getRawHeaders(b"foo"), [b"bar"])

    def test_setRawHeaders(self) -> None:
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

    def test_addRawHeader(self) -> None:
        """
        L{Headers.addRawHeader} adds a new value for a given header.
        """
        h = Headers()
        h.addRawHeader(b"test", b"lemur")
        self.assertEqual(h.getRawHeaders(b"test"), [b"lemur"])
        h.addRawHeader(b"test", b"panda")
        self.assertEqual(h.getRawHeaders(b"test"), [b"lemur", b"panda"])

    def test_getRawHeadersNoDefault(self) -> None:
        """
        L{Headers.getRawHeaders} returns L{None} if the header is not found and
        no default is specified.
        """
        self.assertIsNone(Headers().getRawHeaders(b"test"))

    def test_getRawHeadersDefaultValue(self) -> None:
        """
        L{Headers.getRawHeaders} returns the specified default value when no
        header is found.
        """
        h = Headers()
        default = object()
        self.assertIdentical(h.getRawHeaders(b"test", default), default)

    def test_getRawHeadersWithDefaultMatchingValue(self) -> None:
        """
        If the object passed as the value list to L{Headers.setRawHeaders}
        is later passed as a default to L{Headers.getRawHeaders}, the
        result nevertheless contains encoded values.
        """
        h = Headers()
        default = ["value"]
        h.setRawHeaders(b"key", default)
        self.assertIsInstance(h.getRawHeaders(b"key", default)[0], bytes)
        self.assertEqual(h.getRawHeaders(b"key", default), [b"value"])

    def test_getRawHeaders(self) -> None:
        """
        L{Headers.getRawHeaders} returns the values which have been set for a
        given header.
        """
        h = Headers()
        h.setRawHeaders(b"test", [b"lemur"])
        self.assertEqual(h.getRawHeaders(b"test"), [b"lemur"])
        self.assertEqual(h.getRawHeaders(b"Test"), [b"lemur"])

    def test_hasHeaderTrue(self) -> None:
        """
        Check that L{Headers.hasHeader} returns C{True} when the given header
        is found.
        """
        h = Headers()
        h.setRawHeaders(b"test", [b"lemur"])
        self.assertTrue(h.hasHeader(b"test"))
        self.assertTrue(h.hasHeader(b"Test"))

    def test_hasHeaderFalse(self) -> None:
        """
        L{Headers.hasHeader} returns C{False} when the given header is not
        found.
        """
        self.assertFalse(Headers().hasHeader(b"test"))

    def test_removeHeader(self) -> None:
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

    def test_removeHeaderDoesntExist(self) -> None:
        """
        L{Headers.removeHeader} is a no-operation when the specified header is
        not found.
        """
        h = Headers()
        h.removeHeader(b"test")
        self.assertEqual(list(h.getAllRawHeaders()), [])

    def test_getAllRawHeaders(self) -> None:
        """
        L{Headers.getAllRawHeaders} returns an iterable of (k, v) pairs, where
        C{k} is the canonicalized representation of the header name, and C{v}
        is a sequence of values.
        """
        h = Headers()
        h.setRawHeaders(b"test", [b"lemurs"])
        h.setRawHeaders(b"www-authenticate", [b"basic aksljdlk="])

        allHeaders = {(k, tuple(v)) for k, v in h.getAllRawHeaders()}

        self.assertEqual(
            allHeaders,
            {(b"WWW-Authenticate", (b"basic aksljdlk=",)), (b"Test", (b"lemurs",))},
        )

    def test_headersComparison(self) -> None:
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

    def test_otherComparison(self) -> None:
        """
        An instance of L{Headers} does not compare equal to other unrelated
        objects.
        """
        h = Headers()
        self.assertNotEqual(h, ())
        self.assertNotEqual(h, object())
        self.assertNotEqual(h, b"foo")

    def test_repr(self) -> None:
        """
        The L{repr} of a L{Headers} instance shows the names and values of all
        the headers it contains.
        """
        foo = b"foo"
        bar = b"bar"
        baz = b"baz"
        self.assertEqual(
            repr(Headers({foo: [bar, baz]})),
            f"Headers({{{foo.capitalize()!r}: [{bar!r}, {baz!r}]}})",
        )

    def test_reprWithRawBytes(self) -> None:
        """
        The L{repr} of a L{Headers} instance shows the names and values of all
        the headers it contains, not attempting to decode any raw bytes.
        """
        # There's no such thing as undecodable latin-1, you'll just get
        # some mojibake
        foo = b"foo"
        # But this is invalid UTF-8! So, any accidental decoding/encoding will
        # throw an exception.
        bar = b"bar\xe1"
        baz = b"baz\xe1"
        self.assertEqual(
            repr(Headers({foo: [bar, baz]})),
            f"Headers({{{foo.capitalize()!r}: [{bar!r}, {baz!r}]}})",
        )

    def test_subclassRepr(self) -> None:
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
            f"FunnyHeaders({{{foo.capitalize()!r}: [{bar!r}, {baz!r}]}})",
        )

    def test_copy(self) -> None:
        """
        L{Headers.copy} creates a new independent copy of an existing
        L{Headers} instance, allowing future modifications without impacts
        between the copies.
        """
        h = Headers()
        h.setRawHeaders(b"test", [b"foo"])
        i = h.copy()
        self.assertEqual(i.getRawHeaders(b"test"), [b"foo"])
        h.addRawHeader(b"test", b"bar")
        self.assertEqual(i.getRawHeaders(b"test"), [b"foo"])
        i.addRawHeader(b"test", b"baz")
        self.assertEqual(h.getRawHeaders(b"test"), [b"foo", b"bar"])


class UnicodeHeadersTests(TestCase):
    """
    Tests for L{Headers}, using L{str} arguments for methods.
    """

    def test_sanitizeLinearWhitespace(self) -> None:
        """
        Linear whitespace in header names or values is replaced with a
        single space.
        """
        assertSanitized(self, textLinearWhitespaceComponents, sanitizedBytes)

    def test_initializer(self) -> None:
        """
        The header values passed to L{Headers.__init__} can be retrieved via
        L{Headers.getRawHeaders}. If a L{bytes} argument is given, it returns
        L{bytes} values, and if a L{str} argument is given, it returns
        L{str} values. Both are the same header value, just encoded or
        decoded.
        """
        h = Headers({"Foo": ["bar"]})
        self.assertEqual(h.getRawHeaders(b"foo"), [b"bar"])
        self.assertEqual(h.getRawHeaders("foo"), ["bar"])

    def test_setRawHeaders(self) -> None:
        """
        L{Headers.setRawHeaders} sets the header values for the given
        header name to the sequence of strings, encoded.
        """
        rawValue = ["value1", "value2"]
        rawEncodedValue = [b"value1", b"value2"]
        h = Headers()
        h.setRawHeaders("test", rawValue)
        self.assertTrue(h.hasHeader(b"test"))
        self.assertTrue(h.hasHeader(b"Test"))
        self.assertTrue(h.hasHeader("test"))
        self.assertTrue(h.hasHeader("Test"))
        self.assertEqual(h.getRawHeaders("test"), rawValue)
        self.assertEqual(h.getRawHeaders(b"test"), rawEncodedValue)

    def test_nameNotEncodable(self) -> None:
        """
        Passing L{str} to any function that takes a header name will encode
        said header name as ISO-8859-1, and if it cannot be encoded, it will
        raise a L{UnicodeDecodeError}.
        """
        h = Headers()

        # Only these two functions take names
        with self.assertRaises(UnicodeEncodeError):
            h.setRawHeaders("\u2603", ["val"])

        with self.assertRaises(UnicodeEncodeError):
            h.hasHeader("\u2603")

    def test_nameNotToken(self) -> None:
        """
        HTTP header names must be tokens, so any names containing non-token
        characters raises L{InvalidHeaderName}
        """
        h = Headers()

        # A non-token character within ISO-8851-1
        self.assertRaises(InvalidHeaderName, h.setRawHeaders, b"\xe1", [b"val"])
        self.assertRaises(InvalidHeaderName, h.setRawHeaders, "\u00e1", [b"val"])

        # Whitespace
        self.assertRaises(InvalidHeaderName, h.setRawHeaders, b"a b", [b"val"])
        self.assertRaises(InvalidHeaderName, h.setRawHeaders, "c\nd", [b"val"])
        self.assertRaises(InvalidHeaderName, h.setRawHeaders, "c\td", [b"val"])

    def test_nameEncoding(self) -> None:
        """
        Passing L{str} to any function that takes a header name will encode
        said header name as ISO-8859-1.
        """
        h = Headers()

        # We set it using a Unicode string.
        h.setRawHeaders("bar", [b"foo"])

        # It's encoded to the ISO-8859-1 value, which we can use to access it
        self.assertTrue(h.hasHeader(b"bar"))
        self.assertEqual(h.getRawHeaders(b"bar"), [b"foo"])

        # We can still access it using the Unicode string..
        self.assertTrue(h.hasHeader("bar"))

    def test_rawHeadersValueEncoding(self) -> None:
        """
        Passing L{str} to L{Headers.setRawHeaders} will encode the name as
        ISO-8859-1 and values as UTF-8.
        """
        h = Headers()
        h.setRawHeaders("x", ["\u2603", b"foo"])
        self.assertTrue(h.hasHeader(b"x"))
        self.assertEqual(h.getRawHeaders(b"x"), [b"\xe2\x98\x83", b"foo"])

    def test_addRawHeader(self) -> None:
        """
        L{Headers.addRawHeader} adds a new value for a given header.
        """
        h = Headers()
        h.addRawHeader("test", "lemur")
        self.assertEqual(h.getRawHeaders("test"), ["lemur"])
        h.addRawHeader("test", "panda")
        self.assertEqual(h.getRawHeaders("test"), ["lemur", "panda"])
        self.assertEqual(h.getRawHeaders(b"test"), [b"lemur", b"panda"])

    def test_getRawHeadersNoDefault(self) -> None:
        """
        L{Headers.getRawHeaders} returns L{None} if the header is not found and
        no default is specified.
        """
        self.assertIsNone(Headers().getRawHeaders("test"))

    def test_getRawHeadersDefaultValue(self) -> None:
        """
        L{Headers.getRawHeaders} returns the specified default value when no
        header is found.
        """
        h = Headers()
        default = object()
        self.assertIdentical(h.getRawHeaders("test", default), default)
        self.assertIdentical(h.getRawHeaders("test", None), None)
        self.assertEqual(h.getRawHeaders("test", [None]), [None])
        self.assertEqual(
            h.getRawHeaders("test", ["\N{SNOWMAN}"]),
            ["\N{SNOWMAN}"],
        )

    def test_getRawHeadersWithDefaultMatchingValue(self) -> None:
        """
        If the object passed as the value list to L{Headers.setRawHeaders}
        is later passed as a default to L{Headers.getRawHeaders}, the
        result nevertheless contains decoded values.
        """
        h = Headers()
        default = [b"value"]
        h.setRawHeaders(b"key", default)
        self.assertIsInstance(h.getRawHeaders("key", default)[0], str)
        self.assertEqual(h.getRawHeaders("key", default), ["value"])

    def test_getRawHeaders(self) -> None:
        """
        L{Headers.getRawHeaders} returns the values which have been set for a
        given header.
        """
        h = Headers()
        h.setRawHeaders("test", ["lemur"])
        self.assertEqual(h.getRawHeaders("test"), ["lemur"])
        self.assertEqual(h.getRawHeaders("Test"), ["lemur"])
        self.assertEqual(h.getRawHeaders(b"test"), [b"lemur"])
        self.assertEqual(h.getRawHeaders(b"Test"), [b"lemur"])

    def test_hasHeaderTrue(self) -> None:
        """
        Check that L{Headers.hasHeader} returns C{True} when the given header
        is found.
        """
        h = Headers()
        h.setRawHeaders("test", ["lemur"])
        self.assertTrue(h.hasHeader("test"))
        self.assertTrue(h.hasHeader("Test"))
        self.assertTrue(h.hasHeader(b"test"))
        self.assertTrue(h.hasHeader(b"Test"))

    def test_hasHeaderFalse(self) -> None:
        """
        L{Headers.hasHeader} returns C{False} when the given header is not
        found.
        """
        self.assertFalse(Headers().hasHeader("test"))

    def test_removeHeader(self) -> None:
        """
        Check that L{Headers.removeHeader} removes the given header.
        """
        h = Headers()

        h.setRawHeaders("foo", ["lemur"])
        self.assertTrue(h.hasHeader("foo"))
        h.removeHeader("foo")
        self.assertFalse(h.hasHeader("foo"))
        self.assertFalse(h.hasHeader(b"foo"))

        h.setRawHeaders("bar", ["panda"])
        self.assertTrue(h.hasHeader("bar"))
        h.removeHeader("Bar")
        self.assertFalse(h.hasHeader("bar"))
        self.assertFalse(h.hasHeader(b"bar"))

    def test_removeHeaderDoesntExist(self) -> None:
        """
        L{Headers.removeHeader} is a no-operation when the specified header is
        not found.
        """
        h = Headers()
        h.removeHeader("test")
        self.assertEqual(list(h.getAllRawHeaders()), [])

    def test_getAllRawHeaders(self) -> None:
        """
        L{Headers.getAllRawHeaders} returns an iterable of (k, v) pairs, where
        C{k} is the canonicalized representation of the header name, and C{v}
        is a sequence of values.
        """
        h = Headers()
        h.setRawHeaders("test", ["lemurs"])
        h.setRawHeaders("www-authenticate", ["basic aksljdlk="])
        h.setRawHeaders("content-md5", ["kjdfdfgdfgnsd"])

        allHeaders = {(k, tuple(v)) for k, v in h.getAllRawHeaders()}

        self.assertEqual(
            allHeaders,
            {
                (b"WWW-Authenticate", (b"basic aksljdlk=",)),
                (b"Content-MD5", (b"kjdfdfgdfgnsd",)),
                (b"Test", (b"lemurs",)),
            },
        )

    def test_headersComparison(self) -> None:
        """
        A L{Headers} instance compares equal to itself and to another
        L{Headers} instance with the same values.
        """
        first = Headers()
        first.setRawHeaders("foo", ["panda"])
        second = Headers()
        second.setRawHeaders("foo", ["panda"])
        third = Headers()
        third.setRawHeaders("foo", ["lemur", "panda"])

        self.assertEqual(first, first)
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

        # Headers instantiated with bytes equivs are also the same
        firstBytes = Headers()
        firstBytes.setRawHeaders(b"foo", [b"panda"])
        secondBytes = Headers()
        secondBytes.setRawHeaders(b"foo", [b"panda"])
        thirdBytes = Headers()
        thirdBytes.setRawHeaders(b"foo", [b"lemur", "panda"])

        self.assertEqual(first, firstBytes)
        self.assertEqual(second, secondBytes)
        self.assertEqual(third, thirdBytes)

    def test_otherComparison(self) -> None:
        """
        An instance of L{Headers} does not compare equal to other unrelated
        objects.
        """
        h = Headers()
        self.assertNotEqual(h, ())
        self.assertNotEqual(h, object())
        self.assertNotEqual(h, "foo")

    def test_repr(self) -> None:
        """
        The L{repr} of a L{Headers} instance shows the names and values of all
        the headers it contains. This shows only reprs of bytes values, as
        undecodable headers may cause an exception.
        """
        foo = "foo"
        bar = "bar\u2603"
        baz = "baz"
        fooEncoded = "'Foo'"
        barEncoded = "'bar\\xe2\\x98\\x83'"
        fooEncoded = "b" + fooEncoded
        barEncoded = "b" + barEncoded
        self.assertEqual(
            repr(Headers({foo: [bar, baz]})),
            "Headers({{{}: [{}, {!r}]}})".format(
                fooEncoded, barEncoded, baz.encode("utf8")
            ),
        )

    def test_subclassRepr(self) -> None:
        """
        The L{repr} of an instance of a subclass of L{Headers} uses the name
        of the subclass instead of the string C{"Headers"}.
        """
        foo = "foo"
        bar = "bar\u2603"
        baz = "baz"
        fooEncoded = "b'Foo'"
        barEncoded = "b'bar\\xe2\\x98\\x83'"

        class FunnyHeaders(Headers):
            pass

        self.assertEqual(
            repr(FunnyHeaders({foo: [bar, baz]})),
            "FunnyHeaders({%s: [%s, %r]})"
            % (fooEncoded, barEncoded, baz.encode("utf8")),
        )

    def test_copy(self) -> None:
        """
        L{Headers.copy} creates a new independent copy of an existing
        L{Headers} instance, allowing future modifications without impacts
        between the copies.
        """
        h = Headers()
        h.setRawHeaders("test", ["foo\u2603"])
        i = h.copy()

        # The copy contains the same value as the original
        self.assertEqual(i.getRawHeaders("test"), ["foo\u2603"])
        self.assertEqual(i.getRawHeaders(b"test"), [b"foo\xe2\x98\x83"])

        # Add a header to the original
        h.addRawHeader("test", "bar")

        # Verify that the copy has not changed
        self.assertEqual(i.getRawHeaders("test"), ["foo\u2603"])
        self.assertEqual(i.getRawHeaders(b"test"), [b"foo\xe2\x98\x83"])

        # Add a header to the copy
        i.addRawHeader("Test", b"baz")

        # Verify that the orignal does not have it
        self.assertEqual(h.getRawHeaders("test"), ["foo\u2603", "bar"])
        self.assertEqual(h.getRawHeaders(b"test"), [b"foo\xe2\x98\x83", b"bar"])


class MixedHeadersTests(TestCase):
    """
    Tests for L{Headers}, mixing L{bytes} and L{str} arguments for methods
    where that is permitted.
    """

    def test_addRawHeader(self) -> None:
        """
        L{Headers.addRawHeader} accepts mixed L{str} and L{bytes}.
        """
        h = Headers()
        h.addRawHeader(b"bytes", "str")
        h.addRawHeader("str", b"bytes")

        self.assertEqual(h.getRawHeaders(b"Bytes"), [b"str"])
        self.assertEqual(h.getRawHeaders("Str"), ["bytes"])

    def test_setRawHeaders(self) -> None:
        """
        L{Headers.setRawHeaders} accepts mixed L{str} and L{bytes}.
        """
        h = Headers()
        h.setRawHeaders(b"bytes", [b"bytes"])
        h.setRawHeaders("str", ["str"])
        h.setRawHeaders("mixed-str", [b"bytes", "str"])
        h.setRawHeaders(b"mixed-bytes", ["str", b"bytes"])

        self.assertEqual(h.getRawHeaders(b"Bytes"), [b"bytes"])
        self.assertEqual(h.getRawHeaders("Str"), ["str"])
        self.assertEqual(h.getRawHeaders("Mixed-Str"), ["bytes", "str"])
        self.assertEqual(h.getRawHeaders(b"Mixed-Bytes"), [b"str", b"bytes"])
