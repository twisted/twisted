# -*- test-case-name: twisted.web.test.test_static -*-
"""
Implementation of C{Range:} header request logic for L{twisted.web.static}.
"""

from __future__ import annotations

import os
import time
from io import SEEK_END, SEEK_SET
from typing import IO

from zope.interface import implementer

from twisted.internet import abstract, interfaces
from twisted.logger import Logger
from twisted.web.http import (
    OK,
    PARTIAL_CONTENT,
    REQUESTED_RANGE_NOT_SATISFIABLE,
    Request,
)

ValidRange = tuple[int | None, int | None]
ValidRanges = list[ValidRange]
MimeRanges = list[tuple[bytes, int, int]]

# ValidRange is intentionally wrongly typed due to
# <https://github.com/python/mypy/issues/22511>; it should be this:

# ValidRange = tuple[None, int] | tuple[int, None] | tuple[int, int]

log = Logger()


def _rangeToOffsetAndLength(size: int, rangeHeaderValue: ValidRange) -> tuple[int, int]:
    """
    Convert an RFC2616-style C{(start, end)} from a C{Range} header to an
    offset (a location to seek to) and a length (a number of bytes to read).

    Either, but not both, of C{start} or C{end} can be L{None}.

        - C{start}=L{None} means that C{end} is actually a start value relative
          to the end of the resource.

        - C{end}=L{None} means the end of the resource should be the end of the
          range.

    End is I{inclusive}, per RFC 2616.  If this range doesn't overlap with any
    of this resource, C{(0, 0)} is returned, which is not otherwise a value
    return value.

    @param size: The total size of the resource being served.

    @param rangeHeaderValue: The C{(start, end)} values as parsed from the
        header.

    @return: C{(offset, size)} where offset is how far into this resource this
        resource the range begins and size is how long the range is, or C{(0,
        0)} if the range does not overlap this resource.
    """
    match rangeHeaderValue:
        case (int(offset), int(endInclusive)):
            ending = endInclusive + 1 if endInclusive < size else size
        case (None, int(fromEnd)):
            offset = max(0, size - fromEnd)
            ending = size
        case (int(offset), None):
            ending = size
    return (offset, ending - offset) if offset < size and offset != ending else (0, 0)


def _parseRangeHeader(rangeHeader: bytes) -> ValidRanges:
    """
    Parse the value of a Range header into (start, stop) pairs.

    In a given pair, either of start or stop can be None, signifying that no
    value was provided, but not both.

    @param rangeHeader: The text content of the C{Range} header.

    @return: A list C{[(start, stop)]} of pairs.
    """

    def invalid(reason: str | None = None) -> ValidRanges:
        log.warn(
            "Ignoring malformed Range header {rangeHeader!r}",
            rangeHeader=rangeHeader.decode("charmap"),
        )
        return []

    try:
        kind, value = rangeHeader.split(b"=", 1)
    except ValueError:
        return invalid("missing = separator")
    kind = kind.strip()
    if kind != b"bytes":
        return invalid(f"Unsupported Bytes-Unit: {kind!r}")
    unparsedRanges = list(filter(None, map(bytes.strip, value.split(b","))))
    parsedRanges: ValidRanges = []

    for byteRange in unparsedRanges:
        start: int | None = None
        end: int | None = None
        try:
            startBytes, endBytes = byteRange.split(b"-", 1)
            if startBytes:
                start = int(startBytes)
            if endBytes:
                end = int(endBytes)
        except ValueError:
            return invalid()
        match (start, end):
            case (None, int(validEnd)):
                parsedRanges.append((None, validEnd))
            case (int(validStart), None):
                parsedRanges.append((validStart, None))
            case (int(validStart), int(validEnd)):
                if start >= end:
                    return invalid()
                parsedRanges.append((validStart, validEnd))
            case _:  # (None, None)
                return invalid()
    return parsedRanges


def _simpleContentHeaders(
    request: Request,
    length: int,
    contentType: str | None = None,
    contentEncoding: str | None = None,
) -> None:
    """
    Set simple C{Content-Length} and C{Content-Type} headers for this request,
    for when the request is returning either a full body or a single range.

    @param request: The L{twisted.web.http.Request} object.

    @param length: The C{Content-Length} to specify.

    @param contentType: The C{Content-Type}, if any.

    @param contentEncoding: The C{Content-Encoding}, if any.
    """
    request.setHeader(b"content-length", b"%d" % (length,))
    if contentType:
        request.setHeader(b"content-type", contentType.encode())
    if contentEncoding:
        request.setHeader(b"content-encoding", contentEncoding.encode())


