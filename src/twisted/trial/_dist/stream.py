"""
Buffer string streams
"""

from itertools import count
from typing import Dict, Iterator, List, TypeVar

from attrs import Factory, define

from twisted.protocols.amp import AMP, Command, Integer, Unicode

T = TypeVar("T")


class StreamOpen(Command):
    """
    Open a new stream.
    """

    response = [(b"streamId", Integer())]


class StreamWrite(Command):
    """
    Write a chunk of data to a stream.
    """

    arguments = [
        (b"streamId", Integer()),
        (b"data", Unicode()),
    ]


@define
class StreamReceiver:
    """
    Buffering de-multiplexing string stream receiver.
    """

    _counter: Iterator[int] = count()
    _streams: Dict[int, List[str]] = Factory(dict)

    def open(self) -> int:
        """
        Open a new stream and return its unique identifier.
        """
        newId = next(self._counter)
        self._streams[newId] = []
        return newId

    def write(self, streamId: int, chunk: str) -> None:
        """
        Write to an open stream using its unique identifier.

        :raise KeyError: If there is no such open stream.
        """
        self._streams[streamId].append(chunk)

    def close(self, streamId: int) -> List[str]:
        """
        Close an open stream and return all of its contents.

        :raise KeyError: If there is no such open stream.
        """
        return self._streams.pop(streamId)


def chunk(data: str, chunkSize: int) -> Iterator[str]:
    """
    Break a string into pieces of no more than ``chunkSize`` length.

    :param data: The string.

    :param chunkSize: The maximum length of the resulting pieces.  All pieces
        except possibly the last will be this length.

    :return: The pieces.
    """
    pos = 0
    while pos < len(data):
        yield data[pos : pos + chunkSize]
        pos += chunkSize


async def stream(amp: AMP, chunks: Iterator[str]) -> int:
    """
    Send the given stream chunks, one by one, over the given connection.

    The chunks are sent using L{StreamWrite} over a stream opened using
    L{StreamOpen}.

    :return: The identifier of the stream over which the chunks were sent.
    """
    streamId = (await amp.callRemote(StreamOpen))["streamId"]

    for oneChunk in chunks:
        await amp.callRemote(StreamWrite, streamId=streamId, data=oneChunk)
    return streamId  # type: ignore[no-any-return]
