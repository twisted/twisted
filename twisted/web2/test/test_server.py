# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A test harness for the twisted.web2 server.
"""

from zope.interface import implements

from twisted.python import components
from twisted.web2 import http, http_headers, iweb, server
from twisted.web2 import resource, stream, compat
from twisted.trial import unittest
from twisted.internet import reactor, defer, address



class NotResource(object):
    """
    Class which does not implement IResource.

    Used as an adaptee by L{AdaptionTestCase.test_registered} to test that
    if an object which does not provide IResource is adapted to IResource
    and there is an adapter to IResource registered, that adapter is used.
    """



class ResourceAdapter(object):
    """
    Adapter to IResource.

    Registered as an adapter from NotResource to IResource so that
    L{AdaptionTestCase.test_registered} can test that such an adapter will
    be used.
    """
    implements(iweb.IResource)

    def __init__(self, original):
        pass

components.registerAdapter(ResourceAdapter, NotResource, iweb.IResource)



class NotOldResource(object):
    """
    Class which does not implement IOldNevowResource or IResource.

    Used as an adaptee by L{AdaptionTestCase.test_transitive} to test that
    if an object which does not provide IResource or IOldNevowResource is
    adapted to IResource and there is an adapter to IOldNevowResource
    registered, first that adapter is used, then the included adapter from
    IOldNevowResource to IResource is used.
    """



class OldResourceAdapter(object):
    """
    Adapter to IOldNevowResource.

    Registered as an adapter from NotOldResource to IOldNevowResource so
    that L{AdaptionTestCase.test_transitive} can test that such an adapter
    will be used to allow the initial input to be adapted to IResource.
    """
    implements(iweb.IOldNevowResource)

    def __init__(self, original):
        pass

components.registerAdapter(OldResourceAdapter, NotOldResource, iweb.IOldNevowResource)



class AdaptionTestCase(unittest.TestCase):
    """
    Test the adaption of various objects to IResource.

    Necessary due to the special implementation of __call__ on IResource
    which extends the behavior provided by the base Interface.__call__.
    """
    def test_unadaptable(self):
        """
        Test that attempting to adapt to IResource an object not adaptable
        to IResource raises an exception or returns the specified alternate
        object.
        """
        class Unadaptable(object):
            pass
        self.assertRaises(TypeError, iweb.IResource, Unadaptable())
        alternate = object()
        self.assertIdentical(iweb.IResource(Unadaptable(), alternate), alternate)


    def test_redundant(self):
        """
        Test that the adaption to IResource of an object which provides
        IResource returns the same object.
        """
        class Resource(object):
            implements(iweb.IResource)
        resource = Resource()
        self.assertIdentical(iweb.IResource(resource), resource)


    def test_registered(self):
        """
        Test that if an adapter exists which can provide IResource for an
        object which does not provide it, that adapter is used.
        """
        notResource = NotResource()
        self.failUnless(isinstance(iweb.IResource(notResource), ResourceAdapter))


    def test_oldResources(self):
        """
        Test that providers of L{IOldNevowResource} can be adapted to
        IResource automatically.
        """
        class OldResource(object):
            implements(iweb.IOldNevowResource)
        oldResource = OldResource()
        resource = iweb.IResource(oldResource)
        self.failUnless(isinstance(resource, compat.OldNevowResourceAdapter))


    def test_transitive(self):
        """
        Test that a special-case transitive adaption from something to
        IOldNevowResource to IResource is possible.
        """
        notResource = NotOldResource()
        resource = iweb.IResource(notResource)
        self.failUnless(isinstance(resource, compat.OldNevowResourceAdapter))



class SimpleRequest(server.Request):
    """I can be used in cases where a Request object is necessary
    but it is benificial to bypass the chanRequest
    """

    clientproto = (1,1)

    def __init__(self, site, method, uri, headers=None, content=None):
        if not headers:
            headers = http_headers.Headers(headers)

        super(SimpleRequest, self).__init__(
            site=site,
            chanRequest=None,
            command=method,
            path=uri,
            version=self.clientproto,
            contentLength=len(content or ''),
            headers=headers)

        self.stream = stream.MemoryStream(content or '')

        self.remoteAddr = address.IPv4Address('TCP', '127.0.0.1', 0)
        self._parseURL()
        self.host = 'localhost'
        self.port = 8080

    def writeResponse(self, response):
        return response


class TestChanRequest:
    implements(iweb.IChanRequest)

    hostInfo = address.IPv4Address('TCP', 'host', 80), False
    remoteHost = address.IPv4Address('TCP', 'remotehost', 34567)


    def __init__(self, site, method, prepath, uri, length=None,
                 headers=None, version=(1,1), content=None):
        self.site = site
        self.method = method
        self.prepath = prepath
        self.uri = uri
        if headers is None:
            headers = http_headers.Headers()
        self.headers = headers
        self.http_version = version
        # Anything below here we do not pass as arguments
        self.request = server.Request(self,
                                      self.method,
                                      self.uri,
                                      self.http_version,
                                      length,
                                      self.headers,
                                      site=self.site,
                                      prepathuri=self.prepath)

        if content is not None:
            self.request.handleContentChunk(content)
            self.request.handleContentComplete()

        self.code = None
        self.responseHeaders = None
        self.data = ''
        self.deferredFinish = defer.Deferred()

    def writeIntermediateResponse(code, headers=None):
        pass

    def writeHeaders(self, code, headers):
        self.responseHeaders = headers
        self.code = code

    def write(self, data):
        self.data += data

    def finish(self, failed=False):
        result = self.code, self.responseHeaders, self.data, failed
        self.finished = True
        self.deferredFinish.callback(result)

    def abortConnection(self):
        self.finish(failed=True)

    def registerProducer(self, producer, streaming):
        pass

    def unregisterProducer(self):
        pass

    def getHostInfo(self):
        return self.hostInfo

    def getRemoteHost(self):
        return self.remoteHost


class BaseTestResource(resource.Resource):
    responseCode = 200
    responseText = 'This is a fake resource.'
    responseHeaders = {}
    addSlash = False

    def __init__(self, children=[]):
        """
        @type children: C{list} of C{tuple}
        @param children: a list of ('path', resource) tuples
        """
        for i in children:
            self.putChild(i[0], i[1])

    def render(self, req):
        return http.Response(self.responseCode, headers=self.responseHeaders,
                             stream=self.responseStream())

    def responseStream(self):
        return stream.MemoryStream(self.responseText)



_unset = object()
class BaseCase(unittest.TestCase):
    """
    Base class for test cases that involve testing the result
    of arbitrary HTTP(S) queries.
    """

    method = 'GET'
    version = (1, 1)
    wait_timeout = 5.0

    def chanrequest(self, root, uri, length, headers, method, version, prepath, content):
        site = server.Site(root)
        return TestChanRequest(site, method, prepath, uri, length, headers, version, content)

    def getResponseFor(self, root, uri, headers={},
                       method=None, version=None, prepath='', content=None, length=_unset):
        if not isinstance(headers, http_headers.Headers):
            headers = http_headers.Headers(headers)
        if length is _unset:
            if content is not None:
                length = len(content)
            else:
                length = 0

        if method is None:
            method = self.method
        if version is None:
            version = self.version

        cr = self.chanrequest(root, uri, length, headers, method, version, prepath, content)
        cr.request.process()
        return cr.deferredFinish

    def assertResponse(self, request_data, expected_response, failure=False):
        """
        @type request_data: C{tuple}
        @type expected_response: C{tuple}
        @param request_data: A tuple of arguments to pass to L{getResponseFor}:
                             (root, uri, headers, method, version, prepath).
                             Root resource and requested URI are required,
                             and everything else is optional.
        @param expected_response: A 3-tuple of the expected response:
                                  (responseCode, headers, htmlData)
        """
        d = self.getResponseFor(*request_data)
        d.addCallback(self._cbGotResponse, expected_response, failure)

        return d

    def _cbGotResponse(self, (code, headers, data, failed), expected_response, expectedfailure=False):
        expected_code, expected_headers, expected_data = expected_response
        self.assertEquals(code, expected_code)
        if expected_data is not None:
            self.assertEquals(data, expected_data)
        for key, value in expected_headers.iteritems():
            self.assertEquals(headers.getHeader(key), value)
        self.assertEquals(failed, expectedfailure)



class SampleWebTest(BaseCase):
    class SampleTestResource(BaseTestResource):
        addSlash = True
        def child_validChild(self, req):
            f = BaseTestResource()
            f.responseCode = 200
            f.responseText = 'This is a valid child resource.'
            return f

        def child_missingChild(self, req):
            f = BaseTestResource()
            f.responseCode = 404
            f.responseStream = lambda self: None
            return f

        def child_remoteAddr(self, req):
            f = BaseTestResource()
            f.responseCode = 200
            f.responseText = 'Remote Addr: %r' % req.remoteAddr.host
            return f

    def setUp(self):
        self.root = self.SampleTestResource()

    def test_root(self):
        return self.assertResponse(
            (self.root, 'http://host/'),
            (200, {}, 'This is a fake resource.'))

    def test_validChild(self):
        return self.assertResponse(
            (self.root, 'http://host/validChild'),
            (200, {}, 'This is a valid child resource.'))

    def test_invalidChild(self):
        return self.assertResponse(
            (self.root, 'http://host/invalidChild'),
            (404, {}, None))

    def test_remoteAddrExposure(self):
        return self.assertResponse(
            (self.root, 'http://host/remoteAddr'),
            (200, {}, "Remote Addr: 'remotehost'"))

    def test_leafresource(self):
        class TestResource(resource.LeafResource):
            def render(self, req):
                return http.Response(stream="prepath:%s postpath:%s" % (
                        req.prepath,
                        req.postpath))

        return self.assertResponse(
            (TestResource(), 'http://host/consumed/path/segments'),
            (200, {}, "prepath:[] postpath:['consumed', 'path', 'segments']"))

    def test_redirectResource(self):
        redirectResource = resource.RedirectResource(scheme='https',
                                                     host='localhost',
                                                     port=443,
                                                     path='/foo',
                                                     querystring='bar=baz')

        return self.assertResponse(
            (redirectResource, 'http://localhost/'),
            (301, {'location': 'https://localhost/foo?bar=baz'}, None))


class URLParsingTest(BaseCase):
    class TestResource(resource.LeafResource):
        def render(self, req):
            return http.Response(stream="Host:%s, Path:%s"%(req.host, req.path))

    def setUp(self):
        self.root = self.TestResource()

    def test_normal(self):
        return self.assertResponse(
            (self.root, '/path', {'Host':'host'}),
            (200, {}, 'Host:host, Path:/path'))

    def test_fullurl(self):
        return self.assertResponse(
            (self.root, 'http://host/path'),
            (200, {}, 'Host:host, Path:/path'))

    def test_strangepath(self):
        # Ensure that the double slashes don't confuse it
        return self.assertResponse(
            (self.root, '//path', {'Host':'host'}),
            (200, {}, 'Host:host, Path://path'))

    def test_strangepathfull(self):
        return self.assertResponse(
            (self.root, 'http://host//path'),
            (200, {}, 'Host:host, Path://path'))



class TestDeferredRendering(BaseCase):
    class ResourceWithDeferreds(BaseTestResource):
        addSlash=True
        responseText = 'I should be wrapped in a Deferred.'
        def render(self, req):
            d = defer.Deferred()
            reactor.callLater(
                0, d.callback, BaseTestResource.render(self, req))
            return d

        def child_deferred(self, req):
            d = defer.Deferred()
            reactor.callLater(0, d.callback, BaseTestResource())
            return d

    def test_deferredRootResource(self):
        return self.assertResponse(
            (self.ResourceWithDeferreds(), 'http://host/'),
            (200, {}, 'I should be wrapped in a Deferred.'))

    def test_deferredChild(self):
        return self.assertResponse(
            (self.ResourceWithDeferreds(), 'http://host/deferred'),
            (200, {}, 'This is a fake resource.'))



class RedirectResourceTest(BaseCase):
    def html(url):
        return "<html><head><title>Moved Permanently</title></head><body><h1>Moved Permanently</h1><p>Document moved to %s.</p></body></html>" % (url,)
    html = staticmethod(html)

    def test_noRedirect(self):
        # This is useless, since it's a loop, but hey
        ds = []
        for url in ("http://host/", "http://host/foo"):
            ds.append(self.assertResponse(
                (resource.RedirectResource(), url),
                (301, {"location": url}, self.html(url))
            ))
        return defer.DeferredList(ds, fireOnOneErrback=True)

    def test_hostRedirect(self):
        ds = []
        for url1, url2 in (
            ("http://host/", "http://other/"),
            ("http://host/foo", "http://other/foo"),
        ):
            ds.append(self.assertResponse(
                (resource.RedirectResource(host="other"), url1),
                (301, {"location": url2}, self.html(url2))
            ))
        return defer.DeferredList(ds, fireOnOneErrback=True)

    def test_pathRedirect(self):
        root = BaseTestResource()
        redirect = resource.RedirectResource(path="/other")
        root.putChild("r", redirect)

        ds = []
        for url1, url2 in (
            ("http://host/r", "http://host/other"),
            ("http://host/r/foo", "http://host/other"),
        ):
            ds.append(self.assertResponse(
                (resource.RedirectResource(path="/other"), url1),
                (301, {"location": url2}, self.html(url2))
            ))
        return defer.DeferredList(ds, fireOnOneErrback=True)



class EmptyResource(resource.Resource):
    def __init__(self, test):
        self.test = test

    def render(self, request):
        self.test.assertEquals(request.urlForResource(self), self.expectedURI)
        return 201



class RememberURIs(BaseCase):
    """
    Tests for URI memory and lookup mechanism in server.Request.
    """
    def test_requestedResource(self):
        """
        Test urlForResource() on deeply nested resource looked up via
        request processing.
        """
        root = EmptyResource(self)
        root.expectedURI = "/"

        foo = EmptyResource(self)
        foo.expectedURI = "/foo"
        root.putChild("foo", foo)

        bar = EmptyResource(self)
        bar.expectedURI = foo.expectedURI + "/bar"
        foo.putChild("bar", bar)

        baz = EmptyResource(self)
        baz.expectedURI = bar.expectedURI + "/baz"
        bar.putChild("baz", baz)

        ds = []

        for uri in (foo.expectedURI, bar.expectedURI, baz.expectedURI):
            ds.append(self.assertResponse(
                (root, uri, {'Host':'host'}),
                (201, {}, None),
            ))

        return defer.DeferredList(ds, fireOnOneErrback=True)

    def test_urlEncoding(self):
        """
        Test to make sure that URL encoding is working.
        """
        root = EmptyResource(self)
        root.expectedURI = "/"

        child = EmptyResource(self)
        child.expectedURI = "/foo%20bar"

        root.putChild("foo bar", child)

        return self.assertResponse(
            (root, child.expectedURI, {'Host':'host'}),
            (201, {}, None)
        )

    def test_locateResource(self):
        """
        Test urlForResource() on resource looked up via a locateResource() call.
        """
        root = resource.Resource()
        child = resource.Resource()
        root.putChild("foo", child)

        request = SimpleRequest(server.Site(root), "GET", "/")

        def gotResource(resource):
            self.assertEquals("/foo", request.urlForResource(resource))

        d = defer.maybeDeferred(request.locateResource, "/foo")
        d.addCallback(gotResource)
        return d

    def test_unknownResource(self):
        """
        Test urlForResource() on unknown resource.
        """
        root = resource.Resource()
        child = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/")

        self.assertRaises(server.NoURLForResourceError, request.urlForResource, child)

    def test_locateChildResource(self):
        """
        Test urlForResource() on deeply nested resource looked up via
        locateChildResource().
        """
        root = EmptyResource(self)
        root.expectedURI = "/"

        foo = EmptyResource(self)
        foo.expectedURI = "/foo"
        root.putChild("foo", foo)

        bar = EmptyResource(self)
        bar.expectedURI = "/foo/bar"
        foo.putChild("bar", bar)

        baz = EmptyResource(self)
        baz.expectedURI = "/foo/bar/b%20a%20z"
        bar.putChild("b a z", baz)

        request = SimpleRequest(server.Site(root), "GET", "/")

        def gotResource(resource):
            # Make sure locateChildResource() gave us the right answer
            self.assertEquals(resource, bar)

            return request.locateChildResource(resource, "b a z").addCallback(gotChildResource)

        def gotChildResource(resource):
            # Make sure locateChildResource() gave us the right answer
            self.assertEquals(resource, baz)

            self.assertEquals(resource.expectedURI, request.urlForResource(resource))

        d = request.locateResource(bar.expectedURI)
        d.addCallback(gotResource)
        return d

    def test_deferredLocateChild(self):
        """
        Test deferred value from locateChild()
        """
        class DeferredLocateChild(resource.Resource):
            def locateChild(self, req, segments):
                return defer.maybeDeferred(
                    super(DeferredLocateChild, self).locateChild,
                    req, segments
                )

        root = DeferredLocateChild()
        child = resource.Resource()
        root.putChild("foo", child)

        request = SimpleRequest(server.Site(root), "GET", "/foo")

        def gotResource(resource):
            self.assertEquals("/foo", request.urlForResource(resource))

        d = request.locateResource("/foo")
        d.addCallback(gotResource)
        return d



class ParsePostDataTests(unittest.TestCase):
    """
    Tests for L{server.parsePOSTData}.
    """

    def test_noData(self):
        """
        Parsing a request without data should succeed but should not fill the
        C{args} and C{files} attributes of the request.
        """
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/")
        def cb(ign):
            self.assertEquals(request.args, {})
            self.assertEquals(request.files, {})
        return server.parsePOSTData(request).addCallback(cb)


    def test_noContentType(self):
        """
        Parsing a request without content-type should succeed but should not
        fill the C{args} and C{files} attributes of the request.
        """
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/", content="foo")
        def cb(ign):
            self.assertEquals(request.args, {})
            self.assertEquals(request.files, {})
        return server.parsePOSTData(request).addCallback(cb)


    def test_urlencoded(self):
        """
        Test parsing data in urlencoded format: it should end in the C{args}
        attribute.
        """
        ctype = http_headers.MimeType('application', 'x-www-form-urlencoded')
        content = "key=value&multiple=two+words&multiple=more%20words"
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        def cb(ign):
            self.assertEquals(request.files, {})
            self.assertEquals(request.args,
                {'multiple': ['two words', 'more words'], 'key': ['value']})
        return server.parsePOSTData(request).addCallback(cb)


    def test_multipart(self):
        """
        Test parsing data in multipart format: it should fill the C{files}
        attribute.
        """
        ctype = http_headers.MimeType('multipart', 'form-data',
                                      (('boundary', '---weeboundary'),))
        content="""-----weeboundary\r
