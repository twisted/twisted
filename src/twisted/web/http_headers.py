# -*- test-case-name: twisted.web.test.test_http_headers -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An API for storing HTTP header names and values.
"""

from typing import List, Iterator, Tuple, Optional, Dict, Union, Any, AnyStr

from twisted.python.compat import comparable, cmp


def _dashCapitalize(name: bytes) -> bytes:
    """
    Return a byte string which is capitalized using '-' as a word separator.

    @param name: The name of the header to capitalize.

    @return: The given header capitalized using '-' as a word separator.
    """
    return b"-".join([word.capitalize() for word in name.split(b"-")])


def _sanitizeLinearWhitespace(headerComponent: bytes) -> bytes:
    r"""
    Replace linear whitespace (C{\n}, C{\r\n}, C{\r}) in a header key
    or value with a single space.

    @param headerComponent: The header key or value to sanitize.

    @return: The sanitized header key or value.
    """
    return b" ".join(headerComponent.splitlines())


@comparable
class Headers:
    """
    Stores HTTP headers in a key and multiple value format.

    When passed L{str}, header names (e.g. 'Content-Type')
    are encoded using ISO-8859-1 and header values (e.g.
    'text/html;charset=utf-8') are encoded using UTF-8. Some methods that return
    values will return them in the same type as the name given.

    If the header keys or values cannot be encoded or decoded using the rules
    above, using just L{bytes} arguments to the methods of this class will
    ensure no decoding or encoding is done, and L{Headers} will treat the keys
    and values as opaque byte strings.

    @cvar _caseMappings: A L{dict} that maps lowercase header names
        to their canonicalized representation.

    @ivar _rawHeaders: A L{dict} mapping header names as L{bytes} to L{list}s of
        header values as L{bytes}.
    """

    _caseMappings = {
        b"content-md5": b"Content-MD5",
        b"dnt": b"DNT",
        b"etag": b"ETag",
        b"p3p": b"P3P",
        b"te": b"TE",
        b"www-authenticate": b"WWW-Authenticate",
        b"x-xss-protection": b"X-XSS-Protection",
    }

    def __init__(
        self,
        rawHeaders: Optional[Dict[AnyStr, List[AnyStr]]] = None,
    ):
        self._rawHeaders = {}  # type: Dict[bytes, List[bytes]]
        if rawHeaders is not None:
            for name, values in rawHeaders.items():
                self.setRawHeaders(name, values)

    def __repr__(self) -> str:
        """
        Return a string fully describing the headers set on this object.
        """
        return "%s(%r)" % (
            self.__class__.__name__,
            self._rawHeaders,
        )

    def __cmp__(self, other):
        """
        Define L{Headers} instances as being equal to each other if they have
        the same raw headers.
        """
        if isinstance(other, Headers):
            return cmp(
                sorted(self._rawHeaders.items()), sorted(other._rawHeaders.items())
            )
        return NotImplemented

    def _encodeName(self, name: AnyStr) -> bytes:
        """
        Encode the name of a header (eg 'Content-Type') to an ISO-8859-1 encoded
        bytestring if required.

        @param name: A HTTP header name

        @return: C{name}, encoded if required, lowercased
        """
        if isinstance(name, str):
            return name.lower().encode("iso-8859-1")
        return name.lower()

    def _encodeValue(self, value: AnyStr) -> bytes:
        """
        Encode a single header value to a UTF-8 encoded bytestring if required.

        @param value: A single HTTP header value.

        @return: C{value}, encoded if required
        """
        if isinstance(value, str):
            return value.encode("utf8")
        return value

    def _encodeValues(self, values: List[AnyStr]) -> List[bytes]:
        """
        Encode a L{list} of header values to a L{list} of UTF-8 encoded
        bytestrings if required.

        @param values: A list of HTTP header values.

        @return: C{values}, with each item encoded if required
        """
        newValues = []

        for value in values:
            newValues.append(self._encodeValue(value))
        return newValues

    def _decodeValues(self, values: List[bytes]) -> List[str]:
        """
        Decode a L{list} of header values into a L{list} of Unicode strings.

        @param values: A list of HTTP header values.

        @return: C{values}, with each item decoded
        """
        newValues = []

        for value in values:
            newValues.append(value.decode("utf8"))
        return newValues

    def copy(self):
        """
        Return a copy of itself with the same headers set.

        @return: A new L{Headers}
        """
        return self.__class__(self._rawHeaders)

    def hasHeader(self, name: AnyStr) -> bool:
        """
        Check for the existence of a given header.

        @param name: The name of the HTTP header to check for.

        @return: C{True} if the header exists, otherwise C{False}.
        """
        return self._encodeName(name) in self._rawHeaders

    def removeHeader(self, name: AnyStr) -> None:
        """
        Remove the named header from this header object.

        @param name: The name of the HTTP header to remove.

        @return: L{None}
        """
        self._rawHeaders.pop(self._encodeName(name), None)

    def setRawHeaders(self, name: AnyStr, values: List[AnyStr]) -> None:
        """
        Sets the raw representation of the given header.

        @param name: The name of the HTTP header to set the values for.

        @param values: A list of strings each one being a header value of
            the given name.

        @raise TypeError: Raised if C{values} is not a L{list} of L{bytes}
            or L{str} strings, or if C{name} is not a L{bytes} or
            L{str} string.

        @return: L{None}
        """
        if not isinstance(values, list):
            raise TypeError(
                "Header entry %r should be list but found "
                "instance of %r instead" % (name, type(values))
            )

        if not isinstance(name, (bytes, str)):
            raise TypeError(
                "Header name is an instance of %r, " "not bytes or str" % (type(name),)
            )

        for count, value in enumerate(values):
            if not isinstance(value, (bytes, str)):
                raise TypeError(
                    "Header value at position %s is an instance of %r, not "
                    "bytes or str"
                    % (
                        count,
                        type(value),
                    )
                )

        _name = _sanitizeLinearWhitespace(self._encodeName(name))
        encodedValues = [
            _sanitizeLinearWhitespace(v) for v in self._encodeValues(values)
        ]

        self._rawHeaders[_name] = encodedValues

    def addRawHeader(self, name: AnyStr, value: AnyStr) -> None:
        """
        Add a new raw value for the given header.

        @param name: The name of the header for which to set the value.

        @param value: The value to set for the named header.
        """
        if not isinstance(name, (bytes, str)):
            raise TypeError(
                "Header name is an instance of %r, " "not bytes or str" % (type(name),)
            )

        if not isinstance(value, (bytes, str)):
            raise TypeError(
                "Header value is an instance of %r, not "
                "bytes or str" % (type(value),)
            )

        values = self.getRawHeaders(name)

        if values is not None:
            values.append(value)
        else:
            values = [value]

        self.setRawHeaders(name, values)

    def getRawHeaders(
        self, name: AnyStr, default: Optional[Any] = None
    ) -> Optional[Union[List[AnyStr], Any]]:
        """
        Returns a list of headers matching the given name as the raw string
        given.

        @param name: The name of the HTTP header to get the values of.

        @param default: The value to return if no header with the given C{name}
            exists.

        @return: If the named header is present, a L{list} of its
            values.  Otherwise, C{default}.
        """
        encodedName = self._encodeName(name)
        values = self._rawHeaders.get(encodedName, default)

        if isinstance(name, str) and values is not default and values is not None:
            return self._decodeValues(values)
        return values

    def getAllRawHeaders(self) -> Iterator[Tuple[bytes, List[bytes]]]:
        """
        Return an iterator of key, value pairs of all headers contained in this
        object, as L{bytes}.  The keys are capitalized in canonical
        capitalization.
        """
        for k, v in self._rawHeaders.items():
            yield self._canonicalNameCaps(k), v

    def _canonicalNameCaps(self, name: bytes) -> bytes:
        """
        Return the canonical name for the given header.

        @param name: The all-lowercase header name to capitalize in its
            canonical form.

        @return: The canonical name of the header.
        """
        return self._caseMappings.get(name, _dashCapitalize(name))


__all__ = ["Headers"]
