# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web2.fileupload} and its different parsing functions.
"""

from twisted.internet import defer
from twisted.trial import unittest
from twisted.internet.defer import waitForDeferred, deferredGenerator

from twisted.web2 import stream, fileupload
from twisted.web2.http_headers import MimeType



class TestStream(stream.SimpleStream):
    """
    A stream that reads less data at a time than it could.
    """
    def __init__(self, mem, maxReturn=1000, start=0, length=None):
        self.mem = mem
        self.start = start
        self.maxReturn = maxReturn
        if length is None:
            self.length = len(mem) - start
        else:
            if len(mem) < length:
                raise ValueError("len(mem) < start + length")
            self.length = length

    def read(self):
        if self.mem is None:
            return None
        if self.length == 0:
            result = None
        else:
            amtToRead = min(self.maxReturn, self.length)
            result = buffer(self.mem, self.start, amtToRead)
            self.length -= amtToRead
            self.start += amtToRead
        return result

    def close(self):
        self.mem = None
        stream.SimpleStream.close(self)



class MultipartTests(unittest.TestCase):
    def doTestError(self, boundary, data, expected_error):
        # Test different amounts of data at a time.
        ds = [fileupload.parseMultipartFormData(TestStream(data,
                                                           maxReturn=bytes),
                                                boundary)
              for bytes in range(1, 20)]
        d = defer.DeferredList(ds, consumeErrors=True)
        d.addCallback(self._assertFailures, expected_error)
        return d

    def _assertFailures(self, failures, *expectedFailures):
        for flag, failure in failures:
            self.failUnlessEqual(flag, defer.FAILURE)
            failure.trap(*expectedFailures)

    def doTest(self, boundary, data, expected_args, expected_files):
        #import time, gc, cgi, cStringIO
        for bytes in range(1, 20):
            #s = TestStream(data, maxReturn=bytes)
            s = stream.IStream(data)
            #t=time.time()
            d = waitForDeferred(fileupload.parseMultipartFormData(s, boundary))
            yield d; args, files = d.getResult()
            #e=time.time()
            #print "%.2g"%(e-t)
            self.assertEquals(args, expected_args)

            # Read file data back into memory to compare.
            out = {}
            for name, l in files.items():
                out[name] = [(filename, ctype, f.read()) for (filename, ctype, f) in l]
            self.assertEquals(out, expected_files)

        #data=cStringIO.StringIO(data)
        #t=time.time()
        #d=cgi.parse_multipart(data, {'boundary':boundary})
        #e=time.time()
        #print "CGI: %.2g"%(e-t)
    doTest = deferredGenerator(doTest)

    def testNormalUpload(self):
        return self.doTest(
            '---------------------------155781040421463194511908194298',
"""-----------------------------155781040421463194511908194298\r
Content-Disposition: form-data; name="foo"\r
\r
Foo Bar\r
-----------------------------155781040421463194511908194298\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/html\r
\r
Contents of a file
blah
blah\r
-----------------------------155781040421463194511908194298--\r
""",
            {'foo':['Foo Bar']},
            {'file':[('filename', MimeType('text', 'html'),
                      "Contents of a file\nblah\nblah")]})

    def testMultipleUpload(self):
        return self.doTest(
            'xyz',
"""--xyz\r
Content-Disposition: form-data; name="foo"\r
\r
Foo Bar\r
--xyz\r
Content-Disposition: form-data; name="foo"\r
\r
Baz\r
--xyz\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/html\r
\r
blah\r
--xyz\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/plain\r
\r
bleh\r
--xyz--\r
""",
            {'foo':['Foo Bar', 'Baz']},
            {'file':[('filename', MimeType('text', 'html'), "blah"),
                     ('filename', MimeType('text', 'plain'), "bleh")]})


    def testStupidFilename(self):
        return self.doTest(
            '----------0xKhTmLbOuNdArY',
"""------------0xKhTmLbOuNdArY\r
Content-Disposition: form-data; name="file"; filename="foo"; name="foobar.txt"\r
Content-Type: text/plain\r
\r
Contents of a file
blah
blah\r
------------0xKhTmLbOuNdArY--\r
""",
            {},
            {'file':[('foo"; name="foobar.txt', MimeType('text', 'plain'),
                      "Contents of a file\nblah\nblah")]})


    def testEmptyFilename(self):
        return self.doTest(
            'curlPYafCMnsamUw9kSkJJkSen41sAV',
"""--curlPYafCMnsamUw9kSkJJkSen41sAV\r
cONTENT-tYPE: application/octet-stream\r
cONTENT-dISPOSITION: FORM-DATA; NAME="foo"; FILENAME=""\r
\r
qwertyuiop\r
--curlPYafCMnsamUw9kSkJJkSen41sAV--\r
""",
            {},
            {'foo':[('', MimeType('application', 'octet-stream'),
                     "qwertyuiop")]})


# Failing parses
    def testMissingContentDisposition(self):
        return self.doTestError(
            '----------0xKhTmLbOuNdArY',
"""------------0xKhTmLbOuNdArY\r
Content-Type: text/html\r
\r
Blah blah I am a stupid webbrowser\r
------------0xKhTmLbOuNdArY--\r
""",
            fileupload.MimeFormatError)


    def testRandomData(self):
        return self.doTestError(
            'boundary',
"""--sdkjsadjlfjlj skjsfdkljsd
sfdkjsfdlkjhsfadklj sffkj""",
            fileupload.MimeFormatError)


    def test_tooBigUpload(self):
        """
        Test that a too big form post fails.
        """
        boundary = '---------------------------155781040421463194511908194298'
        data = """-----------------------------155781040421463194511908194298\r