Content-Disposition: form-data; name="FileNameOne"; filename="myfilename"\r
Content-Type: text/html\r
\r
my great content wooo\r
-----weeboundary--\r
"""
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        def cb(ign):
            self.assertEquals(request.args, {})
            self.assertEquals(request.files.keys(), ['FileNameOne'])
            self.assertEquals(request.files.values()[0][0][:2],
                  ('myfilename', http_headers.MimeType('text', 'html', {})))
            f = request.files.values()[0][0][2]
            self.assertEquals(f.read(), "my great content wooo")
        return server.parsePOSTData(request).addCallback(cb)


    def test_multipartWithNoBoundary(self):
        """
        If the boundary type is not specified, parsing should fail with a
        C{http.HTTPError}.
        """
        ctype = http_headers.MimeType('multipart', 'form-data')
        content="""-----weeboundary\r
Content-Disposition: form-data; name="FileNameOne"; filename="myfilename"\r
Content-Type: text/html\r
\r
my great content wooo\r
-----weeboundary--\r
"""
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        return self.assertFailure(server.parsePOSTData(request),
            http.HTTPError)


    def test_wrongContentType(self):
        """
        Check that a content-type not handled raise a C{http.HTTPError}.
        """
        ctype = http_headers.MimeType('application', 'foobar')
        content = "key=value&multiple=two+words&multiple=more%20words"
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        return self.assertFailure(server.parsePOSTData(request),
            http.HTTPError)


    def test_mimeParsingError(self):
        """
        A malformed content should result in a C{http.HTTPError}.
        
        The tested content has an invalid closing boundary.
        """
        ctype = http_headers.MimeType('multipart', 'form-data',
                                      (('boundary', '---weeboundary'),))
        content="""-----weeboundary\r
