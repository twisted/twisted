# -*- test-case-name: twisted.conch.test.test_common -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Backported functions from Cryptography to support older versions.

These functions can be obtained from C{cryptography.utils} instead, from
version 1.1 onwards.
"""
from __future__ import absolute_import, division
from binascii import unhexlify


if hasattr(int, "from_bytes"):
    intFromBytes = int.from_bytes
else:
    def intFromBytes(data, byteorder, signed=False):
        assert byteorder == 'big'
        assert not signed

        # call bytes() on data to allow the use of bytearrays
        return int(bytes(data).encode('hex'), 16)


if hasattr(int, "to_bytes"):
    def intToBytes(integer, length=None):
        return integer.to_bytes(
            length or (integer.bit_length() + 7) // 8 or 1, 'big'
        )
else:
    def intToBytes(integer, length=None):
        hex_string = '%x' % integer
        if length is None:
            n = len(hex_string)
        else:
            n = length * 2
        return unhexlify(hex_string.zfill(n + (n & 1)))
