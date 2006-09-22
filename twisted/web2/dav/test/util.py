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
from urllib import quote as url_quote
from filecmp import dircmp as DirCompare
from tempfile import mkdtemp
from shutil import copy
from random import randrange, choice

from twisted.python import log
from twisted.trial import unittest
from twisted.internet.defer import Deferred
from twisted.web2.dav.fileop import rmdir
from twisted.web2.dav.util import joinURL
from twisted.web2.dav.static import DAVFile

class TodoTest(Exception):
    pass

class TestCase(unittest.TestCase):
    docroot = property(lambda(self): self.site.resource.fp.path)

    resource_class = DAVFile

    def setUp(self):
        log.msg("Setting up %s" % (self.__class__,))

        docroot = self.mktemp()
        os.mkdir(docroot)

        dirs = (
            os.path.join(docroot, "dir1"),
            os.path.join(docroot, "dir2"),
            os.path.join(docroot, "dir2", "subdir1"),
            os.path.join(docroot, "dir3"),
            os.path.join(docroot, "dir4"),
            os.path.join(docroot, "dir4", "subdir1"),
            os.path.join(docroot, "dir4", "subdir1", "subsubdir1"),
            os.path.join(docroot, "dir4", "subdir2"),
            os.path.join(docroot, "dir4", "subdir2", "dir1"),
            os.path.join(docroot, "dir4", "subdir2", "dir2"),
        )
    
        for dir in dirs: os.mkdir(dir)

        src = os.path.dirname(__file__)
        files = [
            os.path.join(src, f)
            for f in os.listdir(src)
            if os.path.isfile(os.path.join(src, f))
        ]
    
        dc = randrange(len(dirs))
        while dc:
            dc -= 1
            dir = choice(dirs)
            fc = randrange(len(files))
            while fc:
                fc -= 1
                copy(choice(files), dir)

        for path in files[:8]:
            copy(path, docroot)
    
        self.site = Site(self.resource_class(docroot))

    def tearDown(self):
        log.msg("Tearing down %s" % (self.__class__,))
        rmdir(self.docroot)

    def mkdtemp(self, prefix):
        """
        Creates a new directory in the document root and returns its path and
        URI.
        """
        path = mkdtemp(prefix=prefix + "_", dir=self.docroot)
        uri  = joinURL("/", url_quote(os.path.basename(path))) + "/"

        return (path, uri)

    def send(self, request, callback):
        log.msg("Sending %s request for URI %s" % (request.method, request.uri))

        d = request.locateResource(request.uri)
        d.addCallback(lambda resource: resource.renderHTTP(request))
        d.addCallback(request._cbFinishRender)

        if type(callback) is tuple:
            d.addCallbacks(*callback)
        else:
            d.addCallback(callback)

        return d

    def _ebDeferTestMethod(self, f, result):
        if f.check(TodoTest):
            result.addExpectedFailure(self, f, unittest.makeTodo(f.getErrorMessage()))
        else:
            return unittest.TestCase._ebDeferTestMethod(self, f, result)

class Site:
    # FIXME: There is no ISite interface; there should be.
    # implements(ISite)

    def __init__(self, resource):
        self.resource = resource

def dircmp(dir1, dir2):
    dc = DirCompare(dir1, dir2)
    return bool(
        dc.left_only or dc.right_only or
        dc.diff_files or
        dc.common_funny or dc.funny_files
    )

def serialize(f, work):
    d = Deferred()

    def oops(error):
        d.errback(error)

    def do_serialize(_):
        try:
            args = work.next()
        except StopIteration:
            d.callback(None)
        else:
            r = f(*args)
            r.addCallback(do_serialize)
            r.addErrback(oops)

    do_serialize(None)

    return d
