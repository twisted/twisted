import tempfile, os

from twisted.web2.test.test_server import BaseCase
from twisted.web2 import static
from twisted.web2 import http_headers
from twisted.web2 import stream

from twisted.trial import util, assertions

class TestFileSaver(BaseCase):
    def setUpClass(self):
        self.tempdir = tempfile.mkdtemp(prefix='TestFileSaver')
        
        self.root = static.FileSaver(self.tempdir,
                              expectedFields=['FileNameOne'],
                              maxBytes=10)
        self.root.addSlash = True

    def tearDownClass(self):
        os.rmdir(self.tempdir)
        
    def uploadFile(self, fieldname, filename, mimetype, content, resrc=None, host='foo', path='/'):
        if not resrc:
            resrc = self.root
            
        ctype = http_headers.MimeType('multipart', 'form-data',
                                      (('boundary', '---weeboundary'),))
        
        return self.getResponseFor(resrc, '/',
                            headers={'host': 'foo',
                                     'content-length': len(content),
                                     'content-type': ctype },
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
                assertions.failUnlessSubstring(expected_data, data)

            for key, value in expected_headers.iteritems():
                self.assertEquals(headers.getHeader(key), value)

            self.assertEquals(failed, expectedFailure)

    def assertInResponse(self, response, expected_response, failure=False):
        d = response
        d.addCallback(self._CbAssertInResponse, expected_response, failure)
        util.wait(d, timeout=self.wait_timeout)

    def testEnforcesMaxBytes(self):
        self.assertInResponse(self.uploadFile('FileNameOne', 'myfilename',
                                         'text/html', 'X'*11),
                              (200, {}, 'exceeds maximum length'))

    def testEnforcesMimeType(self):
        self.assertInResponse(self.uploadFile('FileNameOne', 'myfilename',
                                              'application/x-python', 'X'),
                              (200, {}, 'type not allowed'))

    def testInvalidField(self):
        self.assertInResponse(self.uploadFile('NotARealField', 'myfilename',
                                              'text/html', 'X'),
                              (200, {}, 'not a valid field'))

