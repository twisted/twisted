# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.static}.
"""

import os, re, StringIO

from zope.interface.verify import verifyClass, verifyObject

from twisted.internet import abstract, interfaces
from twisted.python.runtime import platform
from twisted.python.filepath import FilePath, IFilePath, InsecurePath
from twisted.python import log, components
from twisted.trial.unittest import TestCase
from twisted.web import static, http, script, resource, util
from twisted.web.server import UnsupportedMethod
from twisted.web.test.requesthelper import (
    DummyRequest, DummyRequestHead, DummyRequestPost,
    requestFromUrl)
from twisted.web.test._util import _render


class StaticDataTests(TestCase):
    """
    Tests for L{Data}.
    """
    def test_headRequest(self):
        """
        L{Data.render} returns an empty response body for a I{HEAD} request.
        """
        data = static.Data("foo", "bar")
        request = DummyRequest([''])
        request.method = 'HEAD'
        d = _render(data, request)
        def cbRendered(ignored):
            self.assertEqual(''.join(request.written), "")
        d.addCallback(cbRendered)
        return d


    def test_invalidMethod(self):
        """
        L{Data.render} raises L{UnsupportedMethod} in response to a non-I{GET},
        non-I{HEAD} request.
        """
        data = static.Data("foo", "bar")
        request = DummyRequest([''])
        request.method = 'POST'
        self.assertRaises(UnsupportedMethod, data.render, request)



class StaticFileTests(TestCase):
    """
    Tests for the basic behavior of L{File}.
    """
    def _render(self, resource, request):
        return _render(resource, request)


    def test_invalidMethod(self):
        """
        L{File.render} raises L{UnsupportedMethod} in response to a non-I{GET},
        non-I{HEAD} request.
        """
        request = DummyRequest([''])
        request.method = 'POST'
        path = FilePath(self.mktemp())
        path.setContent("foo")
        file = static.File(path.path)
        self.assertRaises(UnsupportedMethod, file.render, request)


    def test_notFound(self):
        """
        If a request is made which encounters a L{File} before a final segment
        which does not correspond to any file in the path the L{File} was
        created with, a not found response is sent.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        file = static.File(base.path)

        request = DummyRequest(['foobar'])
        child = resource.getChildForRequest(file, request)

        d = self._render(child, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, 404)
        d.addCallback(cbRendered)
        return d


    def test_emptyChild(self):
        """
        The C{''} child of a L{File} which corresponds to a directory in the
        filesystem is a L{DirectoryLister}.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        file = static.File(base.path)

        request = DummyRequest([''])
        child = resource.getChildForRequest(file, request)
        self.assertIsInstance(child, static.DirectoryLister)
        self.assertEqual(child.path, base.path)


    def test_securityViolationNotFound(self):
        """
        If a request is made which encounters a L{File} before a final segment
        which cannot be looked up in the filesystem due to security
        considerations, a not found response is sent.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        file = static.File(base.path)

        request = DummyRequest(['..'])
        child = resource.getChildForRequest(file, request)

        d = self._render(child, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, 404)
        d.addCallback(cbRendered)
        return d


    def test_forbiddenResource(self):
        """
        If the file in the filesystem which would satisfy a request cannot be
        read, L{File.render} sets the HTTP response code to I{FORBIDDEN}.
        """
        base = FilePath(self.mktemp())
        base.setContent('')
        # Make sure we can delete the file later.
        self.addCleanup(base.chmod, 0700)

        # Get rid of our own read permission.
        base.chmod(0)

        file = static.File(base.path)
        request = DummyRequest([''])
        d = self._render(file, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, 403)
        d.addCallback(cbRendered)
        return d
    if platform.isWindows():
        test_forbiddenResource.skip = "Cannot remove read permission on Windows"


    def test_indexNames(self):
        """
        If a request is made which encounters a L{File} before a final empty
        segment, a file in the L{File} instance's C{indexNames} list which
        exists in the path the L{File} was created with is served as the
        response to the request.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        base.child("foo.bar").setContent("baz")
        file = static.File(base.path)
        file.indexNames = ['foo.bar']

        request = DummyRequest([''])
        child = resource.getChildForRequest(file, request)

        d = self._render(child, request)
        def cbRendered(ignored):
            self.assertEqual(''.join(request.written), 'baz')
            self.assertEqual(request.outgoingHeaders['content-length'], '3')
        d.addCallback(cbRendered)
        return d


    def test_staticFile(self):
        """
        If a request is made which encounters a L{File} before a final segment
        which names a file in the path the L{File} was created with, that file
        is served as the response to the request.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        base.child("foo.bar").setContent("baz")
        file = static.File(base.path)

        request = DummyRequest(['foo.bar'])
        child = resource.getChildForRequest(file, request)

        d = self._render(child, request)
        def cbRendered(ignored):
            self.assertEqual(''.join(request.written), 'baz')
            self.assertEqual(request.outgoingHeaders['content-length'], '3')
        d.addCallback(cbRendered)
        return d


    def test_staticFileDeletedGetChild(self):
        """
        A L{static.File} created for a directory which does not exist should
        return childNotFound from L{static.File.getChild}.
        """
        staticFile = static.File(self.mktemp())
        request = DummyRequest(['foo.bar'])
        child = staticFile.getChild("foo.bar", request)
        self.assertEqual(child, staticFile.childNotFound)


    def test_staticFileDeletedRender(self):
        """
        A L{static.File} created for a file which does not exist should render
        its C{childNotFound} page.
        """
        staticFile = static.File(self.mktemp())
        request = DummyRequest(['foo.bar'])
        request2 = DummyRequest(['foo.bar'])
        d = self._render(staticFile, request)
        d2 = self._render(staticFile.childNotFound, request2)
        def cbRendered2(ignored):
            def cbRendered(ignored):
                self.assertEqual(''.join(request.written),
                                  ''.join(request2.written))
            d.addCallback(cbRendered)
            return d
        d2.addCallback(cbRendered2)
        return d2


    def test_headRequest(self):
        """
        L{static.File.render} returns an empty response body for I{HEAD}
        requests.
        """
        path = FilePath(self.mktemp())
        path.setContent("foo")
        file = static.File(path.path)
        request = DummyRequest([''])
        request.method = 'HEAD'
        d = _render(file, request)
        def cbRendered(ignored):
            self.assertEqual("".join(request.written), "")
        d.addCallback(cbRendered)
        return d


    def test_processors(self):
        """
        If a request is made which encounters a L{File} before a final segment
        which names a file with an extension which is in the L{File}'s
        C{processors} mapping, the processor associated with that extension is
        used to serve the response to the request.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        base.child("foo.bar").setContent(
            "from twisted.web.static import Data\n"
            "resource = Data('dynamic world','text/plain')\n")

        file = static.File(base.path)
        file.processors = {'.bar': script.ResourceScript}
        request = DummyRequest(["foo.bar"])
        child = resource.getChildForRequest(file, request)

        d = self._render(child, request)
        def cbRendered(ignored):
            self.assertEqual(''.join(request.written), 'dynamic world')
            self.assertEqual(request.outgoingHeaders['content-length'], '13')
        d.addCallback(cbRendered)
        return d


    def test_ignoreExt(self):
        """
        The list of ignored extensions can be set by passing a value to
        L{File.__init__} or by calling L{File.ignoreExt} later.
        """
        file = static.File(".")
        self.assertEqual(file.ignoredExts, [])
        file.ignoreExt(".foo")
        file.ignoreExt(".bar")
        self.assertEqual(file.ignoredExts, [".foo", ".bar"])

        file = static.File(".", ignoredExts=(".bar", ".baz"))
        self.assertEqual(file.ignoredExts, [".bar", ".baz"])


    def test_ignoredExtensionsIgnored(self):
        """
        A request for the I{base} child of a L{File} succeeds with a resource
        for the I{base<extension>} file in the path the L{File} was created
        with if such a file exists and the L{File} has been configured to
        ignore the I{<extension>} extension.
        """
        base = FilePath(self.mktemp())
        base.makedirs()
        base.child('foo.bar').setContent('baz')
        base.child('foo.quux').setContent('foobar')
        file = static.File(base.path, ignoredExts=(".bar",))

        request = DummyRequest(["foo"])
        child = resource.getChildForRequest(file, request)

        d = self._render(child, request)
        def cbRendered(ignored):
            self.assertEqual(''.join(request.written), 'baz')
        d.addCallback(cbRendered)
        return d



class StaticMakeProducerTests(TestCase):
    """
    Tests for L{File.makeProducer}.
    """


    def makeResourceWithContent(self, content, type=None, encoding=None):
        """
        Make a L{static.File} resource that has C{content} for its content.

        @param content: The bytes to use as the contents of the resource.
        @param type: Optional value for the content type of the resource.
        """
        fileName = self.mktemp()
        fileObject = open(fileName, 'w')
        fileObject.write(content)
        fileObject.close()
        resource = static.File(fileName)
        resource.encoding = encoding
        resource.type = type
        return resource


    def contentHeaders(self, request):
        """
        Extract the content-* headers from the L{DummyRequest} C{request}.

        This returns the subset of C{request.outgoingHeaders} of headers that
        start with 'content-'.
        """
        contentHeaders = {}
        for k, v in request.outgoingHeaders.iteritems():
            if k.startswith('content-'):
                contentHeaders[k] = v
        return contentHeaders


    def test_noRangeHeaderGivesNoRangeStaticProducer(self):
        """
        makeProducer when no Range header is set returns an instance of
        NoRangeStaticProducer.
        """
        resource = self.makeResourceWithContent('')
        request = DummyRequest([])
        producer = resource.makeProducer(request, resource.openForReading())
        self.assertIsInstance(producer, static.NoRangeStaticProducer)


    def test_noRangeHeaderSets200OK(self):
        """
        makeProducer when no Range header is set sets the responseCode on the
        request to 'OK'.
        """
        resource = self.makeResourceWithContent('')
        request = DummyRequest([])
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(http.OK, request.responseCode)


    def test_noRangeHeaderSetsContentHeaders(self):
        """
        makeProducer when no Range header is set sets the Content-* headers
        for the response.
        """
        length = 123
        contentType = "text/plain"
        contentEncoding = 'gzip'
        resource = self.makeResourceWithContent(
            'a'*length, type=contentType, encoding=contentEncoding)
        request = DummyRequest([])
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            {'content-type': contentType, 'content-length': str(length),
             'content-encoding': contentEncoding},
            self.contentHeaders(request))


    def test_singleRangeGivesSingleRangeStaticProducer(self):
        """
        makeProducer when the Range header requests a single byte range
        returns an instance of SingleRangeStaticProducer.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=1-3'
        resource = self.makeResourceWithContent('abcdef')
        producer = resource.makeProducer(request, resource.openForReading())
        self.assertIsInstance(producer, static.SingleRangeStaticProducer)


    def test_singleRangeSets206PartialContent(self):
        """
        makeProducer when the Range header requests a single, satisfiable byte
        range sets the response code on the request to 'Partial Content'.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=1-3'
        resource = self.makeResourceWithContent('abcdef')
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            http.PARTIAL_CONTENT, request.responseCode)


    def test_singleRangeSetsContentHeaders(self):
        """
        makeProducer when the Range header requests a single, satisfiable byte
        range sets the Content-* headers appropriately.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=1-3'
        contentType = "text/plain"
        contentEncoding = 'gzip'
        resource = self.makeResourceWithContent('abcdef', type=contentType, encoding=contentEncoding)
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            {'content-type': contentType, 'content-encoding': contentEncoding,
             'content-range': 'bytes 1-3/6', 'content-length': '3'},
            self.contentHeaders(request))


    def test_singleUnsatisfiableRangeReturnsSingleRangeStaticProducer(self):
        """
        makeProducer still returns an instance of L{SingleRangeStaticProducer}
        when the Range header requests a single unsatisfiable byte range.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=4-10'
        resource = self.makeResourceWithContent('abc')
        producer = resource.makeProducer(request, resource.openForReading())
        self.assertIsInstance(producer, static.SingleRangeStaticProducer)


    def test_singleUnsatisfiableRangeSets416ReqestedRangeNotSatisfiable(self):
        """
        makeProducer sets the response code of the request to of 'Requested
        Range Not Satisfiable' when the Range header requests a single
        unsatisfiable byte range.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=4-10'
        resource = self.makeResourceWithContent('abc')
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            http.REQUESTED_RANGE_NOT_SATISFIABLE, request.responseCode)


    def test_singleUnsatisfiableRangeSetsContentHeaders(self):
        """
        makeProducer when the Range header requests a single, unsatisfiable
        byte range sets the Content-* headers appropriately.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=4-10'
        contentType = "text/plain"
        resource = self.makeResourceWithContent('abc', type=contentType)
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            {'content-type': 'text/plain', 'content-length': '0',
             'content-range': 'bytes */3'},
            self.contentHeaders(request))


    def test_singlePartiallyOverlappingRangeSetsContentHeaders(self):
        """
        makeProducer when the Range header requests a single byte range that
        partly overlaps the resource sets the Content-* headers appropriately.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=2-10'
        contentType = "text/plain"
        resource = self.makeResourceWithContent('abc', type=contentType)
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            {'content-type': 'text/plain', 'content-length': '1',
             'content-range': 'bytes 2-2/3'},
            self.contentHeaders(request))


    def test_multipleRangeGivesMultipleRangeStaticProducer(self):
        """
        makeProducer when the Range header requests a single byte range
        returns an instance of MultipleRangeStaticProducer.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=1-3,5-6'
        resource = self.makeResourceWithContent('abcdef')
        producer = resource.makeProducer(request, resource.openForReading())
        self.assertIsInstance(producer, static.MultipleRangeStaticProducer)


    def test_multipleRangeSets206PartialContent(self):
        """
        makeProducer when the Range header requests a multiple satisfiable
        byte ranges sets the response code on the request to 'Partial
        Content'.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=1-3,5-6'
        resource = self.makeResourceWithContent('abcdef')
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            http.PARTIAL_CONTENT, request.responseCode)


    def test_mutipleRangeSetsContentHeaders(self):
        """
        makeProducer when the Range header requests a single, satisfiable byte
        range sets the Content-* headers appropriately.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=1-3,5-6'
        resource = self.makeResourceWithContent(
            'abcdefghijkl', encoding='gzip')
        producer = resource.makeProducer(request, resource.openForReading())
        contentHeaders = self.contentHeaders(request)
        # The only content-* headers set are content-type and content-length.
        self.assertEqual(
            set(['content-length', 'content-type']),
            set(contentHeaders.keys()))
        # The content-length depends on the boundary used in the response.
        expectedLength = 5
        for boundary, offset, size in producer.rangeInfo:
            expectedLength += len(boundary)
        self.assertEqual(expectedLength, contentHeaders['content-length'])
        # Content-type should be set to a value indicating a multipart
        # response and the boundary used to separate the parts.
        self.assertIn('content-type', contentHeaders)
        contentType = contentHeaders['content-type']
        self.assertNotIdentical(
            None, re.match(
                'multipart/byteranges; boundary="[^"]*"\Z', contentType))
        # Content-encoding is not set in the response to a multiple range
        # response, which is a bit wussy but works well enough with the way
        # static.File does content-encodings...
        self.assertNotIn('content-encoding', contentHeaders)


    def test_multipleUnsatisfiableRangesReturnsMultipleRangeStaticProducer(self):
        """
        makeProducer still returns an instance of L{SingleRangeStaticProducer}
        when the Range header requests multiple ranges, none of which are
        satisfiable.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=10-12,15-20'
        resource = self.makeResourceWithContent('abc')
        producer = resource.makeProducer(request, resource.openForReading())
        self.assertIsInstance(producer, static.MultipleRangeStaticProducer)


    def test_multipleUnsatisfiableRangesSets416ReqestedRangeNotSatisfiable(self):
        """
        makeProducer sets the response code of the request to of 'Requested
        Range Not Satisfiable' when the Range header requests multiple ranges,
        none of which are satisfiable.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=10-12,15-20'
        resource = self.makeResourceWithContent('abc')
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            http.REQUESTED_RANGE_NOT_SATISFIABLE, request.responseCode)


    def test_multipleUnsatisfiableRangeSetsContentHeaders(self):
        """
        makeProducer when the Range header requests multiple ranges, none of
        which are satisfiable, sets the Content-* headers appropriately.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=4-10'
        contentType = "text/plain"
        request.headers['range'] = 'bytes=10-12,15-20'
        resource = self.makeResourceWithContent('abc', type=contentType)
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            {'content-length': '0', 'content-range': 'bytes */3'},
            self.contentHeaders(request))


    def test_oneSatisfiableRangeIsEnough(self):
        """
        makeProducer when the Range header requests multiple ranges, at least
        one of which matches, sets the response code to 'Partial Content'.
        """
        request = DummyRequest([])
        request.headers['range'] = 'bytes=1-3,100-200'
        resource = self.makeResourceWithContent('abcdef')
        resource.makeProducer(request, resource.openForReading())
        self.assertEqual(
            http.PARTIAL_CONTENT, request.responseCode)



