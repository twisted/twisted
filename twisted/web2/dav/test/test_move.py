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
import md5
import shutil

from twisted.web2 import responsecode

import twisted.web2.dav.test.util
from twisted.web2.dav.test.util import SimpleRequest, serialize

class MOVE(twisted.web2.dav.test.util.TestCase):
    """
    MOVE request
    """
    # FIXME:
    # Check that properties are being moved
    def test_MOVE_create(self):
        def test(response, path, isfile, sum, uri, dst_path):
            if response.code != responsecode.CREATED:
                self.fail("Incorrect response code for MOVE %s: %s" % (uri, response.code))

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

        return serialize(self.send, self.work(test))

    def test_MOVE_exists(self):
        def test(response, path, isfile, sum, uri, dst_path):
            if response.code != responsecode.PRECONDITION_FAILED:
                self.fail("Incorrect response code for MOVE without overwrite %s: %s" % (uri, response.code))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

        return serialize(self.send, self.work(test, overwrite=False))

    def test_MOVE_overwrite(self):
        def test(response, path, isfile, sum, uri, dst_path):
            if response.code != responsecode.NO_CONTENT:
                self.fail("Incorrect response code for MOVE with overwrite %s: %s" % (uri, response.code))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

        return serialize(self.send, self.work(test, overwrite=True))

    def test_MOVE_no_parent(self):
        def test(response, path, isfile, sum, uri, dst_path):
            if response.code != responsecode.CONFLICT:
                self.fail("Incorrect response code for MOVE with no parent %s: %s" % (uri, response.code))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

        return serialize(self.send, self.work(test, dst=os.path.join(self.docroot, "elvislives!")))

    def work(self, test, overwrite=None, dst=None):
        if dst is None:
            dst = os.path.join(self.docroot, "dst")
            os.mkdir(dst)

        for basename in os.listdir(self.docroot):
            if basename == "dst": continue

            path     = os.path.join(self.docroot, basename)
            isfile   = os.path.isfile(path)
            sum      = sumFile(path)
            uri      = "/" + basename
            dst_path = os.path.join(dst, basename)
            dst_uri  = urllib.quote("/" + os.path.basename(dst) + "/" + basename)

            if not isfile: uri     += "/"
            if not isfile: dst_uri += "/"

            if overwrite is not None:
                # Create a file at dst_path to create a conflict
                file(dst_path, "w").close()

            def do_test(response, path=path, isfile=isfile, sum=sum, uri=uri, dst_path=dst_path):
                test(response, path, isfile, sum, uri, dst_path)

            request = SimpleRequest(self.site, "MOVE", uri)
            request.headers.setHeader("destination", dst_uri)
            if overwrite is not None:
                request.headers.setHeader("overwrite", overwrite)

            yield (request, do_test, path)

def sumFile(path):
    m = md5.new()

    if os.path.isfile(path):
        f = file(path)
        try:
            m.update(f.read())
        finally:
            f.close()

    elif os.path.isdir(path):
        for dir, subdirs, files in os.walk(path):
            for filename in files:
                m.update(filename)
                f = file(os.path.join(dir, filename))
                try:
                    m.update(f.read())
                finally:
                    f.close()
            for dirname in subdirs:
                m.update(dirname + "/")

    else:
        raise AssertionError()

    return m.digest()
