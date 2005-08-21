try:
    from twisted.web import http
except ImportError:
    from twisted.protocols import http
from twisted.web2.stream import IByteStream, StreamProducer, substream
from nevow import inevow, static
from twisted.python import reflect

from twisted.internet import error as ti_error

from zope.interface import implements

class WebStreamProducer(StreamProducer):
    def __init__(self, stream, request):
        StreamProducer.__init__(self, stream)
        self.consumer = request
        self.request = request

    def stopProducing(self, failure=ti_error.ConnectionLost()):
        StreamProducer.stopProducing(self, failure)
        self.request.finish()

def getByteRange(ctx):
    request = inevow.IRequest(ctx)
    byteRange = request.getHeader('range')
    if byteRange is None:
        return None
    byteRange = byteRange.split('=')
    assert byteRange[0] == 'bytes', "Invalid syntax in range header!"
    start, end = byteRange[1].split('-')
    start = start and int(start) or ''
    end = end and int(end) or ''
    return start, end

class Stream(object):
    implements(inevow.IResource)

    def __init__(self, stream, mimeType):
        self.stream = IByteStream(stream)
        self.mimeType = mimeType
        self._dataRead = 0

    def renderHTTP(self, ctx):
        request = inevow.IRequest(ctx)
        request.setHeader('accept-ranges', 'bytes')
        request.setHeader('content-type', self.mimeType)
        fsize = self.size = self.stream.length
        byteRange = getByteRange(ctx)
        if byteRange:
            start, end = byteRange
            if start and end:
                self.stream = substream(self.stream, int(start), int(end))
            request.setResponseCode(http.PARTIAL_CONTENT)
            request.setHeader('content-range',"bytes %s-%s/%s" % (
                str(start), str(end), str(fsize)))
            self.size = 1 + end - int(start)
        request.setHeader('content-length', str(self.size))
        if request.method == 'HEAD':
            return ''

        producer = WebStreamProducer(self.stream, request)
        request.registerProducer(producer, 0)
        return request.deferred
