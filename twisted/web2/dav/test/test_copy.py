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
import shutil

from twisted.internet.defer import Deferred
from twisted.web2 import responsecode
from twisted.web2.iweb import IResponse

import twisted.web2.dav.test.util
from twisted.web2.dav.test.util import SimpleRequest, dircmp, serialize
from twisted.web2.dav.fileop import rmdir
from twisted.web2.dav.util import joinURL

class COPY(twisted.web2.dav.test.util.TestCase):
    """
    COPY request
    """
    # FIXME:
    # Check that properties are being copied
    # Check overwrite header
    # Try in nonexistant parent collection.
    def test_COPY(self):
        """
        COPY request
        """
        dst = os.path.join(self.docroot, "dst")
        os.mkdir(dst)

        def check_result(response, path, uri, depth, dst_path):
            # FIXME: I can't figure out how these files are getting here;
            # the next line shouldn't be necessary, but somehow is.
            if path.startswith(dst): return

            if os.path.isfile(path):
                if not os.path.isfile(dst_path):
                    self.fail("COPY %s (depth=%r) produced no output file"
                              % (uri, depth))
                if not cmp(path, dst_path):
                    self.fail("COPY %s (depth=%r) produced different file"
                              % (uri, depth))
                os.remove(dst_path)

            elif os.path.isdir(path):
                if not os.path.isdir(dst_path):
                    self.fail("COPY %s (depth=%r) produced no output directory"
                              % (uri, depth))

                if depth in ("infinity", None):
                    if dircmp(path, dst_path):
                        self.fail("COPY %s (depth=%r) produced different directory"
                                  % (uri, depth))

                elif depth == "0":
                    for filename in os.listdir(dst_path):
                        self.fail("COPY %s (depth=%r) shouldn't copy directory contents (eg. %s)"
                                  % (uri, depth, filename))

                else: raise AssertionError("Unknown depth: %r" % (depth,))

                rmdir(dst_path)

            else:
                self.fail("Source %s is neither a file nor a directory"
                          % (path,))

        #
        # We need to serialize these request & test iterations because they can
        # interfere with each other.
        #
        def work():
            for path, uri in self.list():
                # Avoid infinite loop
                if path.startswith(dst): continue
    
                basename = os.path.basename(path)
                dst_path = os.path.join(dst, basename)
                dst_uri  = urllib.quote("/dst/" + basename)
    
                for depth in ("0", "infinity", None):
                    def do_test(response, path=path, uri=uri, depth=depth, dst_path=dst_path):
                        check_result(response, path, uri, depth, dst_path)

                    request = SimpleRequest(self.site, "COPY", uri)
                    request.headers.setHeader("destination", dst_uri)
                    if depth is not None:
                        request.headers.setHeader("depth", depth)

                    yield (request, do_test, path)

        return serialize(self.send, work())

    def test_COPY_resource(self):
        """
        Copy a non-collection resource
        """
        base_dir, base_uri = self.mkdtemp("copy_resource")
        src_path = os.path.join(base_dir, "src")
        dst_path = os.path.join(base_dir, "dst")
        src_uri = joinURL(base_uri, "src")
        dst_uri = joinURL(base_uri, "dst")

        shutil.copy(__file__, src_path)

        request = SimpleRequest(self.site, "COPY", src_uri)
        request.headers.setHeader("destination", dst_uri)

        def work():
            def do_test(response, code):
                if not cmp(src_path, dst_path):
                    self.fail("COPY produced different file")

                response = IResponse(response)

                if response.code != code:
                    self.fail("COPY response %s != %s" % (response.code, code))

            def do_test_create(response):
                return do_test(response, responsecode.CREATED)

            def do_test_replace(response):
                return do_test(response, responsecode.NO_CONTENT)

            return iter((
                (self.send, request, do_test_create, src_path),
                (self.send, request, do_test_replace, src_path),
            ))

        def dispatch(*args):
            f = args[0]
            return f(*args[1:])

        return serialize(dispatch, work())