@implementer(interfaces.IPullProducer)
class StaticProducer:
    """
    Superclass for classes that implement the business of producing.

    @ivar request: The L{IRequest} to write the contents of the file to, or
        C{None} if the writing is done.

    @ivar fileObject: The file the contents of which to write to the request.

    @ivar bufferSize: The size of the chunk to read from the file on each call.
    """

    bufferSize: int = abstract.FileDescriptor.bufferSize

    def __init__(self, request: Request, fileObject: IO[bytes]) -> None:
        """
        Initialize the instance.
        """
        self.request: Request | None = request
        self.fileObject = fileObject

    def start(self) -> None:
        request = self.request
        assert request is not None, "request must be not-None to start"

        def _unregisterAndStop(result: object) -> None:
            request.unregisterProducer()
            self.stopProducing()

        request.notifyFinish().addBoth(_unregisterAndStop)
        request.registerProducer(self, False)

    def resumeProducing(self) -> None:
        raise NotImplementedError(self.resumeProducing)

    def stopProducing(self) -> None:
        """
        Stop producing data.

        @note: this I{should} be called when the consumer (i.e. the
            L{http.Request}) is done consuming, but that is not done
            automatically for non-streaming (pull) producers such as this one.
        """
        self.fileObject.close()
        self.request = None


def _setupNoRange(
    request: Request,
    fullFileSize: int,
    fileForReading: IO[bytes],
    contentType: str | None,
    contentEncoding: str | None,
) -> SingleRangeStaticProducer:
    request.setResponseCode(OK)
    _simpleContentHeaders(request, fullFileSize, contentType, contentEncoding)
    return SingleRangeStaticProducer(request, fileForReading, 0, fullFileSize)


def _contentRange(offset: int, length: int, resourceSize: int) -> bytes:
    """
    Construct a C{Content-Range} header.

    @param offset: How far into this resource the range begins.

    @param length: How long the range is.

    @param resourceSize: How long the entire resource is.

    @return: a string suitable for the value of a C{Content-Range} header for a
        range with the given offset, length, and resource size.
    """
    return b"bytes %d-%d/%d" % (offset, offset + length - 1, resourceSize)


def _notSatisfiableFor(request: Request, fullFileSize: int) -> None:
    """
    The given request is not satisfiable, according to the RFC.  Set an
    appropriate response code and content-range header.
    """
    request.setResponseCode(REQUESTED_RANGE_NOT_SATISFIABLE)
    request.setHeader(b"content-range", b"bytes */%d" % (fullFileSize,))


def _setupSingleRange(
    request: Request,
    startAndEnd: ValidRange,
    fullFileSize: int,
    fileForReading: IO[bytes],
    contentType: str | None,
    contentEncoding: str | None,
) -> SingleRangeStaticProducer:
    """
    Set up the response for C{Range} headers that specify a single range.

    This method checks if the request is satisfiable and sets the response code
    and C{Content-Range} header appropriately.

    @param request: The Request object.

    @param startAndEnd: A 2-tuple of start of the byte range as specified by
        the header and the end of the byte range as specified by the header.
        At most one of the start and end may be L{None}.

    @return: A 2-tuple of the offset and length of the range to return.  offset
        == length == 0 indicates that the request is not satisfiable.
    """
    offset, length = _rangeToOffsetAndLength(fullFileSize, startAndEnd)
    if offset == length == 0:
        _notSatisfiableFor(request, fullFileSize)
    else:
        request.setResponseCode(PARTIAL_CONTENT)
        request.setHeader(b"content-range", _contentRange(offset, length, fullFileSize))
    _simpleContentHeaders(request, length, contentType, contentEncoding)
    return SingleRangeStaticProducer(request, fileForReading, offset, length)


