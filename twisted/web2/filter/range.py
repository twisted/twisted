# -*- test-case-name: twisted.web2.test.test_stream -*-

import time, os

from twisted.web2 import http, http_headers, responsecode, stream

# Some starts at writing a response filter to handle request ranges.

class UnsatisfiableRangeRequest(Exception):
    pass

def canonicalizeRange((start, end), size):
    """Return canonicalized (start, end) or raises UnsatisfiableRangeRequest
    exception.

    NOTE: end is the last byte *inclusive*, which is not the usual convention
    in python! Be very careful! A range of 0,1 should return 2 bytes."""
    
    # handle "-500" ranges
    if start is None:
        start = max(0, size-end)
        end = None
    
    if end is None or end >= size:
        end = size - 1
        
    if start >= size:
        raise UnsatisfiableRangeRequest
    
    return start,end

def makeUnsatisfiable(request, oldresponse):
    if request.headers.hasHeader('if-range'):
        return oldresponse # Return resource instead of error
    response = http.Response(responsecode.REQUESTED_RANGE_NOT_SATISFIABLE)
    response.headers.setHeader("content-range", ('bytes', None, None, oldresponse.stream.length))
    return response

def makeSegment(inputStream, lastOffset, start, end):
    offset = start - lastOffset
    length = end + 1 - start
    
    if offset != 0:
        before, inputStream = inputStream.split(offset)
        before.close()
    return inputStream.split(length)

def rangefilter(request, oldresponse):
    if oldresponse.stream is None:
        return oldresponse
    size = oldresponse.stream.length
    if size is None:
        # Does not deal with indeterminate length outputs
        return oldresponse

    oldresponse.headers.setHeader('accept-ranges',('bytes',))
    
    rangespec = request.headers.getHeader('range')
    
    # If we've got a range header and the If-Range header check passes, and
    # the range type is bytes, do a partial response.
    if (rangespec is not None and http.checkIfRange(request, oldresponse) and
        rangespec[0] == 'bytes'):
        # If it's a single range, return a simple response
        if len(rangespec[1]) == 1:
            try:
                start,end = canonicalizeRange(rangespec[1][0], size)
            except UnsatisfiableRangeRequest:
                return makeUnsatisfiable(request, oldresponse)

            response = http.Response(responsecode.PARTIAL_CONTENT, oldresponse.headers)
            response.headers.setHeader('content-range',('bytes',start, end, size))
            
            content, after = makeSegment(oldresponse.stream, 0, start, end)
            after.close()
            response.stream = content
            return response
        else:
            # Return a multipart/byteranges response
            lastOffset = -1
            offsetList = []
            for arange in rangespec[1]:
                try:
                    start,end = canonicalizeRange(arange, size)
                except UnsatisfiableRangeRequest:
                    continue
                if start <= lastOffset:
                    # Stupid client asking for out-of-order or overlapping ranges, PUNT!
                    return oldresponse
                offsetList.append((start,end))
                lastOffset = end

            if not offsetList:
                return makeUnsatisfiable(request, oldresponse)
            
            content_type = oldresponse.headers.getRawHeaders('content-type')
            boundary = "%x%x" % (int(time.time()*1000000), os.getpid())
            response = http.Response(responsecode.PARTIAL_CONTENT, oldresponse.headers)
            
            response.headers.setHeader('content-type',
                http_headers.MimeType('multipart', 'byteranges',
                                      [('boundary', boundary)]))
            response.stream = out = stream.CompoundStream()
            
            
            lastOffset = 0
            origStream = oldresponse.stream

            headerString = "\r\n--%s" % boundary
            if len(content_type) == 1:
                headerString+='\r\nContent-Type: %s' % content_type[0]
            headerString+="\r\nContent-Range: %s\r\n\r\n"
            
            for start,end in offsetList:
                out.addStream(headerString % 
                    http_headers.generateContentRange(('bytes', start, end, size)))

                content, origStream = makeSegment(origStream, lastOffset, start, end)
                lastOffset = end + 1
                out.addStream(content)
            origStream.close()
            out.addStream("\r\n--%s--\r\n" % boundary)
            return response
    else:
        return oldresponse

    
__all__ = ['rangefilter']
