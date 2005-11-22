from __future__ import generators
import struct
import zlib
from twisted.web2 import stream

# TODO: ungzip (can any browsers actually generate gzipped
# upload data?) But it's necessary for client anyways.

def gzipStream(input, compressLevel=6):
    crc, size = zlib.crc32(''), 0
    # magic header, compression method, no flags
    header = '\037\213\010\000'
    # timestamp
    header += struct.pack('<L', 0)
    # uh.. stuff
    header += '\002\377'
    yield header
    
    compress = zlib.compressobj(compressLevel, zlib.DEFLATED, -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0)
    _compress = compress.compress
    _crc32 = zlib.crc32
    
    yield input.wait
    for buf in input:
        if len(buf) != 0:
            crc = _crc32(buf, crc)
            size += len(buf)
            yield _compress(buf)
        yield input.wait
    
    yield compress.flush()
    yield struct.pack('<LL', crc & 0xFFFFFFFFL, size & 0xFFFFFFFFL)
gzipStream=stream.generatorToStream(gzipStream)

def deflateStream(input, compressLevel=6):
    # NOTE: this produces RFC-conformant but some-browser-incompatible output.
    # The RFC says that you're supposed to output zlib-format data, but many
    # browsers expect raw deflate output. Luckily all those browsers support
    # gzip, also, so they won't even see deflate output. 
    compress = zlib.compressobj(compressLevel, zlib.DEFLATED, zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0)
    _compress = compress.compress
    yield input.wait
    for buf in input:
        if len(buf) != 0:
            yield _compress(buf)
        yield input.wait

    yield compress.flush()
deflateStream=stream.generatorToStream(deflateStream)

def gzipfilter(request, response):
    if response.stream is None or response.headers.getHeader('content-encoding'):
        # Empty stream, or already compressed.
        return response
    
    # FIXME: make this a more flexible matching scheme
    mimetype = response.headers.getHeader('content-type')
    if not mimetype or mimetype.mediaType != 'text':
        return response
    
    # Make sure to note we're going to return different content depending on
    # the accept-encoding header.
    vary = response.headers.getHeader('vary', [])
    if 'accept-encoding' not in vary:
        response.headers.setHeader('vary', vary+['accept-encoding'])
    
    ae = request.headers.getHeader('accept-encoding', {})
    compressor = None
    # Always prefer gzip over deflate no matter what their q-values are.
    if ae.get('gzip', 0):
        response.stream = gzipStream(response.stream)
        response.headers.setHeader('content-encoding', ['gzip'])
    elif ae.get('deflate', 0):
        response.stream = deflateStream(response.stream)
        response.headers.setHeader('content-encoding', ['deflate'])
    
    return response

__all__ = ['gzipfilter']
