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
        self.writeLimit = self.SEND_LIMIT

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

        # To simulate a partial write, don't return values larger
        # than the write limit. Otherwise all data is consumed.
        #
        # In the real world, the write limit here could represent
        # the buffer size of the socket in the operating system.
        return min(len(data), self.writeLimit)


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


def test_fileDescriptor_doWriteFlushBufferedWrites(benchmark: Any) -> None:
    """
    Benchmark flushing four buffered 8KB writes.
    """

    def setup():
        descriptor = BufferedFileDescriptor()
        for _ in range(4):
            # Buffer 4x 8KB chunks
            descriptor.write(WRITE_DATA)
        return (descriptor,), {}

    def teardown(descriptor: BufferedFileDescriptor) -> None:
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


def test_fileDescriptor_doWriteAppendAfterPartialWrite(benchmark: Any) -> None:
    """
    Benchmark flushing new data after an earlier partial write.
    """

    def setup():
        descriptor = BufferedFileDescriptor()
        for _ in range(4):
            # Buffer 4x 8KB chunks
            descriptor.write(WRITE_DATA)

        # Do a partial write, it writes only 8KB
        descriptor.writeLimit = len(WRITE_DATA)
        descriptor.doWrite()

        # Now buffer another chunk
        descriptor.write(WRITE_DATA)

        # Revert the limit back and run benchmark
        descriptor.writeLimit = descriptor.SEND_LIMIT
        return (descriptor,), {}

    def teardown(descriptor: BufferedFileDescriptor) -> None:
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


def test_fileDescriptor_doWriteContinuePartialWrite(benchmark: Any) -> None:
    """
    Benchmark continuing a large buffer after an earlier partial write.
    """

    def setup():
        descriptor = BufferedFileDescriptor()
        for _ in range(17):
            # Buffer 17 x 8KB chunks
            descriptor.write(WRITE_DATA)

        # Do a partial write, it writes only 8KB
        descriptor.writeLimit = len(WRITE_DATA)
        descriptor.doWrite()

        # We have 16 x 8KB = 128KB left
        descriptor.writeLimit = descriptor.SEND_LIMIT
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


def test_fileDescriptor_doWriteContinueSmallPartialWrite(benchmark: Any) -> None:
    """
    Benchmark continuing a partial write smaller than C{SEND_LIMIT}.
    """

    def setup():
        descriptor = BufferedFileDescriptor()
        for _ in range(4):
            descriptor.write(WRITE_DATA)

        # Do a partial write, it writes only 8KB
        descriptor.writeLimit = len(WRITE_DATA)
        descriptor.doWrite()

        # Now run benchmark, where we continue writing 24KB data
        # which is less than SEND_LIMIT.
        return (descriptor,), {}

    def teardown(descriptor: BufferedFileDescriptor) -> None:
        assert descriptor._tempDataBuffer == []
        assert descriptor._tempDataLen == 0
        assert len(descriptor.dataBuffer) - descriptor.offset == 2 * len(WRITE_DATA)

    benchmark.pedantic(
        BufferedFileDescriptor.doWrite,
        setup=setup,
        teardown=teardown,
        rounds=100,
        iterations=1,
    )
