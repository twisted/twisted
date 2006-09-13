##
# Copyright (c) 2005 Apple Computer, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# DRI: Wilfredo Sanchez, wsanchez@apple.com
##

import os

from twisted.web2 import responsecode
from twisted.web2.iweb import IResponse
from twisted.web2.stream import MemoryStream
from twisted.web2.dav.fileop import rmdir
from twisted.web2.test.test_server import SimpleRequest
import twisted.web2.dav.test.util

class MKCOL(twisted.web2.dav.test.util.TestCase):
    """
    MKCOL request
    """
    # FIXME:
    # Try in nonexistant parent collection.
    # Try on existing resource.
    # Try with request body?
    def test_MKCOL(self):
        """
        MKCOL request
        """
        path, uri = self.mkdtemp("collection")

        rmdir(path)

        def check_result(response):
            response = IResponse(response)

            if response.code != responsecode.CREATED:
                self.fail("MKCOL response %s != %s" % (response.code, responsecode.CREATED))

            if not os.path.isdir(path):
                self.fail("MKCOL did not create directory %s" % (path,))

        request = SimpleRequest(self.site, "MKCOL", uri)

        return self.send(request, check_result)

    def test_MKCOL_invalid_body(self):
        """
        MKCOL request with invalid request body
        (Any body at all is invalid in our implementation; there is no
        such thing as a valid body.)
        """
        path, uri = self.mkdtemp("collection")

        rmdir(path)

        def check_result(response):
            response = IResponse(response)

            if response.code != responsecode.UNSUPPORTED_MEDIA_TYPE:
                self.fail("MKCOL response %s != %s" % (response.code, responsecode.UNSUPPORTED_MEDIA_TYPE))

            if os.path.isdir(path):
                self.fail("MKCOL incorrectly created directory %s" % (path,))

        request = SimpleRequest(self.site, "MKCOL", uri)
        request.stream = MemoryStream("This is not a valid MKCOL request body.")

        return self.send(request, check_result)
