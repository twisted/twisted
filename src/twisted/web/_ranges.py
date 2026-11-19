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
from twisted.web import http

log = Logger()

ValidRange = tuple[int | None, int | None]

# type signature is intentionally wrong; should be this:
# https://github.com/python/mypy/issues/22511
# ValidRange = tuple[None, int] | tuple[int, None] | tuple[int, int]

ValidRanges = list[ValidRange]
MimeRanges = list[tuple[bytes, int, int]]


def _rangeToOffsetAndLength(size: int, rangeHeaderValue: ValidRange) -> tuple[int, int]:
    """
    Convert a C{(start, end)} from a Range header to an offset and length.

    Either but not both of start or end can be L{None}.

        - start=L{None} means that the end value is actually a start value
          relative to the end of the resource.

        - end=L{None} means the end of the resource should be the end of the
          range.

    End is I{inclusive}, per RFC 2616.  If this range doesn't overlap with any
    of this resource, C{(0, 0)} is returned, which is not otherwise a value
    return value.

    @param size: The total size of the resource being served.

    @param rangeHeaderValue: The (start,end) values as parsed from the header.

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
    return (offset, ending - offset) if offset < size else (0, 0)


def _parseRangeHeader(rangeHeader: bytes) -> ValidRanges:
    """
    Parse the value of a Range header into (start, stop) pairs.

    In a given pair, either of start or stop can be None, signifying that
    no value was provided, but not both.

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
        except ValueError:
            return invalid()
        if startBytes:
            try:
                start = int(startBytes)
            except ValueError:
                return invalid()
        if endBytes:
            try:
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
    request: http.Request,
    size: int,
    contentType: str | None = None,
    contentEncoding: str | None = None,
) -> None:
    """
    Set simple Content-length and Content-type headers for this request, for
    when the request is returning either a full body or a simple range.

    @param request: The L{twisted.web.http.Request} object.

    @param size: The content-length to specify.

    @param contentType: The content-type, if any.

    @param contentEncoding: The content-encoding, if any.
    """
    request.setHeader(b"content-length", b"%d" % (size,))
    if contentType:
        request.setHeader(b"content-type", contentType.encode())
    if contentEncoding:
        request.setHeader(b"content-encoding", contentEncoding.encode())


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

        L{twisted.internet.interfaces.IProducer.stopProducing}
        is called when our consumer has died, and subclasses also call this
        method when they are done producing data.
        """
        self.fileObject.close()
        self.request = None


def _setupNoRange(
    request: http.Request,
    fullFileSize: int,
    fileForReading: IO[bytes],
    contentType: str | None,
    contentEncoding: str | None,
) -> SingleRangeStaticProducer:
    request.setResponseCode(http.OK)
    _simpleContentHeaders(request, fullFileSize, contentType, contentEncoding)
    return SingleRangeStaticProducer(request, fileForReading, 0, fullFileSize)


def _contentRange(offset: int, size: int, fullFileSize: int) -> bytes:
    """
    Return a string suitable for the value of a Content-Range header for a
    range with the given offset and size.

    The offset and size are not sanity checked in any way.

    @param offset: How far into this resource the range begins.

    @param size: How long the range is.

    @param fullFileSize: How long the entire resource is.

    @return: The value as appropriate for the value of a Content-Range header.
    """
    return b"bytes %d-%d/%d" % (offset, offset + size - 1, fullFileSize)


def _notSatisfiableFor(request: http.Request, fullFileSize: int) -> None:
    """
    The given request is not satisfiable, according to the RFC.  Set an
    appropriate response code and content-range header.
    """
    request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
    request.setHeader(b"content-range", b"bytes */%d" % (fullFileSize,))


def _setupSingleRange(
    request: http.Request,
    startAndEnd: ValidRange,
    fullFileSize: int,
    fileForReading: IO[bytes],
    contentType: str | None,
    contentEncoding: str | None,
) -> SingleRangeStaticProducer:
    """
    Set up the response for Range headers that specify a single range.

    This method checks if the request is satisfiable and sets the response code
    and Content-Range header appropriately.  The return value indicates which
    part of the resource to return.

    @param request: The Request object.

    @param startAndEnd: A 2-tuple of start of the byte range as specified by
        the header and the end of the byte range as specified by the header.
        At most one of the start and end may be L{None}.

    @return: A 2-tuple of the offset and size of the range to return.  offset
        == size == 0 indicates that the request is not satisfiable.
    """
    offset, length = _rangeToOffsetAndLength(fullFileSize, startAndEnd)
    if offset == length == 0:
        _notSatisfiableFor(request, fullFileSize)
    else:
        request.setResponseCode(http.PARTIAL_CONTENT)
        request.setHeader(b"content-range", _contentRange(offset, length, fullFileSize))
    _simpleContentHeaders(request, length, contentType, contentEncoding)
    return SingleRangeStaticProducer(request, fileForReading, offset, length)


class SingleRangeStaticProducer(StaticProducer):
    """
    A L{StaticProducer} that writes a single chunk of a file to the request.
    """

    def __init__(
        self, request: http.Request, fileObject: IO[bytes], offset: int, size: int
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

    def __init__(self, request: http.Request, fileObject: IO[bytes]) -> None:
        here = fileObject.tell()
        fileObject.seek(0, SEEK_END)
        size = fileObject.tell()
        fileObject.seek(here, SEEK_SET)
        super().__init__(request, fileObject, 0, size)


def _setupMultiRange(
    request: http.Request,
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
    contentType = None
    if rangeInfo:
        finalBoundary = b"\r\n--" + boundary + b"--\r\n"
        rangeInfo.append((finalBoundary, 0, 0))
        request.setResponseCode(http.PARTIAL_CONTENT)
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
        self,
        request: http.Request,
        fileObject: IO[bytes],
        rangeInfo: MimeRanges,
    ):
        """
        Initialize the instance.

        @param request: See L{StaticProducer}.

        @param fileObject: See L{StaticProducer}.

        @param rangeInfo: A list of tuples C{[(boundary, offset, size)]} where:

            - C{boundary} will be written to the request first.

            - C{offset} the offset into the file of chunk to write.

            - C{size} the size of the chunk to write.
        """
        StaticProducer.__init__(self, request, fileObject)
        self.rangeInfo = rangeInfo

    def start(self) -> None:
        self.rangeIter = iter(self.rangeInfo)
        self._nextRange()
        super().start()

    def _nextRange(self) -> None:
        self.partBoundary, partOffset, self._partSize = next(self.rangeIter)
        self._partBytesWritten = 0
        """
        This might also raise an error, as explained above in
        L{SingleRangeStaticProducer}.
        """
        self.fileObject.seek(partOffset)

    def resumeProducing(self) -> None:
        if self.request is None:
            raise RuntimeError("request must not be done to resume producing")
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
                toRead = min(self.bufferSize, self._partSize - self._partBytesWritten)
                assert (
                    toRead > 0
                ), f"part={self._partSize} written={self._partBytesWritten}"
                p = self.fileObject.read(toRead)
                if not p:
                    done = True
                    break
                self._partBytesWritten += len(p)
                dataLength += len(p)
                data.append(p)
            if self._partBytesWritten == self._partSize:
                try:
                    self._nextRange()
                except StopIteration:
                    done = True
                    break
        self.request.write(b"".join(data))
        if done:
            self.request.finish()


def _setupRangeProducer(
    request: http.Request,
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
