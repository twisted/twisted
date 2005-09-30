from twisted.trial import unittest
import os
from twisted.web import static

class FakeRequest:
    method = 'GET'

    _headers = None
    _setHeaders = None
    _written = ''

    def __init__(self):
        self._headers = {}
        self._setHeaders = {}

    def getHeader(self, k):
        if self._headers is None:
            return None
        return self._headers.get(k)

    def setHeader(self, k, v):
        self._setHeaders.setdefault(k, []).append(v)

    def setLastModified(self, x):
        pass
    def registerProducer(self, producer, x):
        producer.resumeProducing()
    def unregisterProducer(self):
        pass
    def finish(self):
        pass

    def write(self, data):
        self._written = self._written + data

class Range(unittest.TestCase):
    todo = (unittest.FailTest, 'No range support yet.')

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        name = os.path.join(self.tmpdir, 'junk')
        f = file(name, 'w')
        f.write(8000 * 'x')
        f.close()
        self.file = static.File(name)
        self.request = FakeRequest()

    def testBodyLength(self):
        self.request._headers['range'] = 'bytes=0-1999'
        self.file.render(self.request)
        self.assertEquals(len(self.request._written), 2000)

    def testContentLength(self):
        """Content-Length of a request is correct."""
        self.request._headers['range'] = 'bytes=0-1999'
        self.file.render(self.request)
        self.assertEquals(self.request._setHeaders['content-length'], ['2000'])

    def testContentRange(self):
        """Content-Range of a request is correct."""
        self.request._headers['range'] = 'bytes=0-1999'
        self.file.render(self.request)
        self.assertEquals(self.request._setHeaders.get('content-range'), ['bytes 0-1999/8000'])