class StaticProducerTests(TestCase):
    """
    Tests for the abstract L{StaticProducer}.
    """

    def test_stopProducingClosesFile(self):
        """
        L{StaticProducer.stopProducing} closes the file object the producer is
        producing data from.
        """
        fileObject = StringIO.StringIO()
        producer = static.StaticProducer(None, fileObject)
        producer.stopProducing()
        self.assertTrue(fileObject.closed)


    def test_stopProducingSetsRequestToNone(self):
        """
        L{StaticProducer.stopProducing} sets the request instance variable to
        None, which indicates to subclasses' resumeProducing methods that no
        more data should be produced.
        """
        fileObject = StringIO.StringIO()
        producer = static.StaticProducer(DummyRequest([]), fileObject)
        producer.stopProducing()
        self.assertIdentical(None, producer.request)



class NoRangeStaticProducerTests(TestCase):
    """
    Tests for L{NoRangeStaticProducer}.
    """

    def test_implementsIPullProducer(self):
        """
        L{NoRangeStaticProducer} implements L{IPullProducer}.
        """
        verifyObject(
            interfaces.IPullProducer,
            static.NoRangeStaticProducer(None, None))


    def test_resumeProducingProducesContent(self):
        """
        L{NoRangeStaticProducer.resumeProducing} writes content from the
        resource to the request.
        """
        request = DummyRequest([])
        content = 'abcdef'
        producer = static.NoRangeStaticProducer(
            request, StringIO.StringIO(content))
        # start calls registerProducer on the DummyRequest, which pulls all
        # output from the producer and so we just need this one call.
        producer.start()
        self.assertEqual(content, ''.join(request.written))


    def test_resumeProducingBuffersOutput(self):
        """
        L{NoRangeStaticProducer.start} writes at most
        C{abstract.FileDescriptor.bufferSize} bytes of content from the
        resource to the request at once.
        """
        request = DummyRequest([])
        bufferSize = abstract.FileDescriptor.bufferSize
        content = 'a' * (2*bufferSize + 1)
        producer = static.NoRangeStaticProducer(
            request, StringIO.StringIO(content))
        # start calls registerProducer on the DummyRequest, which pulls all
        # output from the producer and so we just need this one call.
        producer.start()
        expected = [
            content[0:bufferSize],
            content[bufferSize:2*bufferSize],
            content[2*bufferSize:]
            ]
        self.assertEqual(expected, request.written)


    def test_finishCalledWhenDone(self):
        """
        L{NoRangeStaticProducer.resumeProducing} calls finish() on the request
        after it is done producing content.
        """
        request = DummyRequest([])
        finishDeferred = request.notifyFinish()
        callbackList = []
        finishDeferred.addCallback(callbackList.append)
        producer = static.NoRangeStaticProducer(
            request, StringIO.StringIO('abcdef'))
        # start calls registerProducer on the DummyRequest, which pulls all
        # output from the producer and so we just need this one call.
        producer.start()
        self.assertEqual([None], callbackList)



