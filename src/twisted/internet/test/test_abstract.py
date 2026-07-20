# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.abstract}, a collection of APIs for implementing
reactors.
"""
from __future__ import annotations

from io import UnsupportedOperation
from socket import AF_IPX

from hypothesis import example, given, strategies as st

from twisted.internet.abstract import FileDescriptor, isIPAddress, isIPv6Address
from twisted.trial.unittest import SynchronousTestCase
from .test_tcp import _FakeFDSetReactor


class AddressTests(SynchronousTestCase):
    """
    Tests for address-related functionality.
    """

    def test_decimalDotted(self) -> None:
        """
        L{isIPAddress} should return C{True} for any decimal dotted
        representation of an IPv4 address.
        """
        self.assertTrue(isIPAddress("0.1.2.3"))
        self.assertTrue(isIPAddress("252.253.254.255"))

    def test_shortDecimalDotted(self) -> None:
        """
        L{isIPAddress} should return C{False} for a dotted decimal
        representation with fewer or more than four octets.
        """
        self.assertFalse(isIPAddress("0"))
        self.assertFalse(isIPAddress("0.1"))
        self.assertFalse(isIPAddress("0.1.2"))
        self.assertFalse(isIPAddress("0.1.2.3.4"))

    def test_invalidLetters(self) -> None:
        """
        L{isIPAddress} should return C{False} for any non-decimal dotted
        representation including letters.
        """
        self.assertFalse(isIPAddress("a.2.3.4"))
        self.assertFalse(isIPAddress("1.b.3.4"))

    def test_invalidPunctuation(self) -> None:
        """
        L{isIPAddress} should return C{False} for a string containing
        strange punctuation.
        """
        self.assertFalse(isIPAddress(","))
        self.assertFalse(isIPAddress("1,2"))
        self.assertFalse(isIPAddress("1,2,3"))
        self.assertFalse(isIPAddress("1.,.3,4"))

    def test_emptyString(self) -> None:
        """
        L{isIPAddress} should return C{False} for the empty string.
        """
        self.assertFalse(isIPAddress(""))

    def test_invalidNegative(self) -> None:
        """
        L{isIPAddress} should return C{False} for negative decimal values.
        """
        self.assertFalse(isIPAddress("-1"))
        self.assertFalse(isIPAddress("1.-2"))
        self.assertFalse(isIPAddress("1.2.-3"))
        self.assertFalse(isIPAddress("1.2.-3.4"))

    def test_invalidPositive(self) -> None:
        """
        L{isIPAddress} should return C{False} for a string containing
        positive decimal values greater than 255.
        """
        self.assertFalse(isIPAddress("256.0.0.0"))
        self.assertFalse(isIPAddress("0.256.0.0"))
        self.assertFalse(isIPAddress("0.0.256.0"))
        self.assertFalse(isIPAddress("0.0.0.256"))
        self.assertFalse(isIPAddress("256.256.256.256"))

    def test_unicodeAndBytes(self) -> None:
        """
        L{isIPAddress} evaluates ASCII-encoded bytes as well as text.
        """
        # we test passing bytes but don't support bytes in the type annotation
        self.assertFalse(isIPAddress(b"256.0.0.0"))  # type: ignore[arg-type]
        self.assertFalse(isIPAddress("256.0.0.0"))
        self.assertTrue(isIPAddress(b"252.253.254.255"))  # type: ignore[arg-type]
        self.assertTrue(isIPAddress("252.253.254.255"))

    def test_nonIPAddressFamily(self) -> None:
        """
        All address families other than C{AF_INET} and C{AF_INET6} result in a
        L{ValueError} being raised.
        """
        self.assertRaises(ValueError, isIPAddress, b"anything", AF_IPX)

    def test_nonASCII(self) -> None:
        """
        All IP addresses must be encodable as ASCII; non-ASCII should result in
        a L{False} result.
        """
        # we test passing bytes but don't support bytes in the type annotation
        self.assertFalse(isIPAddress(b"\xff.notascii"))  # type: ignore[arg-type]
        self.assertFalse(isIPAddress("\u4321.notascii"))


class IPv6AddressTests(SynchronousTestCase):
    """
    Tests for L{isIPv6Address}, a function for determining if a particular
    string is an IPv6 address literal.
    """

    def test_empty(self) -> None:
        """
        The empty string is not an IPv6 address literal.
        """
        self.assertFalse(isIPv6Address(""))

    def test_colon(self) -> None:
        """
        A single C{":"} is not an IPv6 address literal.
        """
        self.assertFalse(isIPv6Address(":"))

    def test_loopback(self) -> None:
        """
        C{"::1"} is the IPv6 loopback address literal.
        """
        self.assertTrue(isIPv6Address("::1"))

    def test_scopeID(self) -> None:
        """
        An otherwise valid IPv6 address literal may also include a C{"%"}
        followed by an arbitrary scope identifier.
        """
        self.assertTrue(isIPv6Address("fe80::1%eth0"))
        self.assertTrue(isIPv6Address("fe80::2%1"))
        self.assertTrue(isIPv6Address("fe80::3%en2"))

    def test_invalidWithScopeID(self) -> None:
        """
        An otherwise invalid IPv6 address literal is still invalid with a
        trailing scope identifier.
        """
        self.assertFalse(isIPv6Address("%eth0"))
        self.assertFalse(isIPv6Address(":%eth0"))
        self.assertFalse(isIPv6Address("hello%eth0"))

    def test_unicodeAndBytes(self) -> None:
        """
        L{isIPv6Address} evaluates ASCII-encoded bytes as well as text.
        """
        # the type annotation only supports str, but bytes is supported at
        # runtime
        self.assertTrue(isIPv6Address(b"fe80::2%1"))  # type: ignore[arg-type]
        self.assertTrue(isIPv6Address("fe80::2%1"))
        self.assertFalse(isIPv6Address("\u4321"))
        self.assertFalse(isIPv6Address("hello%eth0"))
        self.assertFalse(isIPv6Address(b"hello%eth0"))  # type: ignore[arg-type]


class FileDescriptorTests(SynchronousTestCase):
    """
    Tests for L{FileDescriptor} class.
    """

    def test_fileno(self) -> None:
        """
        It raises L{UnsupportedOperation} since by default no file descriptor
        is associated with the abstract implementation.
        """
        fd = FileDescriptor(_FakeFDSetReactor())
        self.assertRaises(UnsupportedOperation, fd.fileno)


class TrackingFileDescriptor(FileDescriptor):
    """
    Write a limited amount, and track what gets written.
    """

    # Annoying implementation details we need to make it work:
    connected = True
    _writeDisconnected = False

    def __init__(
        self, operations: list[int | bytes], written: list[bytes], send_limit: int
    ):
        self.operations = operations
        self.written = written
        self.SEND_LIMIT = send_limit
        FileDescriptor.__init__(self, _FakeFDSetReactor())

    def writeSomeData(self, data: bytes) -> int:
        toWrite = self.operations.pop(0)
        assert isinstance(toWrite, int)
        toWrite = min(toWrite, len(data))
        self.written.append(data[:toWrite])
        return toWrite


class WriteBufferingTests(SynchronousTestCase):
    """
    Tests for the complex logic in the L{FileDescriptor} class.
    """

    @given(
        operations=st.lists(
            st.one_of(
                st.binary(min_size=1, max_size=10),
                st.integers(min_value=0, max_value=10),
            ),
            min_size=3,
            max_size=30,
        )
    )
    # This catches a bug that was introduced by a performance refactoring:
    @example(operations=[b"abcdef", 0, b"g"])
    def test_writeBuffering(self, operations: list[bytes | int]) -> None:
        """
        A sequence of C{write()} and C{doWrite()} will eventually write all the
        data correctly and in order.

        @param operations: A list of C{bytes} (indicating a C{write()}) or
            C{int} (indicating C{doWrite()} with the integer being how much
            C{writeSomeData()} writeSomeData will successfully write).
        """
        expected = b"".join(op for op in operations if isinstance(op, bytes))
        written: list[bytes] = []

        # Send at most 5 bytes per call to writeSomeData(); default is much
        # higher, of course, but made it smaller so we can have faster
        # tests.
        SEND_LIMIT = 5
        fd = TrackingFileDescriptor(operations, written, SEND_LIMIT)

        # Make sure we flush whatever is left at the end:
        operations += [SEND_LIMIT * 2] * (1 + len(expected) // SEND_LIMIT)

        while operations:
            if isinstance(operations[0], bytes):
                fd.write(operations.pop(0))  # type: ignore[arg-type]
            else:
                fd.doWrite()

        result = b"".join(written)
        self.assertEqual(expected, result)
