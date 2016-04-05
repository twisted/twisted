# -*- test-case-name: twisted.protocols.haproxy.test.test_v2parser -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
IProxyParser implementation for version two of the PROXY protocol.
"""

import binascii
import socket
import struct

from zope.interface import implementer
from twisted.internet import address
from twisted.python import compat

from ._exceptions import (
    convertError, InvalidProxyHeader, InvalidNetworkProtocol,
    MissingAddressData
)
from . import _info
from . import _interfaces


_HIGH = 0b11110000
_LOW = 0b00001111
_UNSPECPROTO = 'UNSPEC'
_LOCALCOMMAND = 'LOCAL'
_PROXYCOMMAND = 'PROXY'

@implementer(_interfaces.IProxyParser)
class V2Parser(object):
    """
    PROXY protocol version two header parser.

    Version two of the PROXY protocol is a binary format.
    """

    PREFIX = b'\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A'
    VERSIONS = (32,)
    COMMANDS = {0: _LOCALCOMMAND, 1: _PROXYCOMMAND}
    NETFAMILIES = {
        0: socket.AF_UNSPEC,
        16: socket.AF_INET,
        32: socket.AF_INET6,
        48: socket.AF_UNIX,
    }
    NETPROTOCOLS = {
        0: _UNSPECPROTO,
        1: socket.SOCK_STREAM,
        2: socket.SOCK_DGRAM,
    }
    ADDRESSFORMATS = {
        # TCP4
        17: '!4s4s2H',
        18: '!4s4s2H',
        # TCP6
        33: '!16s16s2H',
        34: '!16s16s2H',
        # UNIX
        49: '!108s108s',
        50: '!108s108s',
    }

    def __init__(self):
        self.buffer = b''


    def feed(self, data):
        """
        Consume a chunk of data and attempt to parse it.

        @param data: A bytestring.
        @type data: bytes

        @return: A two-tuple containing, in order, a L{_interfaces.IProxyInfo}
            and any bytes fed to the parser that followed the end of the
            header.  Both of these values are None until a complete header is
            parsed.

        @raises InvalidProxyHeader: If the bytes fed to the parser create an
            invalid PROXY header.
        """
        self.buffer += data
        if len(self.buffer) < 16:
            raise InvalidProxyHeader()

        size = struct.unpack('!H', self.buffer[14:16])[0] + 16
        if len(self.buffer) < size:
            return (None, None)

        header, remaining = self.buffer[:size], self.buffer[size:]
        self.buffer = b''
        info = self.parse(header)
        return (info, remaining)


    @staticmethod
    def _bytesToIPv4(bytestring):
        """
        Convert packed 32-bit IPv4 address bytes into a dotted-quad ASCII bytes
        representation of that address.

        @param bytestring: 4 octets representing an IPv4 address.
        @type bytestring: L{bytes}

        @return: a dotted-quad notation IPv4 address.
        @rtype: L{bytes}
        """
        return b'.'.join(
            ('%i' % (ord(b),)).encode('ascii')
            for b in compat.iterbytes(bytestring)
        )


    @staticmethod
    def _bytesToIPv6(bytestring):
        """
        Convert packed 128-bit IPv6 address bytes into a colon-separated ASCII
        bytes representation of that address.

        @param bytestring: 16 octets representing an IPv6 address.
        @type bytestring: L{bytes}

        @return: a dotted-quad notation IPv6 address.
        @rtype: L{bytes}
        """
        hexString = binascii.b2a_hex(bytestring)
        return b':'.join(
            ('%x' % (int(hexString[b:b+4], 16),)).encode('ascii')
            for b in range(0, 32, 4)
        )


    @classmethod
    def parse(cls, line):
        """
        Parse a bytestring as a full PROXY protocol header.

        @param line: A bytestring that represents a valid HAProxy PROXY
            protocol version 2 header.
        @type line: bytes

        @return: A L{_interfaces.IProxyInfo} containing the
            parsed data.

        @raises InvalidProxyHeader: If the bytestring does not represent a
            valid PROXY header.
        """
        prefix = line[:12]
        addrInfo = None
        with convertError(IndexError, InvalidProxyHeader):
            # Use single value slices to ensure bytestring values are returned
            # instead of int in PY3.
            versionCommand = ord(line[12:13])
            familyProto = ord(line[13:14])

        if prefix != cls.PREFIX:
            raise InvalidProxyHeader()

        version, command = versionCommand & _HIGH, versionCommand & _LOW
        if version not in cls.VERSIONS or command not in cls.COMMANDS:
            raise InvalidProxyHeader()

        if cls.COMMANDS[command] == _LOCALCOMMAND:
            return _info.ProxyInfo(line, None, None)

        family, netproto = familyProto & _HIGH, familyProto & _LOW
        if family not in cls.NETFAMILIES or netproto not in cls.NETPROTOCOLS:
            raise InvalidNetworkProtocol()

        if (
                cls.NETFAMILIES[family] == socket.AF_UNSPEC or
                cls.NETPROTOCOLS[netproto] == _UNSPECPROTO
        ):
            return _info.ProxyInfo(line, None, None)

        addressFormat = cls.ADDRESSFORMATS[familyProto]
        addrInfo = line[16:16+struct.calcsize(addressFormat)]
        if cls.NETFAMILIES[family] == socket.AF_UNIX:
            with convertError(struct.error, MissingAddressData):
                source, dest = struct.unpack(addressFormat, addrInfo)
            return _info.ProxyInfo(
                line,
                address.UNIXAddress(source.rstrip(b'\x00')),
                address.UNIXAddress(dest.rstrip(b'\x00')),
            )

        addrType = 'TCP'
        if cls.NETPROTOCOLS[netproto] == socket.SOCK_DGRAM:
            addrType = 'UDP'
        addrCls = address.IPv4Address
        addrParser = cls._bytesToIPv4
        if cls.NETFAMILIES[family] == socket.AF_INET6:
            addrCls = address.IPv6Address
            addrParser = cls._bytesToIPv6

        with convertError(struct.error, MissingAddressData):
            info = struct.unpack(addressFormat, addrInfo)
            source, dest, sPort, dPort = info

        return _info.ProxyInfo(
            line,
            addrCls(addrType, addrParser(source), sPort),
            addrCls(addrType, addrParser(dest), dPort),
        )
