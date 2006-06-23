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

from twisted.web2.iweb import IResponse

import twisted.web2.dav.test.util
from twisted.web2.test.test_server import SimpleRequest

class OPTIONS(twisted.web2.dav.test.util.TestCase):
    """
    OPTIONS request
    """
    def test_DAV1(self):
        """
        DAV level 1
        """
        return self._test_level("1")

    def test_DAV2(self):
        """
        DAV level 2
        """
        return self._test_level("2")

    test_DAV2.todo = "DAV level 2 unimplemented"

    def _test_level(self, level):
        def doTest(response):
            response = IResponse(response)

            dav = response.headers.getHeader("dav")
            if not dav: self.fail("no DAV header: %s" % (response.headers,))
            self.assertIn(level, dav, "no DAV level %s header" % (level,))

            return response

        return self.send(SimpleRequest(self.site, "OPTIONS", "/"), doTest)
