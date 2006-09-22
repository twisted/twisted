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

import twisted.web2.dav.test.util
from twisted.web2 import responsecode
from twisted.web2.test.test_server import SimpleRequest
from twisted.web2.dav.test.util import dircmp, serialize
from twisted.web2.dav.fileop import rmdir

class COPY(twisted.web2.dav.test.util.TestCase):
    """
    COPY request
    """
    # FIXME:
    # Check that properties are being copied
    def test_COPY_create(self):
        """
        COPY to new resource.
        """
        def test(response, path, isfile, sum, uri, depth, dst_path):
            if response.code != responsecode.CREATED:
                self.fail("Incorrect response code for COPY %s (depth=%r): %s != %s"
                          % (uri, depth, response.code, responsecode.CREATED))

            if response.headers.getHeader("location") is None:
                self.fail("Reponse to COPY %s (depth=%r) with CREATE status is missing location: header."
                          % (uri, depth))

            if os.path.isfile(path):
                if not os.path.isfile(dst_path):
                    self.fail("COPY %s (depth=%r) produced no output file" % (uri, depth))
                if not cmp(path, dst_path):
                    self.fail("COPY %s (depth=%r) produced different file" % (uri, depth))
                os.remove(dst_path)

            elif os.path.isdir(path):
                if not os.path.isdir(dst_path):
                    self.fail("COPY %s (depth=%r) produced no output directory" % (uri, depth))

                if depth in ("infinity", None):
                    if dircmp(path, dst_path):
                        self.fail("COPY %s (depth=%r) produced different directory" % (uri, depth))

                elif depth == "0":
                    for filename in os.listdir(dst_path):
                        self.fail("COPY %s (depth=%r) shouldn't copy directory contents (eg. %s)" % (uri, depth, filename))

                else: raise AssertionError("Unknown depth: %r" % (depth,))

                rmdir(dst_path)

            else:
                self.fail("Source %s is neither a file nor a directory"
                          % (path,))

        return serialize(self.send, work(self, test))

    def test_COPY_exists(self):
        """
        COPY to existing resource.
        """
        def test(response, path, isfile, sum, uri, depth, dst_path):
            if response.code != responsecode.PRECONDITION_FAILED:
                self.fail("Incorrect response code for COPY without overwrite %s: %s != %s"
                          % (uri, response.code, responsecode.PRECONDITION_FAILED))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

        return serialize(self.send, work(self, test, overwrite=False))

    def test_COPY_overwrite(self):
        """
        COPY to existing resource with overwrite header.
        """
        def test(response, path, isfile, sum, uri, depth, dst_path):
            if response.code != responsecode.NO_CONTENT:
                self.fail("Incorrect response code for COPY with overwrite %s: %s != %s"
                          % (uri, response.code, responsecode.NO_CONTENT))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

            self.failUnless(os.path.exists(dst_path), "COPY didn't produce file: %s" % (dst_path,))

        return serialize(self.send, work(self, test, overwrite=True))

    def test_COPY_no_parent(self):
        """
        COPY to resource with no parent.
        """
        def test(response, path, isfile, sum, uri, depth, dst_path):
            if response.code != responsecode.CONFLICT:
                self.fail("Incorrect response code for COPY with no parent %s: %s != %s"
                          % (uri, response.code, responsecode.CONFLICT))
            else:
                # FIXME: Check XML error code (2518bis)
                pass

        return serialize(self.send, work(self, test, dst=os.path.join(self.docroot, "elvislives!")))

def work(self, test, overwrite=None, dst=None, depths=("0", "infinity", None)):
    if dst is None:
        dst = os.path.join(self.docroot, "dst")
        os.mkdir(dst)

    for basename in os.listdir(self.docroot):
        if basename == "dst": continue

        path = os.path.join(self.docroot, basename)
        uri = "/" + basename
        isfile = os.path.isfile(path)
        sum = sumFile(path)
        basename = os.path.basename(path)
        dst_path = os.path.join(dst, basename)
        dst_uri = urllib.quote("/dst/" + basename)

        if not isfile:
            uri     += "/"
            dst_uri += "/"

        if overwrite is not None:
            # Create a file at dst_path to create a conflict
            file(dst_path, "w").close()

        for depth in depths:
            def do_test(response, path=path, isfile=isfile, sum=sum, uri=uri, depth=depth, dst_path=dst_path):
                test(response, path, isfile, sum, uri, depth, dst_path)

            request = SimpleRequest(self.site, self.__class__.__name__, uri)
            request.headers.setHeader("destination", dst_uri)
            if depth is not None:
                request.headers.setHeader("depth", depth)
            if overwrite is not None:
                request.headers.setHeader("overwrite", overwrite)

            yield (request, do_test)

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
