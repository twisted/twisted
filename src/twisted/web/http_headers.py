# -*- test-case-name: twisted.web.test.test_http_headers -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An API for storing HTTP header names and values.
"""
from __future__ import annotations

from typing import (
    AnyStr,
    ClassVar,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from twisted.python.compat import cmp, comparable
from twisted.web._abnf import _istoken


class InvalidHeaderName(ValueError):
    """
    HTTP header names must be tokens, per RFC 9110 section 5.1.
    """


_T = TypeVar("_T")


def _sanitizeLinearWhitespace(headerComponent: bytes) -> bytes:
    r"""
    Replace linear whitespace (C{\n}, C{\r\n}, C{\r}) in a header
    value with a single space.

    @param headerComponent: The header value to sanitize.

    @return: The sanitized header value.
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

    @ivar _rawHeaders: A L{dict} mapping header names as L{bytes} to L{list}s of
        header values as L{bytes}.
    """

    __slots__ = ["_rawHeaders"]

    def __init__(
        self,
        rawHeaders: Optional[Mapping[AnyStr, Sequence[AnyStr]]] = None,
    ) -> None:
        self._rawHeaders: Dict[bytes, List[bytes]] = {}
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

    def copy(self) -> Headers:
        """
        Return a copy of itself with the same headers set.

        @return: A new L{Headers}
        """
        # pretty sure this type:ignore is a mypy bug:
        # https://github.com/python/mypy/issues/18279
        return self.__class__(self._rawHeaders)  # type:ignore[arg-type]

    def hasHeader(self, name: AnyStr) -> bool:
        """
        Check for the existence of a given header.

        @param name: The name of the HTTP header to check for.

        @return: C{True} if the header exists, otherwise C{False}.
        """
        return _nameEncoder.encode(name) in self._rawHeaders

    def removeHeader(self, name: AnyStr) -> None:
        """
        Remove the named header from this header object.

        @param name: The name of the HTTP header to remove.

        @return: L{None}
        """
        self._rawHeaders.pop(_nameEncoder.encode(name), None)

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
        _name = _nameEncoder.encode(name)
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
        self._rawHeaders.setdefault(_nameEncoder.encode(name), []).append(
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
        encodedName = _nameEncoder.encode(name)
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


class _NameEncoder:
    """
    C{_NameEncoder} converts HTTP header names to L{bytes} and canonicalizies
    their capitalization.

    @cvar _caseMappings: A L{dict} that maps conventionally-capitalized
        header names to their canonicalized representation, for headers with
        unconventional capitalization.

    @cvar _canonicalHeaderCache: A L{dict} that maps header names to their
        canonicalized representation.
    """

    __slots__ = ("_canonicalHeaderCache",)
    _canonicalHeaderCache: Dict[Union[bytes, str], bytes]

    _caseMappings: ClassVar[Dict[bytes, bytes]] = {
        b"Content-Md5": b"Content-MD5",
        b"Dnt": b"DNT",
        b"Etag": b"ETag",
        b"P3p": b"P3P",
        b"Te": b"TE",
        b"Www-Authenticate": b"WWW-Authenticate",
        b"X-Xss-Protection": b"X-XSS-Protection",
    }

    _MAX_CACHED_HEADERS: ClassVar[int] = 10_000

    def __init__(self):
        self._canonicalHeaderCache = {}

    def encode(self, name: Union[str, bytes]) -> bytes:
        """
        Encode the name of a header (eg 'Content-Type') to an ISO-8859-1
        bytestring if required. It will be canonicalized to Http-Header-Case.

        @raises InvalidHeaderName:
            If the header name contains invalid characters like whitespace
            or NUL.

        @param name: An HTTP header name

        @return: C{name}, encoded if required, in Header-Case
        """
        if canonicalName := self._canonicalHeaderCache.get(name):
            return canonicalName

        bytes_name = name.encode("iso-8859-1") if isinstance(name, str) else name

        if not _istoken(bytes_name):
            raise InvalidHeaderName(bytes_name)

        result = b"-".join([word.capitalize() for word in bytes_name.split(b"-")])

        # Some headers have special capitalization:
        if result in self._caseMappings:
            result = self._caseMappings[result]

        # In general, we should only see a very small number of header
        # variations in the real world, so caching them is fine. However, an
        # attacker could generate infinite header variations to fill up RAM, so
        # we cap how many we cache. The performance degradation from lack of
        # caching won't be that bad, and legit traffic won't hit it.
        if len(self._canonicalHeaderCache) < self._MAX_CACHED_HEADERS:
            self._canonicalHeaderCache[name] = result

        return result


_nameEncoder = _NameEncoder()
"""
The global name encoder.
"""


__all__ = ["Headers"]
