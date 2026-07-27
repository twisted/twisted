"""
Benchmarks for L{twisted.internet.abstract.FileDescriptor}.
"""

from collections.abc import Callable, Sequence
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
        pass


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
    "4x1024": [b"x" * 1024] * 4,
    "100x1": [b"x"] * 100,
    "mixed-small": mixedSmallChunks(),
}


@pytest.mark.parametrize(
    "chunks",
    SEQUENCES.values(),
    ids=SEQUENCES,
)
@pytest.mark.parametrize(
    "sequenceFactory",
    [list, tuple],
    ids=["list", "tuple"],
)
def test_fileDescriptor_writeSequence(
    benchmark: Any,
    chunks: list[bytes],
    sequenceFactory: Callable[[list[bytes]], Sequence[bytes]],
) -> None:
    """
    Benchmark buffering a sequence with L{FileDescriptor.writeSequence}.
    """
    sequence = sequenceFactory(chunks)

    def setup():
        return (BufferedFileDescriptor(), sequence), {}

    def teardown(descriptor: BufferedFileDescriptor, data: Sequence[bytes]) -> None:
        assert descriptor._tempDataBuffer == list(data)
        assert descriptor._tempDataLen == sum(map(len, data))

    benchmark.pedantic(
        BufferedFileDescriptor.writeSequence,
        setup=setup,
        teardown=teardown,
        rounds=100,
        iterations=1,
    )
