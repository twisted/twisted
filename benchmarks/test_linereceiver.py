"""
Benchmarks for line parsing protocols.
"""

import pytest

from twisted.protocols.basic import LineReceiver, LineOnlyReceiver
from twisted.internet.protocol import Protocol
from twisted.test.proto_helpers import StringTransport


def deliverData(protocol: Protocol, data: bytes, chunkSize: int) -> None:
    i = 0
    while i < len(data):
        protocol.dataReceived(data[i : i + chunkSize])
        i += chunkSize


@pytest.mark.parametrize("chunkSize", [16, 64, 256, 1024])
def test_lineReceiver(benchmark, chunkSize):
    """
    Parses lines, but can in theory also parse raw data.
    """
    class MyLineReceiver(LineReceiver):
        def lineReceived(self, _):
            pass

    protocol = MyLineReceiver()
    protocol.makeConnection(StringTransport())
    data = ((b"abcde" * 10) + b"\r\n") * 1000

    benchmark(lambda: deliverData(protocol, data, chunkSize))


@pytest.mark.parametrize("chunkSize", [16, 64, 256, 1024])
def test_lineOnlyReceiver(benchmark, chunkSize):
    """
    Parses only lines.
    """
    class MyLineReceiver(LineOnlyReceiver):
        def lineReceived(self, line):
            pass

    protocol = MyLineReceiver()
    protocol.makeConnection(StringTransport())
    data = ((b"abcde" * 10) + b"\r\n") * 1000

    benchmark(lambda: deliverData(protocol, data, chunkSize))