Content-Disposition: form-data; name="FileNameOne"; filename="myfilename"\r
Content-Type: text/html\r
\r
my great content wooo\r
-----weeoundary--\r
"""
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        return self.assertFailure(server.parsePOSTData(request),
            http.HTTPError)


    def test_multipartMaxMem(self):
        """
        Check that the C{maxMem} parameter makes the parsing raise an
        exception if the value is reached.
        """
        ctype = http_headers.MimeType('multipart', 'form-data',
                                      (('boundary', '---weeboundary'),))
        content="""-----weeboundary\r
Content-Disposition: form-data; name="FileNameOne"\r
Content-Type: text/html\r
\r
my great content wooo
and even more and more\r
-----weeboundary--\r
"""
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        def cb(res):
            self.assertEquals(res.response.description,
                "Maximum length of 10 bytes exceeded.")
        return self.assertFailure(server.parsePOSTData(request, maxMem=10),
            http.HTTPError).addCallback(cb)


    def test_multipartMaxSize(self):
        """
        Check that the C{maxSize} parameter makes the parsing raise an
        exception if the data is too big.
        """
        ctype = http_headers.MimeType('multipart', 'form-data',
                                      (('boundary', '---weeboundary'),))
        content="""-----weeboundary\r
Content-Disposition: form-data; name="FileNameOne"; filename="myfilename"\r
Content-Type: text/html\r
\r
my great content wooo
and even more and more\r
-----weeboundary--\r
"""
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        def cb(res):
            self.assertEquals(res.response.description,
                "Maximum length of 10 bytes exceeded.")
        return self.assertFailure(server.parsePOSTData(request, maxSize=10),
            http.HTTPError).addCallback(cb)


    def test_maxFields(self):
        """
        Check that the C{maxSize} parameter makes the parsing raise an
        exception if the data contains too many fields.
        """
        ctype = http_headers.MimeType('multipart', 'form-data',
                                      (('boundary', '---xyz'),))
        content = """-----xyz\r
