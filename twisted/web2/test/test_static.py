# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web2.static}.
"""

import os

from twisted.web2.test.test_server import BaseCase
from twisted.web2 import static
from twisted.web2 import http_headers
from twisted.web2 import stream
from twisted.web2 import iweb



class TestData(BaseCase):
    def setUp(self):
        self.text = "Hello, World\n"
        self.data = static.Data(self.text, "text/plain")

    def test_dataState(self):
        """
        Test the internal state of the Data object
        """
        self.assert_(hasattr(self.data, "created_time"))
        self.assertEquals(self.data.data, self.text)
        self.assertEquals(self.data.type, http_headers.MimeType("text", "plain"))
        self.assertEquals(self.data.contentType(), http_headers.MimeType("text", "plain"))


    def test_etag(self):
        """
        Test that we can get an ETag
        """
        self.failUnless(self.data.etag())


    def test_render(self):
        """
        Test that the result from Data.render is acceptable, including the
        response code, the content-type header, and the actual response body
        itself.
        """
        response = iweb.IResponse(self.data.render(None))
        self.assertEqual(response.code, 200)
        self.assert_(response.headers.hasHeader("content-type"))
        self.assertEqual(response.headers.getHeader("content-type"),
                         http_headers.MimeType("text", "plain"))
        def checkStream(data):
            self.assertEquals(str(data), self.text)
        return stream.readStream(iweb.IResponse(self.data.render(None)).stream,
                                 checkStream)



class TestFileSaver(BaseCase):
    def setUp(self):
        """
        Create an empty directory and a resource which will save uploads to
        that directory.
        """
        self.tempdir = self.mktemp()
        os.mkdir(self.tempdir)

        self.root = static.FileSaver(self.tempdir,
                              expectedFields=['FileNameOne'],
                              maxBytes=16)
        self.root.addSlash = True

    def uploadFile(self, fieldname, filename, mimetype, content, resrc=None,
                   host='foo', path='/'):
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
        return self.assertInResponse(
            self.uploadFile('FileNameOne', 'myfilename', 'text/html', 'X'*32),
            (200, {}, 'exceeds maximum length'))

    def test_enforcesMimeType(self):
        return self.assertInResponse(
            self.uploadFile('FileNameOne', 'myfilename',
                            'application/x-python', 'X'),
            (200, {}, 'type not allowed'))

    def test_invalidField(self):
        return self.assertInResponse(
            self.uploadFile('NotARealField', 'myfilename', 'text/html', 'X'),
            (200, {}, 'not a valid field'))

    def test_reportFileSave(self):
        return self.assertInResponse(
            self.uploadFile('FileNameOne', 'myfilename', 'text/plain', 'X'),
            (200, {}, 'Saved file'))

    def test_compareFileContents(self):
        def gotFname(fname):
            contents = file(fname, 'rb').read()
            self.assertEquals(contents, 'Test contents\n')

        d = self.uploadFile('FileNameOne', 'myfilename', 'text/plain',
                            'Test contents\n')
        d.addCallback(self.fileNameFromResponse)
        d.addCallback(gotFname)
        return d
