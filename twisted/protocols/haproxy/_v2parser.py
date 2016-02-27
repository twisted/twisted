# -*- test-case-name: twisted.protocols.haproxy.test.test_v2parser -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
IProxyParser implementation for version two of the PROXY protocol.
"""

import binascii
import struct
import zope.interface

from twisted.internet import address

from . import _exc
from . import _info
from . import _interfaces


_HIGH = 0b11110000
_LOW = 0b00001111



class V2Parser(object):
    """
    PROXY protocol version two header parser.

    Version two of the PROXY protocol is a binary format.
    """

    zope.interface.implements(_interfaces.IProxyParser)

    PREFIX = b'\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A'
    VERSIONS = (32,)
    COMMANDS = {0: 'LOCAL', 1: 'PROXY'}
    NETFAMILIES = {
        0: 'AF_UNSPEC',
        16: 'AF_INET',
        32: 'AF_INET6',
        48: 'AF_UNIX',
    }
    NETPROTOCOLS = {
        0: 'UNSPEC',
        1: 'STREAM',
        2: 'DGRAM',
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

        @return: A two-tuple containing, in order, a
            L{twisted.protocols.haproxy.IProxyInfo} and any bytes fed to the
            parser that followed the end of the header. Both of these values
            are None until a complete header is parsed.

        @raises InvalidProxyHeader: If the bytes fed to the parser create an
            invalid PROXY header.
        """
        self.buffer += data
        if len(self.buffer) < 16:
            return (None, None)

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
        Convert a bytestring to an IPv4 representation.
        """
        return '.'.join(str(ord(b)) for b in bytestring)


    @staticmethod
    def _bytesToIPv6(bytestring):
        """
        Convert a bytestring to an IPv6 representation.
        """
        hexString = binascii.b2a_hex(bytestring)
        return ':'.join(
            '%x' % (int(hexString[b:b+4], 16),) for b in range(0, 32, 4)
        )


    @classmethod
    def parse(cls, line):
        """
        Parse a bytestring as a full PROXY protocol header.

        @param line: A bytestring that represents a valid HAProxy PROXY
            protocol version 2 header.
        @type line: bytes

        @return: A L{twisted.protocols.haproxy.IProxyInfo} containing the
            parsed data.

        @raises InvalidProxyHeader: If the bytestring does not represent a
            valid PROXY header.
        """
        prefix = line[:12]
        addrInfo = None
        with _exc.convertError(IndexError, _exc.InvalidProxyHeader):
            versionCommand = ord(line[12])
            familyProto = ord(line[13])

        if prefix != cls.PREFIX:
            raise _exc.InvalidProxyHeader()

        version, command = versionCommand & _HIGH, versionCommand & _LOW
        if version not in cls.VERSIONS or command not in cls.COMMANDS:
            raise _exc.InvalidProxyHeader()

        if cls.COMMANDS[command] == 'LOCAL':
            return _info.ProxyInfo(line, None, None)

        family, netproto = familyProto & _HIGH, familyProto & _LOW
        if family not in cls.NETFAMILIES or netproto not in cls.NETPROTOCOLS:
            raise _exc.InvalidNetworkProtocol()

        if (
                cls.NETFAMILIES[family] == 'AF_UNSPEC' or
                cls.NETPROTOCOLS[netproto] == 'UNSPEC'
        ):
            return _info.ProxyInfo(line, None, None)

        addressFormat = cls.ADDRESSFORMATS[familyProto]
        addrInfo = line[16:16+struct.calcsize(addressFormat)]
        if cls.NETFAMILIES[family] == 'AF_UNIX':
            with _exc.convertError(struct.error, _exc.MissingAddressData):
                source, dest = struct.unpack(addressFormat, addrInfo)
            return _info.ProxyInfo(
                line,
                address.UNIXAddress(source.rstrip(b'\x00')),
                address.UNIXAddress(dest.rstrip(b'\x00')),
            )

        addrType = 'TCP' if cls.NETPROTOCOLS[netproto] == 'STREAM' else 'UDP'
        addrCls = address.IPv4Address
        addrParser = cls._bytesToIPv4
        if cls.NETFAMILIES[family] == 'AF_INET6':
            addrCls = address.IPv6Address
            addrParser = cls._bytesToIPv6

        with _exc.convertError(struct.error, _exc.MissingAddressData):
            info = struct.unpack(addressFormat, addrInfo)
            source, dest, sPort, dPort = info

        return _info.ProxyInfo(
            line,
            addrCls(addrType, addrParser(source), sPort),
            addrCls(addrType, addrParser(dest), dPort),
        )
