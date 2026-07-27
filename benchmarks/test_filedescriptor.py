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


@pytest.mark.parametrize(
    "chunks",
    SEQUENCES.values(),
    ids=SEQUENCES,
)
def test_fileDescriptor_writeSequence(
    benchmark: Any,
    chunks: list[bytes],
) -> None:
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
