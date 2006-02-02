import os

from twisted.web2.test.test_server import BaseCase
from twisted.web2 import static
from twisted.web2 import http_headers
from twisted.web2 import stream
from twisted.web2 import iweb

class TestData(BaseCase):
    def test_data(self):
        text = "Hello, World\n"
        data = static.Data(text, "text/plain")

        self.assertEquals(data.data, text)
        self.assertEquals(data.type, http_headers.MimeType("text", "plain"))
        self.assertEquals(data.contentType(), http_headers.MimeType("text", "plain"))
        self.failUnless(data.etag())

        def checkStream(data):
            self.assertEquals(str(data), text)

        return stream.readStream(iweb.IResponse(data.render(None)).stream, checkStream)

class TestFileSaver(BaseCase):
    def setUpClass(self):
        self.tempdir = self.mktemp()
        os.mkdir(self.tempdir)
        
        self.root = static.FileSaver(self.tempdir,
                              expectedFields=['FileNameOne'],
                              maxBytes=16)
        self.root.addSlash = True

    def uploadFile(self, fieldname, filename, mimetype, content, resrc=None, host='foo', path='/'):
        if not resrc:
            resrc = self.root
            
        ctype = http_headers.MimeType('multipart', 'form-data',
                                      (('boundary', '---weeboundary'),))
        
        return self.getResponseFor(resrc, '/',
                            headers={'host': 'foo',
                                     'content-type': ctype },
                            length=len(content),
                            method='POST',
                            content="""-----weeboundary\r
Content-Disposition: form-data; name="%s"; filename="%s"\r
Content-Type: %s\r
\r
%s\r
-----weeboundary--\r
""" % (fieldname, filename, mimetype, content))

    def _CbAssertInResponse(self, (code, headers, data, failed),
                            expected_response, expectedFailure=False):
        
        expected_code, expected_headers, expected_data = expected_response
        self.assertEquals(code, expected_code)
        
        if expected_data is not None:
            self.failUnlessSubstring(expected_data, data)

        for key, value in expected_headers.iteritems():
            self.assertEquals(headers.getHeader(key), value)

        self.assertEquals(failed, expectedFailure)

    def fileNameFromResponse(self, response):
        (code, headers, data, failure) = response
        return data[data.index('Saved file')+11:data.index('<br />')]

    def assertInResponse(self, response, expected_response, failure=False):
        d = response
        d.addCallback(self._CbAssertInResponse, expected_response, failure)
        return d

    def test_enforcesMaxBytes(self):
        return self.assertInResponse(self.uploadFile('FileNameOne', 'myfilename',
                                         'text/html', 'X'*32),
                              (200, {}, 'exceeds maximum length'))

    def test_enforcesMimeType(self):
        return self.assertInResponse(self.uploadFile('FileNameOne', 'myfilename',
                                              'application/x-python', 'X'),
                              (200, {}, 'type not allowed'))

    def test_invalidField(self):
        return self.assertInResponse(self.uploadFile('NotARealField', 'myfilename',
                                              'text/html', 'X'),
                              (200, {}, 'not a valid field'))

    def test_reportFileSave(self):
        return self.assertInResponse(self.uploadFile('FileNameOne', 'myfilename',
                                              'text/plain',
                                              'X'),
                              (200, {}, 'Saved file'))

    def test_compareFileContents(self):
        def gotFname(fname):
            contents = file(fname, 'r').read()
            self.assertEquals(contents, 'Test contents')
        
        return self.uploadFile('FileNameOne', 'myfilename', 'text/plain',
                               'Test contents').addCallback(
            self.fileNameFromResponse
            ).addCallback(gotFname)
