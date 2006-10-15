from __future__ import generators

import re
from zope.interface import implements
import urllib
import tempfile

from twisted.internet import defer
from twisted.web2.stream import IStream, FileStream, BufferedStream, readStream
from twisted.web2.stream import generatorToStream, readAndDiscard
from twisted.web2 import http_headers
from cStringIO import StringIO

###################################
#####  Multipart MIME Reader  #####
###################################

class MimeFormatError(Exception):
    pass

# parseContentDispositionFormData is absolutely horrible, but as
# browsers don't seem to believe in sensible quoting rules, it's
# really the only way to handle the header.  (Quotes can be in the
# filename, unescaped)
cd_regexp = re.compile(
    ' *form-data; *name="([^"]*)"(?:; *filename="(.*)")?$',
    re.IGNORECASE)

def parseContentDispositionFormData(value):
    match = cd_regexp.match(value)
    if not match:
        # Error parsing. 
        raise ValueError("Unknown content-disposition format.")
    name=match.group(1)
    filename=match.group(2)
    return name, filename


#@defer.deferredGenerator
def _readHeaders(stream):
    """Read the MIME headers. Assumes we've just finished reading in the
    boundary string."""

    ctype = fieldname = filename = None
    headers = []
    
    # Now read headers
    while 1:
        line = stream.readline(size=1024)
        if isinstance(line, defer.Deferred):
            line = defer.waitForDeferred(line)
            yield line
            line = line.getResult()
        #print "GOT", line
        if not line.endswith('\r\n'):
            if line == "":
                raise MimeFormatError("Unexpected end of stream.")
            else:
                raise MimeFormatError("Header line too long")

        line = line[:-2] # strip \r\n
        if line == "":
            break # End of headers
        
        parts = line.split(':', 1)
        if len(parts) != 2:
            raise MimeFormatError("Header did not have a :")
        name, value = parts
        name = name.lower()
        headers.append((name, value))
        
        if name == "content-type":
            ctype = http_headers.parseContentType(http_headers.tokenize((value,), foldCase=False))
        elif name == "content-disposition":
            fieldname, filename = parseContentDispositionFormData(value)
        
    if ctype is None:
        ctype == http_headers.MimeType('application', 'octet-stream')
    if fieldname is None:
        raise MimeFormatError('Content-disposition invalid or omitted.')

    # End of headers, return (field name, content-type, filename)
    yield fieldname, filename, ctype
    return
_readHeaders = defer.deferredGenerator(_readHeaders)


class _BoundaryWatchingStream(object):
    def __init__(self, stream, boundary):
        self.stream = stream
        self.boundary = boundary
        self.data = ''
        self.deferred = defer.Deferred()
        
    length = None # unknown
    def read(self):
        if self.stream is None:
            if self.deferred is not None:
                deferred = self.deferred
                self.deferred = None
                deferred.callback(None)
            return None
        newdata = self.stream.read()
        if isinstance(newdata, defer.Deferred):
            return newdata.addCallbacks(self._gotRead, self._gotError)
        return self._gotRead(newdata)

    def _gotRead(self, newdata):
        if not newdata:
            raise MimeFormatError("Unexpected EOF")
        # BLECH, converting buffer back into string.
        self.data += str(newdata)
        data = self.data
        boundary = self.boundary
        off = data.find(boundary)
        
        if off == -1:
            # No full boundary, check for the first character
            off = data.rfind(boundary[0], max(0, len(data)-len(boundary)))
            if off != -1:
                # We could have a partial boundary, store it for next time
                self.data = data[off:]
                return data[:off]
            else:
                self.data = ''
                return data
        else:
            self.stream.pushback(data[off+len(boundary):])
            self.stream = None
            return data[:off]

    def _gotError(self, err):
        # Propogate error back to MultipartMimeStream also
        if self.deferred is not None:
            deferred = self.deferred
            self.deferred = None
            deferred.errback(err)
        return err
    
    def close(self):
        # Assume error will be raised again and handled by MMS?
        readAndDiscard(self).addErrback(lambda _: None)
        
class MultipartMimeStream(object):
    implements(IStream)
    def __init__(self, stream, boundary):
        self.stream = BufferedStream(stream)
        self.boundary = "--"+boundary
        self.first = True
        
    def read(self):
        """
        Return a deferred which will fire with a tuple of:
        (fieldname, filename, ctype, dataStream)
        or None when all done.
        
        Format errors will be sent to the errback.
        
        Returns None when all done.

        IMPORTANT: you *must* exhaust dataStream returned by this call
        before calling .read() again!
        """
        if self.first:
            self.first = False
            d = self._readFirstBoundary()
        else:
            d = self._readBoundaryLine()
        d.addCallback(self._doReadHeaders)
        d.addCallback(self._gotHeaders)
        return d

    def _readFirstBoundary(self):
        #print "_readFirstBoundary"
        line = self.stream.readline(size=1024)
        if isinstance(line, defer.Deferred):
            line = defer.waitForDeferred(line)
            yield line
            line = line.getResult()
        if line != self.boundary + '\r\n':
            raise MimeFormatError("Extra data before first boundary: %r looking for: %r" % (line, self.boundary + '\r\n'))
        
        self.boundary = "\r\n"+self.boundary
        yield True
        return
    _readFirstBoundary = defer.deferredGenerator(_readFirstBoundary)

    def _readBoundaryLine(self):
        #print "_readBoundaryLine"
        line = self.stream.readline(size=1024)
        if isinstance(line, defer.Deferred):
            line = defer.waitForDeferred(line)
            yield line
            line = line.getResult()
        
        if line == "--\r\n":
            # THE END!
            yield False
            return
        elif line != "\r\n":
            raise MimeFormatError("Unexpected data on same line as boundary: %r" % (line,))
        yield True
        return
    _readBoundaryLine = defer.deferredGenerator(_readBoundaryLine)

    def _doReadHeaders(self, morefields):
        #print "_doReadHeaders", morefields
        if not morefields:
            return None
        return _readHeaders(self.stream)
    
    def _gotHeaders(self, headers):
        if headers is None:
            return None
        bws = _BoundaryWatchingStream(self.stream, self.boundary)
        self.deferred = bws.deferred
        ret=list(headers)
        ret.append(bws)
        return tuple(ret)