class SingleRangeStaticProducerTests(TestCase):
    """
    Tests for L{SingleRangeStaticProducer}.
    """

    def test_implementsIPullProducer(self):
        """
        L{SingleRangeStaticProducer} implements L{IPullProducer}.
        """
        verifyObject(
            interfaces.IPullProducer,
            static.SingleRangeStaticProducer(None, None, None, None))


    def test_resumeProducingProducesContent(self):
        """
        L{SingleRangeStaticProducer.resumeProducing} writes the given amount
        of content, starting at the given offset, from the resource to the
        request.
        """
        request = DummyRequest([])
        content = 'abcdef'
        producer = static.SingleRangeStaticProducer(
            request, StringIO.StringIO(content), 1, 3)
        # DummyRequest.registerProducer pulls all output from the producer, so
        # we just need to call start.
        producer.start()
        self.assertEqual(content[1:4], ''.join(request.written))


    def test_resumeProducingBuffersOutput(self):
        """
        L{SingleRangeStaticProducer.start} writes at most
        C{abstract.FileDescriptor.bufferSize} bytes of content from the
        resource to the request at once.
        """
        request = DummyRequest([])
        bufferSize = abstract.FileDescriptor.bufferSize
        content = 'abc' * bufferSize
        producer = static.SingleRangeStaticProducer(
            request, StringIO.StringIO(content), 1, bufferSize+10)
        # DummyRequest.registerProducer pulls all output from the producer, so
        # we just need to call start.
        producer.start()
        expected = [
            content[1:bufferSize+1],
            content[bufferSize+1:bufferSize+11],
            ]
        self.assertEqual(expected, request.written)


    def test_finishCalledWhenDone(self):
        """
        L{SingleRangeStaticProducer.resumeProducing} calls finish() on the
        request after it is done producing content.
        """
        request = DummyRequest([])
        finishDeferred = request.notifyFinish()
        callbackList = []
        finishDeferred.addCallback(callbackList.append)
        producer = static.SingleRangeStaticProducer(
            request, StringIO.StringIO('abcdef'), 1, 1)
        # start calls registerProducer on the DummyRequest, which pulls all
        # output from the producer and so we just need this one call.
        producer.start()
        self.assertEqual([None], callbackList)



class MultipleRangeStaticProducerTests(TestCase):
    """
    Tests for L{MultipleRangeStaticProducer}.
    """

    def test_implementsIPullProducer(self):
        """
        L{MultipleRangeStaticProducer} implements L{IPullProducer}.
        """
        verifyObject(
            interfaces.IPullProducer,
            static.MultipleRangeStaticProducer(None, None, None))


    def test_resumeProducingProducesContent(self):
        """
        L{MultipleRangeStaticProducer.resumeProducing} writes the requested
        chunks of content from the resource to the request, with the supplied
        boundaries in between each chunk.
        """
        request = DummyRequest([])
        content = 'abcdef'
        producer = static.MultipleRangeStaticProducer(
            request, StringIO.StringIO(content), [('1', 1, 3), ('2', 5, 1)])
        # DummyRequest.registerProducer pulls all output from the producer, so
        # we just need to call start.
        producer.start()
        self.assertEqual('1bcd2f', ''.join(request.written))


    def test_resumeProducingBuffersOutput(self):
        """
        L{MultipleRangeStaticProducer.start} writes about
        C{abstract.FileDescriptor.bufferSize} bytes of content from the
        resource to the request at once.

        To be specific about the 'about' above: it can write slightly more,
        for example in the case where the first boundary plus the first chunk
        is less than C{bufferSize} but first boundary plus the first chunk
        plus the second boundary is more, but this is unimportant as in
        practice the boundaries are fairly small.  On the other side, it is
        important for performance to bundle up several small chunks into one
        call to request.write.
        """
        request = DummyRequest([])
        content = '0123456789' * 2
        producer = static.MultipleRangeStaticProducer(
            request, StringIO.StringIO(content),
            [('a', 0, 2), ('b', 5, 10), ('c', 0, 0)])
        producer.bufferSize = 10
        # DummyRequest.registerProducer pulls all output from the producer, so
        # we just need to call start.
        producer.start()
        expected = [
            'a' + content[0:2] + 'b' + content[5:11],
            content[11:15] + 'c',
            ]
        self.assertEqual(expected, request.written)


    def test_finishCalledWhenDone(self):
        """
        L{MultipleRangeStaticProducer.resumeProducing} calls finish() on the
        request after it is done producing content.
        """
        request = DummyRequest([])
        finishDeferred = request.notifyFinish()
        callbackList = []
        finishDeferred.addCallback(callbackList.append)
        producer = static.MultipleRangeStaticProducer(
            request, StringIO.StringIO('abcdef'), [('', 1, 2)])
        # start calls registerProducer on the DummyRequest, which pulls all
        # output from the producer and so we just need this one call.
        producer.start()
        self.assertEqual([None], callbackList)



