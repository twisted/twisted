"""
Benchmarks for L{twisted.internet.abstract.FileDescriptor}.
"""

from typing import Any

import pytest

from twisted.internet.abstract import FileDescriptor
from twisted.internet.testing import MemoryReactor


class BufferedFileDescriptor(FileDescriptor):
    """
    A connected L{FileDescriptor} with no-op reactor integration.
    """

    connected = True

    def __init__(self) -> None:
        FileDescriptor.__init__(self, reactor=MemoryReactor())

    def startWriting(self) -> None:
        """
        No reactor is used, so this function is no-op
        """

    # No-op
    stopWriting = startWriting

    def writeSomeData(self, data: bytes) -> int:
        """
        Consume all buffered data
        """

        # There is some cost with len() but should be constant between two benchmarks.
        return len(data)


def mixedSmallChunks() -> list[bytes]:
    """
    Build a sequence with many small chunks of varied lengths.
    """
    sequence = [b"prefix", b":", b" "]
    for index in range(24):
        sequence.extend((b"name-%d" % (index,), b"=", b"value", b";"))
    sequence.append(b"suffix")
    return sequence


SEQUENCES: dict[str, list[bytes]] = {
    "1x8192": [b"x" * 8192],
    "100x1": [b"x"] * 100,
    "mixed-small": mixedSmallChunks(),
}


WRITE_DATA = b"x" * 8192
DO_WRITE_DATA = b"x" * (32 * 1024)


def test_fileDescriptor_write(benchmark: Any) -> None:
    """
    Benchmark writing 8KB with L{FileDescriptor.write}.
    """

    def setup():
        return (BufferedFileDescriptor(), WRITE_DATA), {}

    def teardown(descriptor: BufferedFileDescriptor, data: bytes) -> None:
        # Verify state of buffer and counter
        assert descriptor._tempDataBuffer == [data]
        assert descriptor._tempDataLen == len(data)

    benchmark.pedantic(
        BufferedFileDescriptor.write,
        setup=setup,
        teardown=teardown,
        rounds=100,
        iterations=1,
    )


@pytest.mark.parametrize("chunks", SEQUENCES.values(), ids=SEQUENCES)
def test_fileDescriptor_writeSequence(benchmark: Any, chunks: list[bytes]) -> None:
    """
    Benchmark buffering a sequence with L{FileDescriptor.writeSequence}.
    """

    def setup():
        return (BufferedFileDescriptor(), chunks), {}

    def teardown(descriptor: BufferedFileDescriptor, data: list[bytes]) -> None:
        assert descriptor._tempDataBuffer == data
        assert descriptor._tempDataLen == sum(map(len, data))

    benchmark.pedantic(
        BufferedFileDescriptor.writeSequence,
        setup=setup,
        teardown=teardown,
        rounds=100,
        iterations=1,
    )


def test_fileDescriptor_doWrite(benchmark: Any) -> None:
    """
    Benchmark writing 32KB with L{FileDescriptor.doWrite}.
    """

    def setup():
        descriptor = BufferedFileDescriptor()
        assert descriptor.writeSomeData(b"") == 0
        descriptor.write(DO_WRITE_DATA)
        return (descriptor,), {}

    def teardown(descriptor: BufferedFileDescriptor) -> None:
        # Verify state of buffer and counter
        assert descriptor._tempDataBuffer == []
        assert descriptor._tempDataLen == 0
        assert descriptor.dataBuffer == b""
        assert descriptor.offset == 0

    benchmark.pedantic(
        BufferedFileDescriptor.doWrite,
        setup=setup,
        teardown=teardown,
        rounds=100,
        iterations=1,
    )
