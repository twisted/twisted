# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.abstract}, a collection of APIs for implementing
reactors.
"""
from __future__ import annotations

from typing import Union

from hypothesis import example, given, strategies as st

from twisted.internet.abstract import FileDescriptor, isIPv6Address
from twisted.trial.unittest import SynchronousTestCase
from .test_tcp import _FakeFDSetReactor


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


class TrackingFileDescriptor(FileDescriptor):
    """
    Write a limited amount, and track what gets written.
    """

    # Annoying implementation details we need to make it work:
    connected = True
    _writeDisconnected = False

    def __init__(
        self, operations: list[Union[int, bytes]], written: list[bytes], send_limit: int
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
    def test_writeBuffering(self, operations: list[Union[bytes, int]]) -> None:
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
