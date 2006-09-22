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

import twisted.web2.dav.test.util
import twisted.web2.dav.test.test_copy
from twisted.web2.dav.test.util import serialize
from twisted.web2.dav.test.test_copy import sumFile

class MOVE(twisted.web2.dav.test.util.TestCase):
    """
    MOVE request
    """
    # FIXME:
    # Check that properties are being moved
    def test_MOVE_create(self):
        """
        MOVE to new resource.
        """
        def test(response, path, isfile, sum, uri, depth, dst_path):
            if response.code != responsecode.CREATED:
                self.fail("Incorrect response code for MOVE %s: %s != %s"
                          % (uri, response.code, responsecode.CREATED))

            if response.headers.getHeader("location") is None:
                self.fail("Reponse to MOVE %s with CREATE status is missing location: header."
                          % (uri,))

            if isfile:
                if not os.path.isfile(dst_path):
                    self.fail("MOVE %s produced no output file" % (uri,))
                if sum != sumFile(dst_path):
                    self.fail("MOVE %s produced different file" % (uri,))
            else:
                if not os.path.isdir(dst_path):
                    self.fail("MOVE %s produced no output directory" % (uri,))
                if sum != sumFile(dst_path):
                    self.fail("isdir %s produced different directory" % (uri,))

        return serialize(self.send, work(self, test))

    def test_MOVE_exists(self):
        """
        MOVE to existing resource.
        """
        def test(response, path, isfile, sum, uri, depth, dst_path):
            if response.code != responsecode.PRECONDITION_FAILED:
                self.fail("Incorrect response code for MOVE without overwrite %s: %s != %s"
                          % (uri, response.code, responsecode.PRECONDITION_FAILED))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

        return serialize(self.send, work(self, test, overwrite=False))

    def test_MOVE_overwrite(self):
        """
        MOVE to existing resource with overwrite header.
        """
        def test(response, path, isfile, sum, uri, depth, dst_path):
            if response.code != responsecode.NO_CONTENT:
                self.fail("Incorrect response code for MOVE with overwrite %s: %s != %s"
                          % (uri, response.code, responsecode.NO_CONTENT))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

        return serialize(self.send, work(self, test, overwrite=True))

    def test_MOVE_no_parent(self):
        """
        MOVE to resource with no parent.
        """
        def test(response, path, isfile, sum, uri, depth, dst_path):
            if response.code != responsecode.CONFLICT:
                self.fail("Incorrect response code for MOVE with no parent %s: %s != %s"
                          % (uri, response.code, responsecode.CONFLICT))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

        return serialize(self.send, work(self, test, dst=os.path.join(self.docroot, "elvislives!")))

def work(self, test, overwrite=None, dst=None):
    return twisted.web2.dav.test.test_copy.work(self, test, overwrite, dst, depths=(None,))
