# -*- test-case-name: twisted.web.test.test_static -*-
"""
Implementations of Range: header request logic for L{twisted.web.static}.
"""

from __future__ import annotations

import os
import time
from typing import IO

from zope.interface import implementer

from twisted.internet import abstract, interfaces
from twisted.python import log
from twisted.web import http

validRange = tuple[int, int] | tuple[None, int] | tuple[int, None]
ranges = list[validRange]


def _rangeToOffsetAndSize(
    size: int, start: int | None, end: int | None
) -> tuple[int, int]:
    """
    Convert a start and end from a Range header to an offset and size.

    This method checks that the resulting range overlaps with the size of the
    resource being served.

    Either but not both of start or end can be L{None}.

        - start=L{None} means that the end value is actually a start value
          relative to the end of the resource.

        - end=L{None} means the end of the resource should be the end of the
          range.

    End is interpreted as inclusive, per RFC 2616.

    If this range doesn't overlap with any of this resource, C{(0, 0)} is
    returned, which is not otherwise a value return value.

    @param start: The start value from the header, or L{None} if one was not
        present.

    @param end: The end value from the header, or L{None} if one was not
        present.

    @return: C{(offset, size)} where offset is how far into this resource this
        resource the range begins and size is how long the range is, or C{(0,
        0)} if the range does not overlap this resource.
    """
    if start is None:
        assert end is not None, "start and end cannot both be None"
        start = max(0, size - end)
        end = size
    elif end is None:
        end = size
    elif end < size:
        end += 1
    elif end > size:
        end = size
    if start >= size:
        start = end = 0
    return start, (end - start)


def _parseRangeHeader(rangeHeader: bytes) -> ranges:
    """
    Parse the value of a Range header into (start, stop) pairs.

    In a given pair, either of start or stop can be None, signifying that
    no value was provided, but not both.

    @return: A list C{[(start, stop)]} of pairs.
    """

    def invalid(reason: str | None = None) -> ranges:
        log.msg(f"Ignoring malformed Range header {rangeHeader.decode('charmap')!r}")
        return []

    try:
        kind, value = rangeHeader.split(b"=", 1)
    except ValueError:
        return invalid("missing = separator")
    kind = kind.strip()
    if kind != b"bytes":
        return invalid(f"Unsupported Bytes-Unit: {kind!r}")
    unparsedRanges = list(filter(None, map(bytes.strip, value.split(b","))))
    parsedRanges: ranges = []

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


def _setupNoRange(
    request: http.Request,
    fullFileSize: int,
    fileForReading: IO[bytes],
    contentType: str | None,
    contentEncoding: str | None,
) -> NoRangeStaticProducer:
    request.setResponseCode(http.OK)
    _simpleContentHeaders(request, fullFileSize, contentType, contentEncoding)
    return NoRangeStaticProducer(request, fileForReading)


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
            """
            There's another bug here: we just keep writing until the data runs
            out.  Which means that if someone appends to the file, we will
            write longer than content-length.
            """
        else:
            self.request.unregisterProducer()
            self.request.finish()
            self.stopProducing()


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
    startAndEnd: validRange,
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
    start, end = startAndEnd
    offset, size = _rangeToOffsetAndSize(fullFileSize, start, end)
    if offset == size == 0:
        _notSatisfiableFor(request, fullFileSize)
    else:
        request.setResponseCode(http.PARTIAL_CONTENT)
        request.setHeader(b"content-range", _contentRange(offset, size, fullFileSize))
    _simpleContentHeaders(request, size, contentType, contentEncoding)
    return SingleRangeStaticProducer(request, fileForReading, offset, size)


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
        assert self.request is not None, "request must be set to start producing"
        """
        If this file object is bad, we should handle that and inform the
        request.
        """
        self.fileObject.seek(self.offset)
        self.bytesWritten = 0
        self.request.registerProducer(self, False)

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


def _setupMultiRange(
    request: http.Request,
    byteRanges: ranges,
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
    rangeInfo: list[tuple[bytes, int, int]] = []
    contentLength = 0
    boundary = f"{int(time.time() * 1000000):x}{os.getpid():x}".encode()
    if not contentType:
        contentType = "bytes"  # Do what Apache HTTPD does.
    for start, end in byteRanges:
        partOffset, partSize = _rangeToOffsetAndSize(fullFileSize, start, end)
        if partOffset == partSize == 0:
            continue
        contentLength += partSize
        partSeparator = (
            b"\r\n--%s\r\n" b"Content-type: %s\r\n" b"Content-range: %s\r\n" b"\r\n"
        ) % (
            boundary,
            contentType.encode(),
            _contentRange(partOffset, partSize, fullFileSize),
        )
        contentLength += len(partSeparator)
        rangeInfo.append((partSeparator, partOffset, partSize))
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
                toRead = min(self.bufferSize, self._partSize - self._partBytesWritten)
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


def _setupRangeProducer(
    request: http.Request,
    fileForReading: IO[bytes],
    fullFileSize: int,
    contentType: str | None,
    contentEncoding: str | None,
) -> StaticProducer:
    byteRange = request.getHeader(b"range")
    parsedRanges = _parseRangeHeader(byteRange or b"")
    if len(parsedRanges) == 0:
        return _setupNoRange(
            request, fullFileSize, fileForReading, contentType, contentEncoding
        )
    if len(parsedRanges) == 1:
        return _setupSingleRange(
            request,
            parsedRanges[0],
            fullFileSize,
            fileForReading,
            contentType,
            contentEncoding,
        )
    return _setupMultiRange(
        request, parsedRanges, fullFileSize, fileForReading, contentType
    )
