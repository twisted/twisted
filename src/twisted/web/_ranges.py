# -*- test-case-name: twisted.web.test.test_static -*-
"""
Implementations of Range: header request logic for L{twisted.web.static}.
"""

from __future__ import annotations

from typing import IO, NoReturn

from zope.interface import implementer

from twisted.internet import abstract, interfaces
from twisted.web import http

ranges = list[tuple[int, int] | tuple[None, int] | tuple[int, None]]


def _parseRangeHeader(rangeHeader: bytes) -> ranges:
    """
    Parse the value of a Range header into (start, stop) pairs.

    In a given pair, either of start or stop can be None, signifying that
    no value was provided, but not both.

    @return: A list C{[(start, stop)]} of pairs of length at least one.

    @raise ValueError: if the header is syntactically invalid or if the
        Bytes-Unit is anything other than "bytes'.
    """
    try:
        kind, value = rangeHeader.split(b"=", 1)
    except ValueError:
        raise ValueError("Missing '=' separator")
    kind = kind.strip()
    if kind != b"bytes":
        raise ValueError(f"Unsupported Bytes-Unit: {kind!r}")
    unparsedRanges = list(filter(None, map(bytes.strip, value.split(b","))))
    parsedRanges: ranges = []

    def invalid() -> NoReturn:
        raise ValueError(f"Invalid Byte-Range: {byteRange!r}")

    for byteRange in unparsedRanges:
        start: int | None = None
        end: int | None = None
        try:
            startBytes, endBytes = byteRange.split(b"-", 1)
        except ValueError:
            invalid()
        if startBytes:
            try:
                start = int(startBytes)
            except ValueError:
                invalid()
        if endBytes:
            try:
                end = int(endBytes)
            except ValueError:
                invalid()
        match (start, end):
            case (None, int(validEnd)):
                parsedRanges.append((None, validEnd))
            case (int(validStart), None):
                parsedRanges.append((validStart, None))
            case (int(validStart), int(validEnd)):
                if start >= end:
                    invalid()
                parsedRanges.append((validStart, validEnd))
            case _:  # (None, None)
                invalid()
    return parsedRanges


@implementer(interfaces.IPullProducer)
class StaticProducer:
    """
    Superclass for classes that implement the business of producing.

    @ivar request: The L{IRequest} to write the contents of the file to.

    @ivar fileObject: The file the contents of which to write to the request.

    @ivar bufferSize: The size of the chunk to read from the file on each call.
    """

    bufferSize: int = abstract.FileDescriptor.bufferSize

    def __init__(self, request: http.Request, fileObject: IO[bytes]) -> None:
        """
        Initialize the instance.
        """
        self.request: http.Request | None = request
        self.fileObject = fileObject

    def start(self) -> None:
        raise NotImplementedError(self.start)

    def resumeProducing(self) -> None:
        raise NotImplementedError(self.resumeProducing)

    def stopProducing(self) -> None:
        """
        Stop producing data.

        L{twisted.internet.interfaces.IProducer.stopProducing}
        is called when our consumer has died, and subclasses also call this
        method when they are done producing data.
        """
        self.fileObject.close()
        self.request = None


class NoRangeStaticProducer(StaticProducer):
    """
    A L{StaticProducer} that writes the entire file to the request.
    """

    def start(self) -> None:
        assert self.request is not None
        self.request.registerProducer(self, False)

    def resumeProducing(self) -> None:
        if not self.request:
            return
        """
        We need to close the file, and we need to finish the request.

        we need to handle several different errors here:

            - the file might have been closed outside of our control, in which
              case we need to make sure that when .read() raises an error we
              still notice and finish the request and don't leave it
              outstanding.  This is unlikely and requires a state-corruption
              bug somewhere else in the code, but it is I/O that _could_ happen
              and we should account for it.

            - the request might have already been finished, in which case both
              .request.write() and .request.finish() will raise exceptions.  we
              should probably handle errors from those too, although we *could*
              find out that the request has already finished via
              .notifyFinish().

            - There's no reason that .close() should ever raise an exception,
              stopProducing should be fine.
        """
        data = self.fileObject.read(self.bufferSize)
        if data:
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        else:
            self.request.unregisterProducer()
            self.request.finish()
            self.stopProducing()