class SingleRangeStaticProducer(StaticProducer):
    """
    A L{StaticProducer} that writes a single chunk of a file to the request.
    """

    def __init__(
        self, request: Request, fileObject: IO[bytes], offset: int, size: int
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
        self.fileObject.seek(self.offset)
        self.bytesWritten = 0
        super().start()

    def resumeProducing(self) -> None:
        if self.request is None:
            raise RuntimeError("request must not be done to resume producing")
        data = self.fileObject.read(min(self.bufferSize, self.size - self.bytesWritten))
        if data:
            self.bytesWritten += len(data)
            self.request.write(data)
        if (self.bytesWritten == self.size) or (not data):
            self.request.finish()


class NoRangeStaticProducer(SingleRangeStaticProducer):
    """
    Only re-exposed to satisfy existing tests and API compatibility surface.
    """

    def __init__(self, request: Request, fileObject: IO[bytes]) -> None:
        here = fileObject.tell()
        fileObject.seek(0, SEEK_END)
        size = fileObject.tell()
        fileObject.seek(here, SEEK_SET)
        super().__init__(request, fileObject, 0, size)


def _setupMultiRange(
    request: Request,
    byteRanges: ValidRanges,
    fullFileSize: int,
    fileForReading: IO[bytes],
    contentType: str | None,
) -> MultipleRangeStaticProducer:
    """
    Set up the response for Range headers that specify multiple ranges.

    This method checks if the request is satisfiable and sets the response code
    and Content-Type and Content-Length headers appropriately.  It creates a
    L{MultipleRangeStaticProducer} to produce the response.

    @param request: The Request object.

    @param byteRanges: A list of C{(start, end)} values as specified by the
        header.  For each range, at most one of C{start} and C{end} may be
        L{None}.

    @return: See above.
    """
    rangeInfo: MimeRanges = []
    contentLength = 0
    boundary = f"{int(time.time() * 1000000):x}{os.getpid():x}".encode()
    if not contentType:
        contentType = "bytes"  # Do what Apache HTTPD does.
    for eachRange in byteRanges:
        partOffset, partLength = _rangeToOffsetAndLength(fullFileSize, eachRange)
        if partOffset == partLength == 0:
            continue
        contentLength += partLength
        partSeparator = (
            b"\r\n--%s\r\n" b"Content-type: %s\r\n" b"Content-range: %s\r\n" b"\r\n"
        ) % (
            boundary,
            contentType.encode(),
            _contentRange(partOffset, partLength, fullFileSize),
        )
        contentLength += len(partSeparator)
        rangeInfo.append((partSeparator, partOffset, partLength))
    if rangeInfo:
        finalBoundary = b"\r\n--" + boundary + b"--\r\n"
        rangeInfo.append((finalBoundary, 0, 0))
        request.setResponseCode(PARTIAL_CONTENT)
        contentLength += len(finalBoundary)
        contentType = f'multipart/byteranges; boundary="{boundary.decode()}"'
    else:
        _notSatisfiableFor(request, fullFileSize)
    _simpleContentHeaders(request, contentLength, contentType)
    return MultipleRangeStaticProducer(request, fileForReading, rangeInfo)


class MultipleRangeStaticProducer(StaticProducer):
    """
    A L{StaticProducer} that writes several chunks of a file to the request.
    """

    partBoundary: bytes | None

    def __init__(
        self, request: Request, fileObject: IO[bytes], rangeInfo: MimeRanges
    ) -> None:
        """
        Initialize the instance.

        @param request: See L{StaticProducer}.

        @param fileObject: See L{StaticProducer}.

        @param rangeInfo: A list of tuples C{[(boundary, offset, length)]} where:

                - C{boundary} will be written to the request first.

                - C{offset} the offset into the file of chunk to write.

                - C{length} the length of the chunk to write.
        """
        StaticProducer.__init__(self, request, fileObject)
        self.rangeInfo = rangeInfo

    def start(self) -> None:
        self.rangeIter = iter(self.rangeInfo)
        self._nextRange()
        super().start()

    def _nextRange(self) -> None:
        self.partBoundary, partOffset, self._partLength = next(self.rangeIter)
        self._partBytesWritten = 0
        """
        This might also raise an error, as explained above in
        L{SingleRangeStaticProducer}.
        """
        self.fileObject.seek(partOffset)

    def resumeProducing(self) -> None:
        if self.request is None:
            raise RuntimeError("request must not be done to resume producing")
        data = []  # the raw data we are going to write to the request
        dataLength = 0  # the accumulated length of all the bytes in `data`
        done = False  # have we reached the last chunk
        while dataLength < self.bufferSize:
            if self.partBoundary:
                # We are *at* the part boundary; write out the boundary header.
                dataLength += len(self.partBoundary)
                data.append(self.partBoundary)
                self.partBoundary = None
            if self._partLength:
                # If the part has no size, it's just the trailer; otherwise we
                # need to actually read some bytes from the file.
                toRead = min(self.bufferSize, self._partLength - self._partBytesWritten)
                bytesRead = self.fileObject.read(toRead)
                if not bytesRead:
                    done = True
                    break
                self._partBytesWritten += len(bytesRead)
                dataLength += len(bytesRead)
                data.append(bytesRead)
            if self._partBytesWritten == self._partLength:
                try:
                    self._nextRange()
                except StopIteration:
                    done = True
                    break
        self.request.write(b"".join(data))
        if done:
            self.request.finish()


def _setupRangeProducer(
    request: Request,
    openFile: IO[bytes],
    fileSize: int,
    contentType: str | None,
    contentEncoding: str | None,
) -> StaticProducer:
    """
    Determine an appropriate L{IProducer} implementation to use, create it, and
    set up any headers on the given L{http.Request}.
    """
    match _parseRangeHeader(request.getHeader(b"range") or b""):
        case []:
            return _setupNoRange(
                request, fileSize, openFile, contentType, contentEncoding
            )
        case [oneRange]:
            return _setupSingleRange(
                request, oneRange, fileSize, openFile, contentType, contentEncoding
            )
        case list(parsedRanges):
            return _setupMultiRange(
                request, parsedRanges, fileSize, openFile, contentType
            )
