### WORK IN PROGRESS - DOES NOT WORK

from twisted.internet import defer
from twisted.web2.stream import FileStream, BufferedStream
from cStringIO import StringIO
import re


class MimeFormatError(Exception):
    pass

# parseContentDispositionFormData is absolutely horrible, but as
# browsers don't seem to believe in sensible quoting rules, it's
# really the only way to handle the header.  (Quotes can be in the
# filename, unescaped)
cd_regexp = re.compile(
    'content-disposition: *form-data; *name="([^"]*)"(; *filename="(.*)")?$',
    re.IGNORECASE)

def parseContentDispositionFormData(value):
    match = cd_regexp.match(value)
    if not match:
        # Error parsing. 
        raise ValueError("Unknown content-disposition format.")
    name=cd_regexp.group(0)
    filename=cd_regexp.group(2)
    return name, filename

#@defer.deferredGenerator
def parseMultipartFormData(stream, boundary, maxSize=):
    stream = BufferedStream(stream)

    #@defer.deferredGenerator
    def readDataTillBoundary(write, boundary):
        """Read in data from stream and call write on each chunk.
        Stops after reading in the boundary string.
        """
        lastData = ''
        
        while 1:
            data = lastData
            newdata = stream.read()
            if isinstance(newdata, defer.Deferred):
                newdata = defer.waitForDeferred(newdata)
                yield newdata; newdata = newdata.getResult()
                
            if not newdata:
                raise MimeFormatError("Unexpected EOF")
            data += newdata
            
            off = data.find(boundary)
            
            if off == -1:
                # No boundary
                off = data.rfind(boundary[0], max(0, len(data)-len(boundary)))
                if off != -1:
                    # But, we could have a partial result, store it for next time
                    write(data[:off])
                    data = data[off:]
                else:
                    write(data)
                    data = ''
                
                # Loop back around
            else:
                # Found boundary
                write(data[:off])
                stream.pushback(data[off+len(boundary):])
                return
    readDataTillBoundary = defer.deferredGenerator(readDataTillBoundary)
    
    
    #@defer.deferredGenerator
    def readHeaders():
        """Read the MIME headers. Assumes we've just finished reading in the boundary string."""
        
        ctype = None
        fieldname = None
        filename = None
        
        # Now read headers
        while 1:
            line = stream.readline(maxLength=1024)
            if isinstance(line, defer.Deferred):
                line = defer.waitForDeferred(line)
                yield line; line = line.getResult()
            
            if line == "":
                if ctype is None:
                    ctype == http_headers.MimeType('application', 'octet-stream')
                if fieldname is None:
                    raise MimeFormatError('Content-disposition invalid or omitted.')
                
                # End of headers, return (field name, content-type, filename)
                yield fieldname, ctype, filename; return 
            
            parts = line.split(':', 1)
            if len(parts) != 2:
                raise MimeFormatError("Header did not have a :")
            name, value = parts
            name = name.lower()

            if name == "content-type":
                ctype = http_headers.parseContentType(tokenize(value, foldCase=False))
            elif name == "content-disposition":
                fieldname, filename = parseContentDispositionFormData(value)
            else:
                # Unknown header -- ignore
                pass
    readHeaders = defer.deferredGenerator(readHeaders)
    
    def raiseError(data):
        if data:
            raise MimeFormatError("Extra data before first boundary: %r"% data)

    def discard(data):
        pass
    
    boundary = "--"+boundary
    
    d = readDataTillBoundary(write=raiseError, boundary=boundary)
    d = defer.waitForDeferred(d)
    yield d; d.getResult()
    
    boundary = "\r\n"+boundary
    
    while 1:
        # read post-boundary line data
        line = stream.readline(maxLength=1024)
        if isinstance(line, defer.Deferred):
            line = defer.waitForDeferred(line)
            yield line; line = line.getResult()
        
        if line == "--":
            # THE END!
            return
        elif line != "":
            print "EXTRA: %r" % line
            raise MimeFormatError("Unexpected data on same line as boundary.")

        try:
            x = defer.waitForDeferred(readHeaders())
            yield x; x = x.getResult()
            
            # Parse data
            fieldname, ctype, filename = x
            buf = StringIO()
            d = readDataTillBoundary(write=buf.write, boundary=boundary)
            d = defer.waitForDeferred(d)
            yield d; d.getResult()
            if cdisp is None:
                # Is a field
                args[fieldname] = str(buf)
            else:
                # Is a file upload
                files[fieldname] = (buf, ctype, filename)
                
        except ValueError, v:
            raise MimeFormatError(v)
        

            
    yield args, files
    return
parse = defer.deferredGenerator(parse)

if __name__ == '__main__':
    d = parse(FileStream(open("upload.txt")), "---------------------------011013906415445")
    from twisted.python import log
    d.addErrback(log.err)