Content-Disposition: form-data; name="foo"\r
\r
Foo Bar\r
-----xyz\r
Content-Disposition: form-data; name="foo"\r
\r
Baz\r
-----xyz\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/html\r
\r
blah\r
-----xyz\r
Content-Disposition: form-data; name="file"; filename="filename"\r
Content-Type: text/plain\r
\r
bleh\r
-----xyz--\r
"""
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        def cb(res):
            self.assertEquals(res.response.description,
                "Maximum number of fields 3 exceeded")
        return self.assertFailure(server.parsePOSTData(request, maxFields=3),
            http.HTTPError).addCallback(cb)


    def test_otherErrors(self):
        """
        Test that errors durign parsing other than C{MimeFormatError} are
        propagated.
        """
        ctype = http_headers.MimeType('multipart', 'form-data',
                                      (('boundary', '---weeboundary'),))
        # XXX: maybe this is not a good example
        # parseContentDispositionFormData could handle this problem
        content="""-----weeboundary\r
Content-Disposition: form-data; name="FileNameOne"; filename="myfilename and invalid data \r
-----weeboundary--\r
"""
        root = resource.Resource()
        request = SimpleRequest(server.Site(root), "GET", "/",
                http_headers.Headers({'content-type': ctype}), content)
        return self.assertFailure(server.parsePOSTData(request),
            ValueError)