def readIntoFile(stream, outFile, maxlen):
    """Read the stream into a file, but not if it's longer than maxlen.
    Returns Deferred which will be triggered on finish.
    """
    curlen = [0]
    def done(_):
        return _
    def write(data):
        curlen[0] += len(data)
        if curlen[0] > maxlen:
            raise MimeFormatError("Maximum length of %d bytes exceeded." %
                                  maxlen)
        
        outFile.write(data)
    return readStream(stream, write).addBoth(done)

#@defer.deferredGenerator
def parseMultipartFormData(stream, boundary,
                           maxMem=100*1024, maxFields=1024, maxSize=10*1024*1024):
    # If the stream length is known to be too large upfront, abort immediately
    
    if stream.length is not None and stream.length > maxSize:
        raise MimeFormatError("Maximum length of %d bytes exceeded." %
                                  maxSize)
    
    mms = MultipartMimeStream(stream, boundary)
    numFields = 0
    args = {}
    files = {}
    
    while 1:
        datas = mms.read()
        if isinstance(datas, defer.Deferred):
            datas = defer.waitForDeferred(datas)
            yield datas
            datas = datas.getResult()
        if datas is None:
            break
        
        numFields+=1
        if numFields == maxFields:
            raise MimeFormatError("Maximum number of fields %d exceeded"%maxFields)
        
        # Parse data
        fieldname, filename, ctype, stream = datas
        if filename is None:
            # Not a file
            outfile = StringIO()
            maxBuf = min(maxSize, maxMem)
        else:
            outfile = tempfile.NamedTemporaryFile()
            maxBuf = maxSize
        x = readIntoFile(stream, outfile, maxBuf)
        if isinstance(x, defer.Deferred):
            x = defer.waitForDeferred(x)
            yield x
            x = x.getResult()
        if filename is None:
            # Is a normal form field
            outfile.seek(0)
            data = outfile.read()
            args.setdefault(fieldname, []).append(data)
            maxMem -= len(data)
            maxSize -= len(data)
        else:
            # Is a file upload
            maxSize -= outfile.tell()
            outfile.seek(0)
            files.setdefault(fieldname, []).append((filename, ctype, outfile))
        
        
    yield args, files
    return
parseMultipartFormData = defer.deferredGenerator(parseMultipartFormData)

###################################
##### x-www-urlencoded reader #####
###################################


def parse_urlencoded_stream(input, maxMem=100*1024,
                     keep_blank_values=False, strict_parsing=False):
    lastdata = ''
    still_going=1
    
    while still_going:
        try:
            yield input.wait
            data = input.next()
        except StopIteration:
            pairs = [lastdata]
            still_going=0
        else:
            maxMem -= len(data)
            if maxMem < 0:
                raise MimeFormatError("Maximum length of %d bytes exceeded." %
                                      maxMem)
            pairs = str(data).split('&')
            pairs[0] = lastdata + pairs[0]
            lastdata=pairs.pop()
        
        for name_value in pairs:
            nv = name_value.split('=', 1)
            if len(nv) != 2:
                if strict_parsing:
                    raise MimeFormatError("bad query field: %s") % `name_value`
                continue
            if len(nv[1]) or keep_blank_values:
                name = urllib.unquote(nv[0].replace('+', ' '))
                value = urllib.unquote(nv[1].replace('+', ' '))
                yield name, value
parse_urlencoded_stream = generatorToStream(parse_urlencoded_stream)

def parse_urlencoded(stream, maxMem=100*1024, maxFields=1024,
                     keep_blank_values=False, strict_parsing=False):
    d = {}
    numFields = 0

    s=parse_urlencoded_stream(stream, maxMem, keep_blank_values, strict_parsing)
    
    while 1:
        datas = s.read()
        if isinstance(datas, defer.Deferred):
            datas = defer.waitForDeferred(datas)
            yield datas
            datas = datas.getResult()
        if datas is None:
            break
        name, value = datas
        
        numFields += 1
        if numFields == maxFields:
            raise MimeFormatError("Maximum number of fields %d exceeded"%maxFields)
        
        if name in d:
            d[name].append(value)
        else:
            d[name] = [value]
    yield d
    return
parse_urlencoded = defer.deferredGenerator(parse_urlencoded)


if __name__ == '__main__':
    d = parseMultipartFormData(
        FileStream(open("upload.txt")), "----------0xKhTmLbOuNdArY")
    from twisted.python import log
    d.addErrback(log.err)
    def pr(s):
        print s
    d.addCallback(pr)

__all__ = ['parseMultipartFormData', 'parse_urlencoded', 'parse_urlencoded_stream', 'MultipartMimeStream', 'MimeFormatError']
