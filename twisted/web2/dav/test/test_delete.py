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
import urllib
import random

from twisted.web2 import responsecode
from twisted.web2.iweb import IResponse
from twisted.web2.test.test_server import SimpleRequest
from twisted.web2.dav.test.util import serialize
import twisted.web2.dav.test.util

class DELETE(twisted.web2.dav.test.util.TestCase):
    """
    DELETE request
    """
    # FIXME:
    # Try setting unwriteable perms on file, then delete
    # Try check response XML for error in some but not all files

    def test_DELETE(self):
        """
        DELETE request
        """
        def check_result(response, path):
            response = IResponse(response)

            if response.code != responsecode.NO_CONTENT:
                self.fail("DELETE response %s != %s" % (response.code, responsecode.NO_CONTENT))

            if os.path.exists(path):
                self.fail("DELETE did not remove path %s" % (path,))

        def work():
            for filename in os.listdir(self.docroot):
                path = os.path.join(self.docroot, filename)
                uri = urllib.quote("/" + filename)

                if os.path.isdir(path): uri = uri + "/"

                def do_test(response, path=path):
                    return check_result(response, path)

                request = SimpleRequest(self.site, "DELETE", uri)

                depth = random.choice(("infinity", None))
                if depth is not None:
                    request.headers.setHeader("depth", depth)

                yield (request, do_test)

        return serialize(self.send, work())
