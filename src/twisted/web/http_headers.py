# -*- test-case-name: twisted.web.test.test_http_headers -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An API for storing HTTP header names and values.
"""

from typing import (
    AnyStr,
    ClassVar,
    Dict,
    Iterator,
    List,
    Mapping,
    NewType,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

from twisted.python.compat import cmp, comparable

_T = TypeVar("_T")


def _sanitizeLinearWhitespace(headerComponent: bytes) -> bytes:
    r"""
    Replace linear whitespace (C{\n}, C{\r\n}, C{\r}) in a header key
    or value with a single space.

    @param headerComponent: The header key or value to sanitize.

    @return: The sanitized header key or value.
    """
    return b" ".join(headerComponent.splitlines())


# A header key whose values have been encoded to the appropriate format.
# Specific contents are implementation specific and may change, so do not
# create these directly.
_EncodedHeader = NewType("_EncodedHeader", bytes)


def _encodeName(name: Union[str, bytes]) -> _EncodedHeader:
    """
    Encode the name of a header (eg 'Content-Type') to an ISO-8859-1
    encoded bytestring if required.  It will be canonicalized and
    whitespace-sanitized.

    @param name: A HTTP header name

    @return: C{name}, encoded if required, lowercased
    """
    cache = Headers._canonicalHeaderCache

    if canonicalName := cache.get(name, None):
        return canonicalName

    bytes_name = name.encode("iso-8859-1") if isinstance(name, str) else name
    mappings = Headers._caseMappings
    result: _EncodedHeader
    if bytes_name.lower() in mappings:
        # Some headers have special capitalization:
        result = mappings[bytes_name.lower()]
    else:
        result = cast(
            _EncodedHeader,
            _sanitizeLinearWhitespace(
                b"-".join([word.capitalize() for word in bytes_name.split(b"-")])
            ),
        )

    # In general, we should only see a very small number of header
    # variations in the real world, so caching them is fine. However, an
    # attacker could generate infinite header variations to fill up RAM, so
    # we cap how many we cache. The performance degradation from lack of
    # caching won't be that bad, and legit traffic won't hit it.
    if len(cache) < Headers._MAX_CACHED_HEADERS:
        cache[name] = result

    return result


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
        to their canonicalized representation, for headers with unconventional
        capitalization.

    @cvar _canonicalHeaderCache: A L{dict} that maps header names to their
        canonicalized representation.

    @ivar _rawHeaders: A L{dict} mapping header names as L{bytes} to L{list}s of
        header values as L{bytes}.
    """

    _caseMappings: ClassVar[Dict[bytes, _EncodedHeader]] = {
        b"content-md5": _EncodedHeader(b"Content-MD5"),
        b"dnt": _EncodedHeader(b"DNT"),
        b"etag": _EncodedHeader(b"ETag"),
        b"p3p": _EncodedHeader(b"P3P"),
        b"te": _EncodedHeader(b"TE"),
        b"www-authenticate": _EncodedHeader(b"WWW-Authenticate"),
        b"x-xss-protection": _EncodedHeader(b"X-XSS-Protection"),
    }

    _canonicalHeaderCache: ClassVar[Dict[Union[bytes, str], _EncodedHeader]] = {}

    _MAX_CACHED_HEADERS: ClassVar[int] = 10_000

    __slots__ = ["_rawHeaders"]

    def __init__(
        self,
        rawHeaders: Optional[Mapping[AnyStr, Sequence[AnyStr]]] = None,
    ) -> None:
        self._rawHeaders: Dict[_EncodedHeader, List[bytes]] = {}
        if rawHeaders is not None:
            for name, values in rawHeaders.items():
                self.setRawHeaders(name, values)

    def __repr__(self) -> str:
        """
        Return a string fully describing the headers set on this object.
        """
        return "{}({!r})".format(
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
        return _encodeName(name) in self._rawHeaders

    def removeHeader(self, name: AnyStr) -> None:
        """
        Remove the named header from this header object.

        @param name: The name of the HTTP header to remove.

        @return: L{None}
        """
        self._rawHeaders.pop(_encodeName(name), None)

    def _setRawHeadersFaster(self, name: _EncodedHeader, values: List[bytes]) -> None:
        """
        Like C{setRawHeaders}, but faster.

        @param name: The name of the HTTP header to set the values for.

        @param values: A list of bytes, each one being a header value of the
            given name. These will be still be sanitized since otherwise it's
            too easy for security bugs to allow unescaped whitespace through.
        """
        self._rawHeaders[name] = [_sanitizeLinearWhitespace(v) for v in values]

    def _getRawHeaderLastFaster(self, name: _EncodedHeader) -> Optional[bytes]:
        """
        Get the last header value, if any.

        @param name: The name of the HTTP header to get the value for.
        """
        result = self._rawHeaders.get(name, None)
        if result is not None:
            return result[-1]
        else:
            return None

    def _getRawHeadersFaster(self, name: _EncodedHeader) -> Optional[list[bytes]]:
        """
        Get the header values, if any.

        @param name: The name of the HTTP header to get the values for.
        """
        return self._rawHeaders.get(name, None)

    def setRawHeaders(
        self, name: Union[str, bytes], values: Sequence[Union[str, bytes]]
    ) -> None:
        """
        Sets the raw representation of the given header.

        @param name: The name of the HTTP header to set the values for.

        @param values: A list of strings each one being a header value of
            the given name.

        @raise TypeError: Raised if C{values} is not a sequence of L{bytes}
            or L{str}, or if C{name} is not L{bytes} or L{str}.

        @return: L{None}
        """
        _name = _encodeName(name)
        encodedValues: List[bytes] = []
        for v in values:
            if isinstance(v, str):
                _v = v.encode("utf8")
            else:
                _v = v
            encodedValues.append(_sanitizeLinearWhitespace(_v))

        self._rawHeaders[_name] = encodedValues

    def addRawHeader(self, name: Union[str, bytes], value: Union[str, bytes]) -> None:
        """
        Add a new raw value for the given header.

        @param name: The name of the header for which to set the value.

        @param value: The value to set for the named header.
        """
        self._rawHeaders.setdefault(_encodeName(name), []).append(
            _sanitizeLinearWhitespace(
                value.encode("utf8") if isinstance(value, str) else value
            )
        )

    @overload
    def getRawHeaders(self, name: AnyStr) -> Optional[Sequence[AnyStr]]:
        ...

    @overload
    def getRawHeaders(self, name: AnyStr, default: _T) -> Union[Sequence[AnyStr], _T]:
        ...

    def getRawHeaders(
        self, name: AnyStr, default: Optional[_T] = None
    ) -> Union[Sequence[AnyStr], Optional[_T]]:
        """
        Returns a sequence of headers matching the given name as the raw string
        given.

        @param name: The name of the HTTP header to get the values of.

        @param default: The value to return if no header with the given C{name}
            exists.

        @return: If the named header is present, a sequence of its
            values.  Otherwise, C{default}.
        """
        encodedName = _encodeName(name)
        values = self._rawHeaders.get(encodedName, [])
        if not values:
            return default

        if isinstance(name, str):
            return [v.decode("utf8") for v in values]
        return values

    def getAllRawHeaders(self) -> Iterator[Tuple[bytes, Sequence[bytes]]]:
        """
        Return an iterator of key, value pairs of all headers contained in this
        object, as L{bytes}.  The keys are capitalized in canonical
        capitalization.
        """
        return iter(self._rawHeaders.items())


__all__ = ["Headers"]