Content-Disposition: form-data; name="foo"\r
\r
Foo Bar\r
-----------------------------155781040421463194511908194298\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/html\r
\r
Contents of a file
blah
blah\r
-----------------------------155781040421463194511908194298--\r
"""
        s = stream.IStream(data)
        return self.assertFailure(
            fileupload.parseMultipartFormData(s, boundary, maxSize=200),
            fileupload.MimeFormatError)


    def test_tooManyFields(self):
        """
        Test when breaking the maximum number of fields.
        """
        boundary = 'xyz'
        data = """--xyz\r
Content-Disposition: form-data; name="foo"\r
\r
Foo Bar\r
--xyz\r
Content-Disposition: form-data; name="foo"\r
\r
Baz\r
--xyz\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/html\r
\r
blah\r
--xyz\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/plain\r
\r
bleh\r
--xyz--\r
"""
        s = stream.IStream(data)
        return self.assertFailure(
            fileupload.parseMultipartFormData(s, boundary, maxFields=3),
            fileupload.MimeFormatError)


    def test_maxMem(self):
        """
        An attachment with no filename goes to memory: check that the
        C{maxMem} parameter limits the size of this kind of attachment.
        """
        boundary = '---------------------------155781040421463194511908194298'
        data = """-----------------------------155781040421463194511908194298\r
Content-Disposition: form-data; name="foo"\r
\r
Foo Bar and more content\r
-----------------------------155781040421463194511908194298\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/html\r
\r
Contents of a file
blah
blah\r
-----------------------------155781040421463194511908194298--\r
"""
        s = stream.IStream(data)
        return self.assertFailure(
            fileupload.parseMultipartFormData(s, boundary, maxMem=10),
            fileupload.MimeFormatError)



class TestURLEncoded(unittest.TestCase):
    def doTest(self, data, expected_args):
        for bytes in range(1, 20):
            s = TestStream(data, maxReturn=bytes)
            d = waitForDeferred(fileupload.parse_urlencoded(s))
            yield d; args = d.getResult()
            self.assertEquals(args, expected_args)
    doTest = deferredGenerator(doTest)


    def test_parseValid(self):
        self.doTest("a=b&c=d&c=e", {'a':['b'], 'c':['d', 'e']})
        self.doTest("a=b&c=d&c=e", {'a':['b'], 'c':['d', 'e']})
        self.doTest("a=b+c%20d", {'a':['b c d']})


    def test_parseInvalid(self):
        self.doTest("a&b=c", {'b':['c']})