class RangeTests(TestCase):
    """
    Tests for I{Range-Header} support in L{twisted.web.static.File}.

    @type file: L{file}
    @ivar file: Temporary (binary) file containing the content to be served.

    @type resource: L{static.File}
    @ivar resource: A leaf web resource using C{file} as content.

    @type request: L{DummyRequest}
    @ivar request: A fake request, requesting C{resource}.

    @type catcher: L{list}
    @ivar catcher: List which gathers all log information.
    """
    def setUp(self):
        """
        Create a temporary file with a fixed payload of 64 bytes.  Create a
        resource for that file and create a request which will be for that
        resource.  Each test can set a different range header to test different
        aspects of the implementation.
        """
        path = FilePath(self.mktemp())
        # This is just a jumble of random stuff.  It's supposed to be a good
        # set of data for this test, particularly in order to avoid
        # accidentally seeing the right result by having a byte sequence
        # repeated at different locations or by having byte values which are
        # somehow correlated with their position in the string.
        self.payload = ('\xf8u\xf3E\x8c7\xce\x00\x9e\xb6a0y0S\xf0\xef\xac\xb7'
                        '\xbe\xb5\x17M\x1e\x136k{\x1e\xbe\x0c\x07\x07\t\xd0'
                        '\xbckY\xf5I\x0b\xb8\x88oZ\x1d\x85b\x1a\xcdk\xf2\x1d'
                        '&\xfd%\xdd\x82q/A\x10Y\x8b')
        path.setContent(self.payload)
        self.file = path.open()
        self.resource = static.File(self.file.name)
        self.resource.isLeaf = 1
        self.request = DummyRequest([''])
        self.request.uri = self.file.name
        self.catcher = []
        log.addObserver(self.catcher.append)


    def tearDown(self):
        """
        Clean up the resource file and the log observer.
        """
        self.file.close()
        log.removeObserver(self.catcher.append)


    def _assertLogged(self, expected):
        """
        Asserts that a given log message occurred with an expected message.
        """
        logItem = self.catcher.pop()
        self.assertEqual(logItem["message"][0], expected)
        self.assertEqual(
            self.catcher, [], "An additional log occured: %r" % (logItem,))


    def test_invalidRanges(self):
        """
        L{File._parseRangeHeader} raises L{ValueError} when passed
        syntactically invalid byte ranges.
        """
        f = self.resource._parseRangeHeader

        # there's no =
        self.assertRaises(ValueError, f, 'bytes')

        # unknown isn't a valid Bytes-Unit
        self.assertRaises(ValueError, f, 'unknown=1-2')

        # there's no - in =stuff
        self.assertRaises(ValueError, f, 'bytes=3')

        # both start and end are empty
        self.assertRaises(ValueError, f, 'bytes=-')

        # start isn't an integer
        self.assertRaises(ValueError, f, 'bytes=foo-')

        # end isn't an integer
        self.assertRaises(ValueError, f, 'bytes=-foo')

        # end isn't equal to or greater than start
        self.assertRaises(ValueError, f, 'bytes=5-4')


    def test_rangeMissingStop(self):
        """
        A single bytes range without an explicit stop position is parsed into a
        two-tuple giving the start position and C{None}.
        """
        self.assertEqual(
            self.resource._parseRangeHeader('bytes=0-'), [(0, None)])


    def test_rangeMissingStart(self):
        """
        A single bytes range without an explicit start position is parsed into
        a two-tuple of C{None} and the end position.
        """
        self.assertEqual(
            self.resource._parseRangeHeader('bytes=-3'), [(None, 3)])


    def test_range(self):
        """
        A single bytes range with explicit start and stop positions is parsed
        into a two-tuple of those positions.
        """
        self.assertEqual(
            self.resource._parseRangeHeader('bytes=2-5'), [(2, 5)])


    def test_rangeWithSpace(self):
        """
        A single bytes range with whitespace in allowed places is parsed in
        the same way as it would be without the whitespace.
        """
        self.assertEqual(
            self.resource._parseRangeHeader(' bytes=1-2 '), [(1, 2)])
        self.assertEqual(
            self.resource._parseRangeHeader('bytes =1-2 '), [(1, 2)])
        self.assertEqual(
            self.resource._parseRangeHeader('bytes= 1-2'), [(1, 2)])
        self.assertEqual(
            self.resource._parseRangeHeader('bytes=1 -2'), [(1, 2)])
        self.assertEqual(
            self.resource._parseRangeHeader('bytes=1- 2'), [(1, 2)])
        self.assertEqual(
            self.resource._parseRangeHeader('bytes=1-2 '), [(1, 2)])


    def test_nullRangeElements(self):
        """
        If there are multiple byte ranges but only one is non-null, the
        non-null range is parsed and its start and stop returned.
        """
        self.assertEqual(
            self.resource._parseRangeHeader('bytes=1-2,\r\n, ,\t'), [(1, 2)])


    def test_multipleRanges(self):
        """
        If multiple byte ranges are specified their starts and stops are
        returned.
        """
        self.assertEqual(
            self.resource._parseRangeHeader('bytes=1-2,3-4'),
            [(1, 2), (3, 4)])


    def test_bodyLength(self):
        """
        A correct response to a range request is as long as the length of the
        requested range.
        """
        self.request.headers['range'] = 'bytes=0-43'
        self.resource.render(self.request)
        self.assertEqual(len(''.join(self.request.written)), 44)


    def test_invalidRangeRequest(self):
        """
        An incorrect range request (RFC 2616 defines a correct range request as
        a Bytes-Unit followed by a '=' character followed by a specific range.
        Only 'bytes' is defined) results in the range header value being logged
        and a normal 200 response being sent.
        """
        self.request.headers['range'] = range = 'foobar=0-43'
        self.resource.render(self.request)
        expected = "Ignoring malformed Range header %r" % (range,)
        self._assertLogged(expected)
        self.assertEqual(''.join(self.request.written), self.payload)
        self.assertEqual(self.request.responseCode, http.OK)
        self.assertEqual(
            self.request.outgoingHeaders['content-length'],
            str(len(self.payload)))


    def parseMultipartBody(self, body, boundary):
        """
        Parse C{body} as a multipart MIME response separated by C{boundary}.

        Note that this with fail the calling test on certain syntactic
        problems.
        """
        sep = "\r\n--" + boundary
        parts = ''.join(body).split(sep)
        self.assertEqual('', parts[0])
        self.assertEqual('--\r\n', parts[-1])
        parsed_parts = []
        for part in parts[1:-1]:
            before, header1, header2, blank, partBody = part.split('\r\n', 4)
            headers = header1 + '\n' + header2
            self.assertEqual('', before)
            self.assertEqual('', blank)
            partContentTypeValue = re.search(
                '^content-type: (.*)$', headers, re.I|re.M).group(1)
            start, end, size = re.search(
                '^content-range: bytes ([0-9]+)-([0-9]+)/([0-9]+)$',
                headers, re.I|re.M).groups()
            parsed_parts.append(
                {'contentType': partContentTypeValue,
                 'contentRange': (start, end, size),
                 'body': partBody})
        return parsed_parts


    def test_multipleRangeRequest(self):
        """
        The response to a request for multipe bytes ranges is a MIME-ish
        multipart response.
        """
        startEnds = [(0, 2), (20, 30), (40, 50)]
        rangeHeaderValue = ','.join(["%s-%s"%(s,e) for (s, e) in startEnds])
        self.request.headers['range'] = 'bytes=' + rangeHeaderValue
        self.resource.render(self.request)
        self.assertEqual(self.request.responseCode, http.PARTIAL_CONTENT)
        boundary = re.match(
            '^multipart/byteranges; boundary="(.*)"$',
            self.request.outgoingHeaders['content-type']).group(1)
        parts = self.parseMultipartBody(''.join(self.request.written), boundary)
        self.assertEqual(len(startEnds), len(parts))
        for part, (s, e) in zip(parts, startEnds):
            self.assertEqual(self.resource.type, part['contentType'])
            start, end, size = part['contentRange']
            self.assertEqual(int(start), s)
            self.assertEqual(int(end), e)
            self.assertEqual(int(size), self.resource.getFileSize())
            self.assertEqual(self.payload[s:e+1], part['body'])


    def test_multipleRangeRequestWithRangeOverlappingEnd(self):
        """
        The response to a request for multipe bytes ranges is a MIME-ish
        multipart response, even when one of the ranged falls off the end of
        the resource.
        """
        startEnds = [(0, 2), (40, len(self.payload) + 10)]
        rangeHeaderValue = ','.join(["%s-%s"%(s,e) for (s, e) in startEnds])
        self.request.headers['range'] = 'bytes=' + rangeHeaderValue
        self.resource.render(self.request)
        self.assertEqual(self.request.responseCode, http.PARTIAL_CONTENT)
        boundary = re.match(
            '^multipart/byteranges; boundary="(.*)"$',
            self.request.outgoingHeaders['content-type']).group(1)
        parts = self.parseMultipartBody(''.join(self.request.written), boundary)
        self.assertEqual(len(startEnds), len(parts))
        for part, (s, e) in zip(parts, startEnds):
            self.assertEqual(self.resource.type, part['contentType'])
            start, end, size = part['contentRange']
            self.assertEqual(int(start), s)
            self.assertEqual(int(end), min(e, self.resource.getFileSize()-1))
            self.assertEqual(int(size), self.resource.getFileSize())
            self.assertEqual(self.payload[s:e+1], part['body'])


    def test_implicitEnd(self):
        """
        If the end byte position is omitted, then it is treated as if the
        length of the resource was specified by the end byte position.
        """
        self.request.headers['range'] = 'bytes=23-'
        self.resource.render(self.request)
        self.assertEqual(''.join(self.request.written), self.payload[23:])
        self.assertEqual(len(''.join(self.request.written)), 41)
        self.assertEqual(self.request.responseCode, http.PARTIAL_CONTENT)
        self.assertEqual(
            self.request.outgoingHeaders['content-range'], 'bytes 23-63/64')
        self.assertEqual(self.request.outgoingHeaders['content-length'], '41')


    def test_implicitStart(self):
        """
        If the start byte position is omitted but the end byte position is
        supplied, then the range is treated as requesting the last -N bytes of
        the resource, where N is the end byte position.
        """
        self.request.headers['range'] = 'bytes=-17'
        self.resource.render(self.request)
        self.assertEqual(''.join(self.request.written), self.payload[-17:])
        self.assertEqual(len(''.join(self.request.written)), 17)
        self.assertEqual(self.request.responseCode, http.PARTIAL_CONTENT)
        self.assertEqual(
            self.request.outgoingHeaders['content-range'], 'bytes 47-63/64')
        self.assertEqual(self.request.outgoingHeaders['content-length'], '17')


    def test_explicitRange(self):
        """
        A correct response to a bytes range header request from A to B starts
        with the A'th byte and ends with (including) the B'th byte. The first
        byte of a page is numbered with 0.
        """
        self.request.headers['range'] = 'bytes=3-43'
        self.resource.render(self.request)
        written = ''.join(self.request.written)
        self.assertEqual(written, self.payload[3:44])
        self.assertEqual(self.request.responseCode, http.PARTIAL_CONTENT)
        self.assertEqual(
            self.request.outgoingHeaders['content-range'], 'bytes 3-43/64')
        self.assertEqual(
            str(len(written)), self.request.outgoingHeaders['content-length'])


    def test_explicitRangeOverlappingEnd(self):
        """
        A correct response to a bytes range header request from A to B when B
        is past the end of the resource starts with the A'th byte and ends
        with the last byte of the resource. The first byte of a page is
        numbered with 0.
        """
        self.request.headers['range'] = 'bytes=40-100'
        self.resource.render(self.request)
        written = ''.join(self.request.written)
        self.assertEqual(written, self.payload[40:])
        self.assertEqual(self.request.responseCode, http.PARTIAL_CONTENT)
        self.assertEqual(
            self.request.outgoingHeaders['content-range'], 'bytes 40-63/64')
        self.assertEqual(
            str(len(written)), self.request.outgoingHeaders['content-length'])


    def test_statusCodeRequestedRangeNotSatisfiable(self):
        """
        If a range is syntactically invalid due to the start being greater than
        the end, the range header is ignored (the request is responded to as if
        it were not present).
        """
        self.request.headers['range'] = 'bytes=20-13'
        self.resource.render(self.request)
        self.assertEqual(self.request.responseCode, http.OK)
        self.assertEqual(''.join(self.request.written), self.payload)
        self.assertEqual(
            self.request.outgoingHeaders['content-length'],
            str(len(self.payload)))


    def test_invalidStartBytePos(self):
        """
        If a range is unsatisfiable due to the start not being less than the
        length of the resource, the response is 416 (Requested range not
        satisfiable) and no data is written to the response body (RFC 2616,
        section 14.35.1).
        """
        self.request.headers['range'] = 'bytes=67-108'
        self.resource.render(self.request)
        self.assertEqual(
            self.request.responseCode, http.REQUESTED_RANGE_NOT_SATISFIABLE)
        self.assertEqual(''.join(self.request.written), '')
        self.assertEqual(self.request.outgoingHeaders['content-length'], '0')
        # Sections 10.4.17 and 14.16
        self.assertEqual(
            self.request.outgoingHeaders['content-range'],
            'bytes */%d' % (len(self.payload),))