class SingleRangeStaticProducer(StaticProducer):
    """
    A L{StaticProducer} that writes a single chunk of a file to the request.
    """

    def __init__(
        self,
        request: http.Request,
        fileObject: IO[bytes],
        offset: int,
        size: int,
    ) -> None:
        """
        Initialize the instance.

        @param request: See L{StaticProducer}.

        @param fileObject: See L{StaticProducer}.

        @param offset: The offset into the file of the chunk to be written.

        @param size: The size of the chunk to write.
        """
        super().__init__(request, fileObject)
        self.offset = offset
        self.size = size

    def start(self) -> None:
        assert self.request is not None, "request must be set to start producing"
        """
        If this file object is bad, we should handle that and inform the
        request.
        """
        self.fileObject.seek(self.offset)
        self.bytesWritten = 0
        self.request.registerProducer(self, 0)

    def resumeProducing(self) -> None:
        if not self.request:
            return
        """
        All the same error conditions as L{NoRangeStaticProducer}; no new ones
        here, the only new one is seek().
        """
        data = self.fileObject.read(min(self.bufferSize, self.size - self.bytesWritten))
        if data:
            self.bytesWritten += len(data)
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        if (self.request and self.bytesWritten == self.size) or (not data):
            self.request.unregisterProducer()
            self.request.finish()
            self.stopProducing()


class MultipleRangeStaticProducer(StaticProducer):
    """
    A L{StaticProducer} that writes several chunks of a file to the request.
    """

    partBoundary: bytes | None

    def __init__(
        self,
        request: http.Request,
        fileObject: IO[bytes],
        rangeInfo: list[tuple[bytes, int, int]],
    ):
        """
        Initialize the instance.

        @param request: See L{StaticProducer}.
        @param fileObject: See L{StaticProducer}.
        @param rangeInfo: A list of tuples C{[(boundary, offset, size)]}
            where:
             - C{boundary} will be written to the request first.
             - C{offset} the offset into the file of chunk to write.
             - C{size} the size of the chunk to write.
        """
        StaticProducer.__init__(self, request, fileObject)
        self.rangeInfo = rangeInfo

    def start(self) -> None:
        assert self.request is not None, "request must be set to start producing"
        self.rangeIter = iter(self.rangeInfo)
        self._nextRange()
        self.request.registerProducer(self, 0)

    def _nextRange(self) -> None:
        self.partBoundary, partOffset, self._partSize = next(self.rangeIter)
        self._partBytesWritten = 0
        """
        This might also raise an error, as explained above in
        L{SingleRangeStaticProducer}.
        """
        self.fileObject.seek(partOffset)

    def resumeProducing(self) -> None:
        if not self.request:
            return
        # the raw data we are going to write to the request in this
        # resumeProducing call
        data = []
        # the accumulated length of all the bytes in `data`
        dataLength = 0
        # have we reached the last chunk
        done = False
        while dataLength < self.bufferSize:
            if self.partBoundary:
                # We are *at* the part boundary; write out the header.
                dataLength += len(self.partBoundary)
                data.append(self.partBoundary)
                self.partBoundary = None
            if self._partSize:
                # If the part has no size, it's just the trailer; otherwise we
                # need to actually read some bytes from the file.
                toRead = min(
                    self.bufferSize,
                    self._partSize - self._partBytesWritten,
                )
                assert toRead > 0
                p = self.fileObject.read(toRead)
                if not p:
                    done = True
                    break
                self._partBytesWritten += len(p)
                dataLength += len(p)
                data.append(p)
            if self.request and self._partBytesWritten == self._partSize:
                try:
                    self._nextRange()
                except StopIteration:
                    done = True
                    break
        self.request.write(b"".join(data))
        if done:
            self.request.unregisterProducer()
            self.request.finish()
            self.stopProducing()
