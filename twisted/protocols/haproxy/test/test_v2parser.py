# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.protocols.haproxy.V2Parser}.
"""

from twisted.trial import unittest
from twisted.internet import address

from .. import _exc
from .. import _v2parser


class V2ParserTests(unittest.TestCase):
    """
    Test L{twisted.protocols.haproxy.V2Parser} behaviour.
    """

    def _makeHeaderIPv6(
            self,
            sig=None,
            verCom=None,
            famProto=None,
            addrLength=None,
            addrs=None,
            ports=None,
    ):
        """
        Construct a version 2 header with custom bytes.
        """
        sig = sig or b'\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A'
        # V2 PROXY
        verCom = verCom or b'\x21'
        # AF_INET6/STREAM
        famProto = famProto or b'\x21'
        # 16 bytes for 2 IPv6 addresses and two ports
        addrLength = addrLength or b'\x00\x24'
        # ::1 for source and destination
        addrs = addrs or ((b'\x00' * 15) + b'\x01') * 2
        # 8080 for source 8888 for destination
        ports = ports or b'\x1F\x90\x22\xB8'
        return sig + verCom + famProto + addrLength + addrs + ports


    def _makeHeaderIPv4(
            self,
            sig=None,
            verCom=None,
            famProto=None,
            addrLength=None,
            addrs=None,
            ports=None,
    ):
        """
        Construct a version 2 header with custom bytes.
        """
        sig = sig or b'\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A'
        # V2 PROXY
        verCom = verCom or b'\x21'
        # AF_INET/STREAM
        famProto = famProto or b'\x11'
        # 12 bytes for 2 IPv4 addresses and two ports
        addrLength = addrLength or b'\x00\x0C'
        # 127.0.0.1 for source and destination
        addrs = addrs or b'\x7F\x00\x00\x01\x7F\x00\x00\x01'
        # 8080 for source 8888 for destination
        ports = ports or b'\x1F\x90\x22\xB8'
        return sig + verCom + famProto + addrLength + addrs + ports


    def _makeHeaderUnix(
            self,
            sig=None,
            verCom=None,
            famProto=None,
            addrLength=None,
            addrs=None,
    ):
        """
        Construct a version 2 header with custom bytes.
        """
        sig = sig or b'\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A'
        # V2 PROXY
        verCom = verCom or b'\x21'
        # AF_UNIX/STREAM
        famProto = famProto or b'\x31'
        # 108 bytes for 2 null terminated paths
        addrLength = addrLength or b'\x00\xD8'
        # /home/tests/mysockets/sock for source and destination paths
        defaultAddrs = (
            b'\x2F\x68\x6F\x6D\x65\x2F\x74\x65\x73\x74\x73\x2F\x6D\x79\x73\x6F'
            b'\x63\x6B\x65\x74\x73\x2F\x73\x6F\x63\x6B' + (b'\x00' * 82)
        ) * 2
        addrs = addrs or defaultAddrs
        return sig + verCom + famProto + addrLength + addrs


    def test_happyPathIPv4(self):
        """
        Test if a well formed IPv4 header is parsed without error.
        """
        header = self._makeHeaderIPv4()
        self.assertTrue(_v2parser.V2Parser.parse(header))


    def test_happyPathIPv6(self):
        """
        Test if a well formed IPv6 header is parsed without error.
        """
        header = self._makeHeaderIPv6()
        self.assertTrue(_v2parser.V2Parser.parse(header))


    def test_happyPathUnix(self):
        """
        Test if a well formed UNIX header is parsed without error.
        """
        header = self._makeHeaderUnix()
        self.assertTrue(_v2parser.V2Parser.parse(header))


    def test_invalidSignature(self):
        """
        Test if an invalid signature block raises InvalidProxyError.
        """
        header = self._makeHeaderIPv4(sig=b'\x00'*12)
        self.assertRaises(
            _exc.InvalidProxyHeader,
            _v2parser.V2Parser.parse,
            header,
        )


    def test_invalidVersion(self):
        """
        Test if an invalid version raises InvalidProxyError.
        """
        header = self._makeHeaderIPv4(verCom=b'\x11')
        self.assertRaises(
            _exc.InvalidProxyHeader,
            _v2parser.V2Parser.parse,
            header,
        )


    def test_invalidCommand(self):
        """
        Test if an invalid command raises InvalidProxyError.
        """
        header = self._makeHeaderIPv4(verCom=b'\x23')
        self.assertRaises(
            _exc.InvalidProxyHeader,
            _v2parser.V2Parser.parse,
            header,
        )


    def test_localCommandIpv4(self):
        """
        Test that local does not return endpoint data for IPv4 connections.
        """
        header = self._makeHeaderIPv4(verCom=b'\x20')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_localCommandIpv6(self):
        """
        Test that local does not return endpoint data for IPv6 connections.
        """
        header = self._makeHeaderIPv6(verCom=b'\x20')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_localCommandUnix(self):
        """
        Test that local does not return endpoint data for UNIX connections.
        """
        header = self._makeHeaderUnix(verCom=b'\x20')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_proxyCommandIpv4(self):
        """
        Test that proxy returns endpoint data for IPv4 connections.
        """
        header = self._makeHeaderIPv4(verCom=b'\x21')
        info = _v2parser.V2Parser.parse(header)
        self.assertTrue(info.source)
        self.assertTrue(isinstance(info.source, address.IPv4Address))
        self.assertTrue(info.destination)
        self.assertTrue(isinstance(info.destination, address.IPv4Address))


    def test_proxyCommandIpv6(self):
        """
        Test that proxy returns endpoint data for IPv6 connections.
        """
        header = self._makeHeaderIPv6(verCom=b'\x21')
        info = _v2parser.V2Parser.parse(header)
        self.assertTrue(info.source)
        self.assertTrue(isinstance(info.source, address.IPv6Address))
        self.assertTrue(info.destination)
        self.assertTrue(isinstance(info.destination, address.IPv6Address))


    def test_proxyCommandUnix(self):
        """
        Test that proxy returns endpoint data for UNIX connections.
        """
        header = self._makeHeaderUnix(verCom=b'\x21')
        info = _v2parser.V2Parser.parse(header)
        self.assertTrue(info.source)
        self.assertTrue(isinstance(info.source, address.UNIXAddress))
        self.assertTrue(info.destination)
        self.assertTrue(isinstance(info.destination, address.UNIXAddress))


    def test_unspecFamilyIpv4(self):
        """
        Test that UNSPEC does not return endpoint data for IPv4 connections.
        """
        header = self._makeHeaderIPv4(famProto=b'\x01')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_unspecFamilyIpv6(self):
        """
        Test that UNSPEC does not return endpoint data for IPv6 connections.
        """
        header = self._makeHeaderIPv6(famProto=b'\x01')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_unspecFamilyUnix(self):
        """
        Test that UNSPEC does not return endpoint data for UNIX connections.
        """
        header = self._makeHeaderUnix(famProto=b'\x01')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_unspecProtoIpv4(self):
        """
        Test that UNSPEC does not return endpoint data for IPv4 connections.
        """
        header = self._makeHeaderIPv4(famProto=b'\x10')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_unspecProtoIpv6(self):
        """
        Test that UNSPEC does not return endpoint data for IPv6 connections.
        """
        header = self._makeHeaderIPv6(famProto=b'\x20')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_unspecProtoUnix(self):
        """
        Test that UNSPEC does not return endpoint data for UNIX connections.
        """
        header = self._makeHeaderUnix(famProto=b'\x30')
        info = _v2parser.V2Parser.parse(header)
        self.assertFalse(info.source)
        self.assertFalse(info.destination)


    def test_overflowIpv4(self):
        """
        Test that overflow bits are preserved during feed parsing for IPv4.
        """
        testValue = b'TEST DATA\r\n\r\nTEST DATA'
        header = self._makeHeaderIPv4() + testValue
        parser = _v2parser.V2Parser()
        info, overflow = parser.feed(header)
        self.assertTrue(info)
        self.assertEqual(overflow, testValue)


    def test_overflowIpv6(self):
        """
        Test that overflow bits are preserved during feed parsing for IPv6.
        """
        testValue = b'TEST DATA\r\n\r\nTEST DATA'
        header = self._makeHeaderIPv6() + testValue
        parser = _v2parser.V2Parser()
        info, overflow = parser.feed(header)
        self.assertTrue(info)
        self.assertEqual(overflow, testValue)


    def test_overflowUnix(self):
        """
        Test that overflow bits are preserved during feed parsing for Unix.
        """
        testValue = b'TEST DATA\r\n\r\nTEST DATA'
        header = self._makeHeaderUnix() + testValue
        parser = _v2parser.V2Parser()
        info, overflow = parser.feed(header)
        self.assertTrue(info)
        self.assertEqual(overflow, testValue)