class DirectoryListerTest(TestCase):
    """
    Tests for L{static.DirectoryLister}.
    """

    def test_filePath(self):
        """
        L{static.DirectoryLister.__init__} accepts a C{pathname} argument
        which it assigns to L{static.DirectoryLister.path}.
        """
        dummy = b'/a/nonexistent/path'
        self.assertEqual(
            static.DirectoryLister(pathname=dummy).path,
            dummy)


    def test_filePathFactory(self):
        """
        L{static.DirectoryLister._filePathFactory} defaults to
        L{FilePath}.
        """
        self.assertIdentical(
            FilePath,
            static.DirectoryLister._filePathFactory)


    def test_filePathCoercion(self):
        """
        If C{pathname} is not an L{IFilePath} provider,
        L{static.DirectoryLister.__init__} calls C{_filePathFactory}
        with the C{pathname} argument and assigns the return value to
        L{static.DirectoryLister._path}.
        """
        dummy = object()
        filepaths = []
        def fakeFilePathFactory(filepath):
            filepaths.append(filepath)
            return dummy
        self.patch(
            static.DirectoryLister, '_filePathFactory',
            staticmethod(fakeFilePathFactory))
        self.assertIdentical(
            static.DirectoryLister(pathname=b'testpath')._path, dummy)
        self.assertEqual(filepaths, [b'testpath'])


    def test_filePathNoCoercion(self):
        """
        L{static.DirectoryLister.__init__} does not attempt to coerce
        L{IFilePath} providers and assigns the value of
        C{pathname}.path to L{static.DirectoryLister.path}.
        """
        dummy = MemoryPath(path=b'/a/nonexistent/path')
        dl = static.DirectoryLister(pathname=dummy)
        self.assertIdentical(
            dl._path, dummy)
        self.assertEqual(dl.path, dummy.path)


    def _request(self, uri):
        request = DummyRequest([''])
        request.uri = uri
        return request


    def test_renderHeader(self):
        """
        L{static.DirectoryLister} prints the request uri as header of the
        rendered content.
        """
        path = FilePath(self.mktemp())
        path.makedirs()

        lister = static.DirectoryLister(path.path)
        data = lister.render(self._request('foo'))
        self.assertIn("<h1>Directory listing for foo</h1>", data)
        self.assertIn("<title>Directory listing for foo</title>", data)


    def test_renderUnquoteHeader(self):
        """
        L{static.DirectoryLister} unquote the request uri before printing it.
        """
        path = FilePath(self.mktemp())
        path.makedirs()

        lister = static.DirectoryLister(path.path)
        data = lister.render(self._request('foo%20bar'))
        self.assertIn("<h1>Directory listing for foo bar</h1>", data)
        self.assertIn("<title>Directory listing for foo bar</title>", data)


    def test_escapeHeader(self):
        """
        L{static.DirectoryLister} escape "&", "<" and ">" after unquoting the
        request uri.
        """
        path = FilePath(self.mktemp())
        path.makedirs()

        lister = static.DirectoryLister(path.path)
        data = lister.render(self._request('foo%26bar'))
        self.assertIn("<h1>Directory listing for foo&amp;bar</h1>", data)
        self.assertIn("<title>Directory listing for foo&amp;bar</title>", data)


    def test_renderFiles(self):
        """
        L{static.DirectoryLister} is able to list all the files inside a
        directory.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        path.child('file1').setContent("content1")
        path.child('file2').setContent("content2" * 1000)

        lister = static.DirectoryLister(path.path)
        data = lister.render(self._request('foo'))
        body = """<tr class="odd">
    <td><a href="file1">file1</a></td>
    <td>8B</td>
    <td>[text/html]</td>
    <td></td>
</tr>
<tr class="even">
    <td><a href="file2">file2</a></td>
    <td>7K</td>
    <td>[text/html]</td>
    <td></td>
</tr>"""
        self.assertIn(body, data)


    def test_renderDirectories(self):
        """
        L{static.DirectoryLister} is able to list all the directories inside
        a directory.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        path.child('dir1').makedirs()
        path.child('dir2 & 3').makedirs()

        lister = static.DirectoryLister(path.path)
        data = lister.render(self._request('foo'))
        body = """<tr class="odd">
    <td><a href="dir1/">dir1/</a></td>
    <td></td>
    <td>[Directory]</td>
    <td></td>
</tr>
<tr class="even">
    <td><a href="dir2%20%26%203/">dir2 &amp; 3/</a></td>
    <td></td>
    <td>[Directory]</td>
    <td></td>
</tr>"""
        self.assertIn(body, data)


    def test_renderFiltered(self):
        """
        L{static.DirectoryLister} takes a optional C{dirs} argument that
        filter out the list of of directories and files printed.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        path.child('dir1').makedirs()
        path.child('dir2').makedirs()
        path.child('dir3').makedirs()
        lister = static.DirectoryLister(path.path, dirs=["dir1", "dir3"])
        data = lister.render(self._request('foo'))
        body = """<tr class="odd">
    <td><a href="dir1/">dir1/</a></td>
    <td></td>
    <td>[Directory]</td>
    <td></td>
</tr>
<tr class="even">
    <td><a href="dir3/">dir3/</a></td>
    <td></td>
    <td>[Directory]</td>
    <td></td>
