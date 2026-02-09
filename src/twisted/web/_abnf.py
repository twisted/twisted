# -*- test-case-name: twisted.web.test.test_abnf -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tools for pedantically processing the HTTP protocol.
"""


def _istoken(b: bytes) -> bool:
    """
    Is the string a token per RFC 9110 section 5.6.2?
    """
    for c in b:
        if c not in (
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"  # ALPHA
            b"0123456789"  # DIGIT
            b"!#$%&'*+-.^_`|~"
        ):
            return False
    return b != b""


def _decint(data: bytes) -> int:
    """
    Parse a decimal integer of the form C{1*DIGIT}, i.e. consisting only of
    decimal digits. The integer may be embedded in whitespace (space and
    horizontal tab). This differs from the built-in L{int()} function by
    disallowing a leading C{+} character and various forms of whitespace
    (note that we sanitize linear whitespace in header values in
    L{twisted.web.http_headers.Headers}).

    @param data: Value to parse.

    @returns: A non-negative integer.

    @raises ValueError: When I{value} contains non-decimal characters.
    """
    data = data.strip(b" \t")
    if not data.isdigit():
        raise ValueError(f"Value contains non-decimal digits: {data!r}")
    return int(data)


def _ishexdigits(b: bytes) -> bool:
    """
    Is the string case-insensitively hexidecimal?

    It must be composed of one or more characters in the ranges a-f, A-F
    and 0-9.
    """
    for c in b:
        if c not in b"0123456789abcdefABCDEF":
            return False
    return b != b""


def _hexint(b: bytes) -> int:
    """
    Decode a hexadecimal integer.

    Unlike L{int(b, 16)}, this raises L{ValueError} when the integer has
    a prefix like C{b'0x'}, C{b'+'}, or C{b'-'}, which is desirable when
    parsing network protocols.
    """
    if not _ishexdigits(b):
        raise ValueError(b)
    return int(b, 16)
