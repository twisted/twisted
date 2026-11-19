# -*- test-case-name: twisted.web.test.test_static -*-
"""
Implementation of C{Range:} header request logic for L{twisted.web.static}.
"""

from __future__ import annotations

import os
import re
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
rangeHeaderRE = re.compile(rb"\s*bytes\s*=\s*(.*)", re.DOTALL)
oneRangeRE = re.compile(rb"\s*(\d*)\s*-\s*(\d*)\s*")


def _rangeToOffsetAndLength(size: int, rangeHeaderValue: ValidRange) -> tuple[int, int]:
    """
    Convert an RFC2616-style C{(start, end)} from a C{Range} header to an
    offset (a location to seek to) and a length (a number of bytes to read).

    @param size: The total size of the resource being served.

    @param rangeHeaderValue: The C{(start, end)} values as parsed from the
        header.  Either, but not both, of C{start} or C{end} can be L{None}.

    @return: C{(offset, length)} where C{offset} is a count of bytes from the
        beginning of this resource where the requested range begins, and
        C{length} is the number of bytes to read; or, C{(0, 0)}, if the given
        range does not overlap the given size.
    """
    match rangeHeaderValue:
        case (None, int(fromEnd)):
            # empty 'start' means 'end' is actually a count from the end
            ending = size
            offset = max(0, size - fromEnd)
        case (int(offset), None):
            # empty 'end' means 'end' is the end of the resource
            ending = size
        case (int(offset), int(endInclusive)):
            # we have both; 'end' is inclusive, so count is +1
            ending = endInclusive + 1 if endInclusive < size else size
    return (offset, ending - offset) if offset < size and offset != ending else (0, 0)


def _parseRangeHeader(rangeHeader: bytes) -> ValidRanges:
    """
    Parse the value of a Range header into (start, stop) pairs.

    In a given pair, either of start or stop can be None, signifying that no
    value was provided, but not both.

    @param rangeHeader: The contents of a C{Range} header to parse.

    @return: A list C{[(start, stop)]} of pairs.
    """

    def invalid() -> ValidRanges:
        log.warn(
            "Ignoring malformed Range header {rangeHeader!r}",
            rangeHeader=rangeHeader.decode("charmap"),
        )
        return []

    matched = rangeHeaderRE.fullmatch(rangeHeader)
    if not matched:
        return invalid()
    parsedRanges: ValidRanges = []
    for byteRange in filter(None, map(bytes.strip, matched.groups()[0].split(b","))):
        matched = oneRangeRE.fullmatch(byteRange)
        if not matched:
            return invalid()
        match [int(each) if each else None for each in matched.groups()]:
            case (None, int(validEnd)):
                parsedRanges.append((None, validEnd))
            case (int(validStart), None):
                parsedRanges.append((validStart, None))
            case (int(validStart), int(validEnd)):
                if validStart >= validEnd:
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

        @param request: the HTTP request to process.

        @param fileObject: The already-open file object to send to the given
            request.
        """
        self.request: Request | None = request
        self.fileObject = fileObject

    def start(self) -> None:
        """
        Begin sending the contents of this L{StaticProducer}'s file to its
        request.
        """
        request = self.request
        assert request is not None, "request must be not-None to start"

        def _unregisterAndStop(result: object) -> None:
            request.unregisterProducer()
            self.stopProducing()

        request.notifyFinish().addBoth(_unregisterAndStop)
        request.registerProducer(self, False)

    def resumeProducing(self) -> None:
        """
        Subclasses must implement this.
        """
        raise NotImplementedError(self.resumeProducing)

    def stopProducing(self) -> None:
        """
        Stop producing data.

        @note: this I{should} be called when the consumer (i.e. the
            L{http.Request}) is done consuming, but that is not done
            automatically for non-streaming (pull) producers such as this one,
            so instead the L{StaticProducer.start} method sets up the request
            to notify when finished.
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
    """
    Update the given C{request}, which has no C{Range} header, for a response
    that includes the entire given file, and create a
    L{SingleRangeStaticProducer} that will produce that entire file.
    """
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
    oneRange: ValidRange,
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
    offset, length = _rangeToOffsetAndLength(fullFileSize, oneRange)
    if length == 0:
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
        """
        Write some remaining bytes to the request up until the end of the file.
        """
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
    No longer used in the request-handling pipeline anywhere.
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
    and C{Content-Type} and C{Content-Length} headers appropriately.

    @param request: The HTTP request object.

    @param byteRanges: A list of C{(start, end)} values as specified by the
        header.  For each range, at most one of C{start} and C{end} may be
        L{None}.

    @param fullFileSize: The size of the underlying file.

    @param fileForReading: The already-open file to seek around for reading.

    @param contentType: the C{Content-Type} of the underlying file.

    @return: a L{MultipleRangeStaticProducer} that will produce the response.
    """
    rangeInfo: MimeRanges = []
    contentLength = 0
    boundary = f"{int(time.time() * 1000000):x}{os.getpid():x}".encode()
    if not contentType:
        contentType = "bytes"  # Do what Apache HTTPD does.
    for eachRange in byteRanges:
        partOffset, partLength = _rangeToOffsetAndLength(fullFileSize, eachRange)
        if partLength == 0:
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
        """
        Begin a multipart response to a multi-range request.
        """
        self.rangeIter = iter(self.rangeInfo)
        self._nextRange()
        super().start()

    def _nextRange(self) -> None:
        """
        It's time to start producing a new range; update the state to do so,
        and seek the file to the appropriate place.

        @raise StopIteration: when we have no further parts to produce.
        """
        self.partBoundary, partOffset, self._partLength = next(self.rangeIter)
        self._partBytesWritten = 0
        self.fileObject.seek(partOffset)

    def resumeProducing(self) -> None:
        """
        Read data from the file and write data to the request until we have
        written C{self.bufferSize} bytes of data, or until we are out of bytes
        to write, at which point, finish the request.
        """
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
    Determine an appropriate L{IPullProducer} implementation to use, create it,
    and set up any headers on the given L{http.Request}.

    @param request: The request to write the response to.

    @param openFile: The already-opened file to read from.

    @param fileSize: The size of the file.

    @param contentType: The C{Content-Type} of the given file.

    @param contentEncoding: The C{Content-Encoding} of the given file.

    @return: an instance of a subclass of L{StaticProducer} that will produce
        the appropriate range indicated by the C{request}.
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
        case [*parsedRanges]:
            return _setupMultiRange(
                request, parsedRanges, fileSize, openFile, contentType
            )