</tr>"""
        self.assertIn(body, data)


    def test_oddAndEven(self):
        """
        L{static.DirectoryLister} gives an alternate class for each odd and
        even rows in the table.
        """
        lister = static.DirectoryLister('.')
        elements = [{"href": "", "text": "", "size": "", "type": "",
                     "encoding": ""}  for i in xrange(5)]
        content = lister._buildTableContent(elements)

        self.assertEqual(len(content), 5)
        self.assertTrue(content[0].startswith('<tr class="odd">'))
        self.assertTrue(content[1].startswith('<tr class="even">'))
        self.assertTrue(content[2].startswith('<tr class="odd">'))
        self.assertTrue(content[3].startswith('<tr class="even">'))
        self.assertTrue(content[4].startswith('<tr class="odd">'))


    def test_contentType(self):
        """
        L{static.DirectoryLister} produces a MIME-type that indicates that it is
        HTML, and includes its charset (UTF-8).
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        lister = static.DirectoryLister(path.path)
        req = self._request('')
        lister.render(req)
        self.assertEqual(req.outgoingHeaders['content-type'],
                          "text/html; charset=utf-8")


    def test_mimeTypeAndEncodings(self):
        """
        L{static.DirectoryLister} is able to detect mimetype and encoding of
        listed files.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        path.child('file1.txt').setContent("file1")
        path.child('file2.py').setContent("python")
        path.child('file3.conf.gz').setContent("conf compressed")
        path.child('file4.diff.bz2').setContent("diff compressed")

        contentTypes = {
            ".txt": "text/plain",
            ".py": "text/python",
            ".conf": "text/configuration",
            ".diff": "text/diff"
        }

        lister = static.DirectoryLister(path.path, contentTypes=contentTypes)
        dirs, files = lister._getFilesAndDirectories(sorted(path.children()))
        self.assertEqual(dirs, [])
        self.assertEqual(files, [
            {'encoding': '',
             'href': 'file1.txt',
             'size': '5B',
             'text': 'file1.txt',
             'type': '[text/plain]'},
            {'encoding': '',
             'href': 'file2.py',
             'size': '6B',
             'text': 'file2.py',
             'type': '[text/python]'},
            {'encoding': '[gzip]',
             'href': 'file3.conf.gz',
             'size': '15B',
             'text': 'file3.conf.gz',
             'type': '[text/configuration]'},
            {'encoding': '[bzip2]',
             'href': 'file4.diff.bz2',
             'size': '15B',
             'text': 'file4.diff.bz2',
             'type': '[text/diff]'}])


    def test_brokenSymlink(self):
        """
        If on the file in the listing points to a broken symlink, it should not
        be returned by L{static.DirectoryLister._getFilesAndDirectories}.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        file1 = path.child('file1')
        file1.setContent("file1")
        file1.linkTo(path.child("file2"))
        file1.remove()

        lister = static.DirectoryLister(path.path)
        dirs, files = lister._getFilesAndDirectories(path.children())
        self.assertEqual(dirs, [])
        self.assertEqual(files, [])

    if getattr(os, "symlink", None) is None:
        test_brokenSymlink.skip = "No symlink support"


    def test_childrenNotFound(self):
        """
        Any child resource of L{static.DirectoryLister} renders an HTTP
        I{NOT FOUND} response code.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        lister = static.DirectoryLister(path.path)
        request = self._request('')
        child = resource.getChildForRequest(lister, request)
        result = _render(child, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, http.NOT_FOUND)
        result.addCallback(cbRendered)
        return result


    def test_repr(self):
        """
        L{static.DirectoryLister.__repr__} gives the path of the lister.
        """
        path = FilePath(self.mktemp())
        lister = static.DirectoryLister(path.path)
        self.assertEqual(repr(lister),
                          "<DirectoryLister of %r>" % (path.path,))
        self.assertEqual(str(lister),
                          "<DirectoryLister of %r>" % (path.path,))

    def test_formatFileSize(self):
        """
        L{static.formatFileSize} format an amount of bytes into a more readable
        format.
        """
        self.assertEqual(static.formatFileSize(0), "0B")
        self.assertEqual(static.formatFileSize(123), "123B")
        self.assertEqual(static.formatFileSize(4567), "4K")
        self.assertEqual(static.formatFileSize(8900000), "8M")
        self.assertEqual(static.formatFileSize(1234000000), "1G")
        self.assertEqual(static.formatFileSize(1234567890000), "1149G")



class RaisedArgs(Exception):
    def __init__(self, callee, args, kwargs):
        self.callee = callee
        self.args = args
        self.kwargs = kwargs



class _MemoryPath(object):
    """
    In memory fake implementation of IFilePath.
    """
    def __init__(self, path='', isdir=RaisedArgs, child=RaisedArgs,
                 exists=True):
        self.path = path
        self._isdir = isdir
        self._child = child
        self._exists = exists


    def isdir(self, *args, **kwargs):
        if self._isdir is RaisedArgs:
            raise RaisedArgs(self.isdir, args, kwargs)
        return self._isdir


    def child(self, *args, **kwargs):
        if self._child is RaisedArgs:
            raise RaisedArgs(self.child, args, kwargs)
        elif isinstance(self._child, Exception):
            raise self._child
        else:
            return self._child


    def exists(self, *args, **kwargs):
        if self._exists is RaisedArgs:
            raise RaisedArgs(self.exists, args, kwargs)
        return self._exists



class MemoryPath(components.proxyForInterface(IFilePath)):
    """
    Wraps _MemoryPath and provides parts of FilePath which are not in
    IFilePath.
    """
    def __init__(self, *args, **kwargs):
        self._childSearchPreauth = kwargs.pop("childSearchPreauth", None)
        self.original = _MemoryPath(*args, **kwargs)


    @property
    def path(self):
        """
        """
        return self.original.path


    def childSearchPreauth(self, *args, **kwargs):
        """
        """
        if self._childSearchPreauth is RaisedArgs:
            raise RaisedArgs(self.child, args, kwargs)
        elif isinstance(self._childSearchPreauth, Exception):
            raise self._childSearchPreauth
        else:
            return self._childSearchPreauth



class MemoryFile(MemoryPath):
    def isdir(self):
        return False



class MemoryDir(MemoryPath):
    def isdir(self):
        return True



class PathTests(TestCase):
    """
    Tests for L{Path}.
    """
    def test_filePath(self):
        """
        L{Path._filePath} defaults to C{FilePath('.')}
        """
        self.assertEqual(static.Path()._filePath,
                         FilePath('.'))


    def test_filePathOverride(self):
        """
        L{Path.__init__} accepts a C{filePath} argument
        which is assigned to the C{_filePath} attribute.
        """
        dummy = MemoryPath()
        self.assertIdentical(
            static.Path(filePath=dummy)._filePath,
            dummy)


    def test_filePathNonExistentValueError(self):
        """
        L{Path.__init__} raises L{ValueError} if the supplied
        C{filePath} argument represents a path that does not
        exist.
        """
        e = self.assertRaises(
            IOError,
            static.Path, filePath=MemoryPath(path='foo', exists=False))
        self.assertEqual(e.errno, 2)
        self.assertEqual(e.filename, 'foo')


    def test_fileRenderer(self):
        """
        L{Path._fileRenderer} defaults to L{static.FilePathRenderer}
        """
        self.assertIdentical(
            static.Path()._fileRenderer,
            static.FilePathRenderer)


    def test_fileRendererOverride(self):
        """
        L{Path.__init__} accepts a C{fileRenderer} argument
        which is assigned to the C{_fileRenderer} attribute.
        """
        dummy = object()
        self.assertIdentical(
            static.Path(fileRenderer=dummy)._fileRenderer,
            dummy)


    def test_directoryRenderer(self):
        """
        L{Path._directoryRenderer} defaults to
        L{static.DirectoryPathRenderer}.
        """
        self.assertIdentical(
            static.Path()._directoryRenderer,
            static.DirectoryPathRenderer)


    def test_directoryRendererOverride(self):
        """
        L{Path.__init__} accepts a C{directoryRenderer} argument
        which is assigned to the C{_directoryRenderer} attribute.
        """
        dummy = object()
        self.assertIdentical(
            static.Path(directoryRenderer=dummy)._directoryRenderer,
            dummy)


    def test_pathNotFoundRenderer(self):
        """
        L{Path._pathNotFoundRenderer} defaults to
        L{resource.NoResource}.
        """
        self.assertIdentical(
            static.Path()._pathNotFoundRenderer,
            resource.NoResource)


    def test_pathNotFoundRendererOverride(self):
        """
        L{Path.__init__} accepts a C{pathNotFoundRenderer} argument
        which is assigned to the C{_pathNotFoundRenderer} attribute.
        """
        dummy = object()
        self.assertIdentical(
            static.Path(pathNotFoundRenderer=dummy)._pathNotFoundRenderer,
            dummy)


    def test_pathFactory(self):
        """
        L{Path._pathFactory} defaults to L{Path}.
        """
        self.assertIdentical(
            static.Path()._pathFactory.func,
            static.Path)


    def test_pathFactoryOverride(self):
        """
        L{Path.__init__} accepts a C{pathFactory} argument
        which is assigned to the C{_pathFactory} attribute.
        """
        dummy = lambda:None
        self.assertIdentical(
            static.Path(pathFactory=dummy)._pathFactory.func,
            dummy)


    def test_pathFactoryTypeError(self):
        """
        If the C{pathFactory} argument supplied to L{Path.__init__} is not
        callable, a L{TypeError} is raised.
        """
        self.assertRaises(
            TypeError,
            static.Path, pathFactory=object())


    def test_redirectRenderer(self):
        """
        L{Path._redirectRenderer} defaults to L{util.Redirect}.
        """
        self.assertIdentical(
            util.Redirect,
            static.Path()._redirectRenderer,
        )


    def test_redirectRendererOverride(self):
        """
        L{Path.__init__} accepts a C{redirectRenderer} argument
        which is assigned to the C{_redirectRenderer} attribute.
        """
        dummy = object()
        self.assertIdentical(
            static.Path(redirectRenderer=dummy)._redirectRenderer,
            dummy)


    def test_interface(self):
        """
        L{Path} implements L{IResource}.
        """
        self.assertTrue(
            verifyClass(resource.IResource, static.Path))


    def test_getChildWithDefaultRootTrailingSlashDirectory(self):
        """
        If L{Path.getChildWithDefault} receives an empty name argument it
        means the resource is handling the root path "/". If the
        current path is a directory, it calls C{directoryRenderer}
        with the current path and returns the result.
        """
        dummyDir = MemoryDir()
        self.assertIdentical(
            dummyDir,
            static.Path(
                filePath=dummyDir,
                directoryRenderer=lambda path: path).getChildWithDefault(
                    name='', request=None)
        )


    def test_getChildWithDefaultRootTrailingSlashFile(self):
        """
        If L{Path.getChildWithDefault} receives an empty name argument it
        means the resource is handling the root path "/". If the
        current path is a file, it calls C{fileRenderer}
        with the current path and returns the result.
        """
        dummyFile = MemoryFile()
        self.assertIdentical(
            dummyFile,
            static.Path(
                filePath=dummyFile,
                fileRenderer=lambda path: path).getChildWithDefault(
                    name='', request=None)
        )


    def test_getChildWithDefaultInsecurePath(self):
        """
        If the supplied C{name} triggers a L{file.InsecurePath} exception
        the request is handled by C{pathNotFoundHandler}.
        """
        dummy = object()
        self.assertEqual(
            dummy,
            static.Path(
                filePath=MemoryDir(child=InsecurePath()),
                pathNotFoundRenderer=lambda: dummy).getChildWithDefault(
                    name='ignored', request=None)
        )


    def test_getChildWithDefaultNotFound(self):
        """
        If the requested name is not a child of the current directory
        a 404 renderer is returned.
        """
        dummy = object()

        self.assertEqual(
            static.Path(
                filePath=MemoryDir(child=MemoryPath(exists=False)),
                pathNotFoundRenderer=lambda: dummy).getChildWithDefault(
                    name='nonexistent', request=None),
            dummy)


    def test_getChildWithDefaultFoundDirectoryWithTrailingSlash(self):
        """
        L{Path.getChildWithDefault} calls C{directoryRenderer} with the
        child path and returns the result -- when the supplied C{name}
        matches a known child of the current path and the supplied
        C{request} has a single empty postpath segment (ie url has
        trailing slash) and the child is a directory.
        """
        dummyResult = object()
        dummyChildDir = MemoryDir()

        def dummyDirectoryRenderer(path):
            self.assertIdentical(dummyChildDir, path)
            return dummyResult

        f = static.Path(
            filePath=MemoryDir(child=dummyChildDir),
            directoryRenderer=dummyDirectoryRenderer)

        self.assertIdentical(
            dummyResult,
            f.getChildWithDefault(
                name='exists', request=DummyRequest(postpath=[''])))


    def test_getChildWithDefaultFoundFileWithTrailingSlash(self):
        """
        L{Path.getChildWithDefault} calls C{pathNotFoundRenderer}
        and returns the result -- when the supplied C{name}
        matches a known child of the current path and the supplied
        C{request} has a single empty postpath segment (ie url has
        trailing slash) and the child is a file.
        """
        dummyResult = object()
        dummyChildFile = MemoryFile()

        def dummyPathNotFoundRenderer():
            return dummyResult

        f = static.Path(
            filePath=MemoryDir(child=dummyChildFile),
            pathNotFoundRenderer=dummyPathNotFoundRenderer)

        self.assertIdentical(
            dummyResult,
            f.getChildWithDefault(
                name='exists', request=DummyRequest(postpath=[''])))


    def test_getChildWithDefaultConstructorArgumentPassing(self):
        """
        L{Path.getChildWithDefault} calls C{pathFactory} with all
        arguments passed to the original constructor and returns the
        result -- when the supplied C{name} matches a known child of
        the current path and the supplied C{request} postpath has a
        non-empty first segment (ie we are currently handling a
        non-leaf segment of the url).
        """
        class DummyPathFactory(object):
            def __init__(self, filePath, *args, **kwargs):
                self.filePath = filePath
                self.args = args
                self.kwargs = kwargs

        dummyFile = MemoryPath(exists=True)
        kwargs = dict(
            fileRenderer=object(),
            directoryRenderer=object(),
            pathNotFoundRenderer=object(),
            pathFactory=DummyPathFactory,
            redirectRenderer=object())

        f = static.Path(
            filePath=MemoryDir(child=dummyFile), **kwargs)
        result = f.getChildWithDefault(
            name='exists', request=DummyRequest(postpath=['childname']))

        self.assertEqual(
            (dummyFile, (), kwargs),
            (result.filePath, result.args, result.kwargs)
        )


    def test_getChildWithDefaultFinalSegmentDirectory(self):
        """
        L{Path.getChildWithDefault} calls C{redirectRenderer} and returns
        the result -- when the supplied C{name} matches a known child
        directory of the current path and the supplied C{request}
        postpath is empty (ie we are currently handling a leaf segment
        of the url and it is a directory which has been requested
        without a trailing slash -- so we we send a redirect to add
        the trailing slash.).
        """
        dummyRequest = requestFromUrl(b'http://example.com/exists')
        dummyRequest.postpath = []

        dummyResult = object()

        f = static.Path(
            filePath=MemoryDir(child=MemoryDir(exists=True)),
            redirectRenderer=lambda url: (url, dummyResult))

        result = f.getChildWithDefault(
            name='exists', request=dummyRequest)

        self.assertEqual(
            (b'http://example.com/exists/', dummyResult),
            result
        )


    def test_getChildWithDefaultFinalSegmentFile(self):
        """
        L{Path.getChildWithDefault} calls C{fileRenderer} and returns
        the result -- when the supplied C{name} matches a known child
        file of the current path and the supplied C{request}
        postpath is empty (ie we are currently handling a leaf segment
        of the url and it is a file).
        """
        dummyFile = MemoryFile(exists=True)
        dummyResult = object()
        f = static.Path(
            filePath=MemoryDir(child=dummyFile),
            fileRenderer=lambda path: (path, dummyResult))

        result = f.getChildWithDefault(
            name='exists', request=DummyRequest(postpath=[]))

        self.assertEqual(
            (dummyFile, dummyResult),
            result
        )



class FilePathRendererTests(TestCase):
    """
    Tests for L{FilePathRenderer}.
    """
    def test_interface(self):
        """
        L{FilePathRenderer} implements L{IResource}.
        """
        self.assertTrue(
            verifyClass(resource.IResource, static.FilePathRenderer))



class DirectoryPathRendererTests(TestCase):
    """
    Tests for L{DirectoryPathRenderer}.
    """

    def test_filePath(self):
        """
        L{DirectoryPathRenderer._filePath} defaults to C{FilePath('.')}
        """
        self.assertEqual(static.DirectoryPathRenderer()._filePath,
                         FilePath('.'))


    def test_filePathDirectoryAssertion(self):
        """
        L{DirectoryPathRenderer.__init__} raises an L{ValueError} if
        C{filePath} argument is not a directory.
        """
        self.assertRaises(
            ValueError,
            static.DirectoryPathRenderer, filePath=MemoryFile())


    def test_filePathOverride(self):
        """
        L{DirectoryPathRenderer.__init__} accepts a C{filePath} argument
        which is assigned to the C{_filePath} attribute.
        """
        dummy = MemoryDir()
        self.assertIdentical(
            static.DirectoryPathRenderer(filePath=dummy)._filePath,
            dummy)


    def test_indexNames(self):
        """
        L{DirectoryPathRenderer._indexNames} is a list of filenames which
        are considered to be directory indexes.
        """
        self.assertEqual(
            static.DirectoryPathRenderer._indexNames,
            ("index", "index.html", "index.htm", "index.rpy"))


    def test_indexNamesOverride(self):
        """
        L{DirectoryPathRenderer.__init__} accepts an C{indexNames}
        argument which is assigned to
        L{DirectoryPathRenderer._indexNames}.
        """
        self.assertEqual(
            static.DirectoryPathRenderer(
                indexNames=('foo', 'bar'))._indexNames,
            ("foo", "bar"))


    def test_pathNotFoundRenderer(self):
        """
        L{DirectoryPathRenderer._pathNotFoundRenderer} defaults to
        L{resource.ForbiddenResource}.
        """
        self.assertIdentical(
            static.DirectoryPathRenderer()._pathNotFoundRenderer,
            resource.ForbiddenResource)


    def test_pathNotFoundRendererOverride(self):
        """
        L{DirectoryPathRenderer.__init__} accepts a
        C{pathNotFoundRenderer} argument which is assigned to the
        C{_pathNotFoundRenderer} attribute.
        """
        dummy = lambda: None
        self.assertIdentical(
            static.DirectoryPathRenderer(
                pathNotFoundRenderer=dummy)._pathNotFoundRenderer,
            dummy)


    def test_fileRenderer(self):
        """
        L{DirectoryPathRenderer._fileRenderer} defaults to
        L{static.FilePathRenderer}.
        """
        self.assertIdentical(
            static.DirectoryPathRenderer()._fileRenderer,
            static.FilePathRenderer)


    def test_fileRendererOverride(self):
        """
        L{DirectoryPathRenderer.__init__} accepts a
        C{fileRenderer} argument which is assigned to the
        C{_fileRenderer} attribute.
        """
        dummy = lambda: None
        self.assertIdentical(
            static.DirectoryPathRenderer(
                fileRenderer=dummy)._fileRenderer,
            dummy)


    def test_interface(self):
        """
        L{DirectoryPathRenderer} implements L{IResource}.
        """
        self.assertTrue(
            verifyClass(resource.IResource, static.DirectoryPathRenderer))


    def test_renderRefuseUnsupportedMethod(self):
        """
        L{DirectoryPathRenderer.render} raises L{UnsupportedMethod} in
        response to a non-I{GET}, non-I{HEAD} request.
        """
        e = self.assertRaises(
            UnsupportedMethod,
            static.DirectoryPathRenderer().render,
            DummyRequestPost(postpath=None))
        self.assertEqual(e.allowedMethods, (b'GET', b'HEAD'))


    def test_renderFound(self):
        """
        If the directory contains one of C{indexNames},
        L{DirectoryPathRenderer.render} generates a response by
        instantiating C{self._fileRenderer} with C{filePath} and
        calling its render method with C{request}.
        """
        dummyResponse = object()
        dummyFile = MemoryFile(exists=True)
        files = []
        dummyRequest = DummyRequestHead(postpath=None)
        requests = []
        class DummyFilePathResource(object):
            def __init__(self, filePath=None):
                files.append(filePath)

            def render(self, request):
                requests.append(request)
                return dummyResponse

        response = static.DirectoryPathRenderer(
            filePath=MemoryDir(child=dummyFile),
            fileRenderer=DummyFilePathResource).render(
                request=dummyRequest)

        self.assertEqual(
            (dummyResponse, [dummyFile], [dummyRequest]),
            (response, files, requests))


    def test_renderNotFound(self):
        """
        If the directory does not contain any of C{indexNames},
        L{DirectoryPathRenderer.render} generates a response by
        instantiating C{self._pathNotFoundRenderer} with C{filePath} and
        calling its render method with C{request}.
        """
        dummyResponse = object()
        dummyDir = MemoryDir(child=MemoryFile(exists=False))
        files = []
        dummyRequest = DummyRequestHead(postpath=None)
        requests = []
        class DummyPathNotFoundResource(object):
            def __init__(self, filePath):
                files.append(filePath)
            def render(self, request):
                requests.append(request)
                return dummyResponse

        response = static.DirectoryPathRenderer(
            filePath=dummyDir,
            pathNotFoundRenderer=DummyPathNotFoundResource).render(
                request=dummyRequest)

        self.assertEqual(
            (dummyResponse, [dummyDir], [dummyRequest]),
            (response, files, requests))



class ForbiddenResourceTests(TestCase):
    """
    """
    # These tests need moving to a new NotFoundResource, ForbiddenResource
    def test_renderNotFound(self):
        """
        L{ForbiddenResource.render} sets the request responseCode to
        C{FORBIDDEN}.
        """
        request = DummyRequestHead(postpath=None)
        resource.ForbiddenResource().render(request=request)
        self.assertEqual(request.responseCode, resource.FORBIDDEN)


    def test_renderHeadNoContent(self):
        """
        L{ForbiddenResource.render} returns C{b''} for I{HEAD} requests.
        """
        self.assertEqual(
            resource.ForbiddenResource().render(
                request=DummyRequestHead(postpath=None)),
            b'')
    test_renderHeadNoContent.skip = (
        "XXX: Resources shouldn't return content for HEAD requests. Right?")


    def test_renderGetContent(self):
        """
        L{ForbiddenResource.render} returns a message for I{GET} requests.
        """
        self.assertIn(
            b'Sorry, resource is forbidden.',
            resource.ForbiddenResource().render(
                request=DummyRequestHead(postpath=None)))



class AddSlashTests(TestCase):
    def test_addSlash(self):
        """
        L{static.addSlash} takes an L{http.Request} object and returns the
        url of the request with an added slash.
        """
        self.assertEqual(
            static.addSlash(requestFromUrl(b'http://example.com/foo')),
            b'http://example.com/foo/')


    def test_trailingSlash(self):
        """
        If the supplied L{http.Request} object already represents a url
        with a trailing slash L{static.addSlash} adds another slash.
        """
        self.assertEqual(
            static.addSlash(requestFromUrl(b'http://example.com/foo/')),
            b'http://example.com/foo//')


    def test_queryString(self):
        """
        If the supplied L{http.Request} object has a url with a
        querystring L{static.addSlash} adds the slash between the path
        and the querystring.
        """
        self.assertEqual(
            static.addSlash(
                requestFromUrl(b'http://example.com/foo?bar=baz')),
            b'http://example.com/foo/?bar=baz')


    def test_queryStringContainingQuestionMark(self):
        """
        If the supplied L{http.Request} object has a url with a
        querystring containing multiple question marks,
        L{static.addSlash} leaves the them in place.
        """
        self.assertEqual(
            static.addSlash(
                requestFromUrl(b'http://example.com/foo?bar=baz?qux')),
            b'http://example.com/foo/?bar=baz?qux')


    def test_secure(self):
        """
        If the supplied L{http.Request} object isSecure the url scheme is
        set to https.
        """
        self.assertEqual(
            static.addSlash(requestFromUrl(b'https://www.example.com/foo')),
            b'https://www.example.com/foo/')



class RemoveSlashTests(TestCase):
    def test_removeSlash(self):
        """
        L{static.removeSlash} takes an L{http.Request} object and returns
        the url of the request with the trailing slash removed.
        """
        self.assertEqual(
            static.removeSlash(requestFromUrl('http://example.com/foo/')),
            b'http://example.com/foo')


    def test_noTrailingSlash(self):
        """
        If the supplied L{http.Request} url doesn't have a trailing slash
        L{static.removeSlash} returns the url unaltered.
        """
        self.assertEqual(
            static.removeSlash(requestFromUrl(b'http://example.com/foo')),
            b'http://example.com/foo')


    def test_multipleTrailingSlashes(self):
        """
        If the supplied L{http.Request} url has multiple trailing slashes
        L{static.removeSlash} removes them all.
        """
        self.assertEqual(
            static.removeSlash(requestFromUrl('http://example.com/foo//')),
            b'http://example.com/foo')


    def test_queryString(self):
        """
        If the supplied L{http.Request} object has a url with a
        querystring, L{static.removeSlash} removes the slash from
        between the path and the querystring.
        """
        self.assertEqual(
            static.removeSlash(
                requestFromUrl(b'http://example.com/foo/?bar=baz')),
            b'http://example.com/foo?bar=baz')


    def test_queryStringContainingQuestionMark(self):
        """
        If the supplied L{http.Request} object has a url with a
        querystring containing multiple question marks,
        L{static.removeSlash} leaves them intact.
        """
        self.assertEqual(
            static.removeSlash(
                requestFromUrl(b'http://example.com/foo/?bar=baz?qux')),
            b'http://example.com/foo?bar=baz?qux')


    def test_secure(self):
        """
        If the supplied L{http.Request} object isSecure the url scheme is
        set to https.
        """
        self.assertEqual(
            static.removeSlash(requestFromUrl(b'https://example.com/foo/')),
            b'https://example.com/foo')
