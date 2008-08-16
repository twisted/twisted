# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.wsgi}.
"""

__metaclass__ = type

from sys import exc_info
from urllib import quote
from StringIO import StringIO
from thread import get_ident

from zope.interface.verify import verifyObject

from twisted.python.compat import set
from twisted.python.log import addObserver, removeObserver
from twisted.python.threadpool import ThreadPool
from twisted.internet.defer import Deferred, gatherResults
from twisted.internet import reactor
from twisted.trial.unittest import TestCase
from twisted.web.resource import IResource, Resource
from twisted.web.server import Request, Site
from twisted.web.wsgi import WSGIResource
from twisted.web.test.test_web import DummyChannel


class SynchronousThreadPool:
    """
    A single-threaded implementation of part of the L{ThreadPool} interface.
    This implementation calls functions synchronously rather than running
    them in a thread pool.  It is used to make the tests which are not
    directly for thread-related behavior deterministic.
    """
    def callInThread(self, f, *a, **kw):
        """
        Call C{f(*a, **kw)} in this thread rather than scheduling it to be
        called in a thread.
        """
        f(*a, **kw)



class SynchronousReactorThreads:
    """
    A single-threaded implementation of part of the L{IReactorThreads}
    interface.  This implementation assumes that it will only be invoked
    from the reactor thread, so it calls functions synchronously rather than
    trying to schedule them to run in the reactor thread.  It is used in
    conjunction with L{SynchronousThreadPool} to make the tests which are
    not directly for thread-related behavior deterministic.
    """
    def callFromThread(self, f, *a, **kw):
        """
        Call C{f(*a, **kw)} in this thread which should also be the reactor
        thread.
        """
        f(*a, **kw)



class WSGIResourceTests(TestCase):
    def setUp(self):
        """
        Create a L{WSGIResource} with synchronous threading objects and a no-op
        application object.  This is useful for testing certain things about
        the resource implementation which are unrelated to WSGI.
        """
        self.resource = WSGIResource(
            SynchronousReactorThreads(), SynchronousThreadPool(),
            lambda environ, startResponse: None)


    def test_interfaces(self):
        """
        L{WSGIResource} implements L{IResource} and stops resource traversal.
        """
        verifyObject(IResource, self.resource)
        self.assertTrue(self.resource.isLeaf)


    def test_unsupported(self):
        """
        A L{WSGIResource} cannot have L{IResource} children.  Its
        C{getChildWithDefault} and C{putChild} methods raise L{RuntimeError}.
        """
        self.assertRaises(
            RuntimeError,
            self.resource.getChildWithDefault,
            "foo", Request(DummyChannel(), False))
        self.assertRaises(
            RuntimeError,
            self.resource.putChild,
            "foo", Resource())


class WSGITestsMixin:
    """
    @ivar channelFactory: A no-argument callable which will be invoked to
        create a new HTTP channel to associate with request objects.
    """
    channelFactory = DummyChannel

    def setUp(self):
        self.threadpool = SynchronousThreadPool()
        self.reactor = SynchronousReactorThreads()


    def lowLevelRender(
        self, requestFactory, applicationFactory, channelFactory, method,
        version, resourceSegments, requestSegments, query=None, headers=[],
        body=None, safe=''):
        """
        @param method: A C{str} giving the request method to use.

        @param version: A C{str} like C{'1.1'} giving the request version.

        @param resourceSegments: A C{list} of unencoded path segments which
            specifies the location in the resource hierarchy at which the
            L{WSGIResource} will be placed, eg C{['']} for I{/}, C{['foo',
            'bar', '']} for I{/foo/bar/}, etc.

        @param requestSegments: A C{list} of unencoded path segments giving the
            request URI.

        @param query: A C{list} of two-tuples of C{str} giving unencoded query
            argument keys and values.

        @param headers: A C{list} of two-tuples of C{str} giving request header
            names and corresponding values.

        @param safe: A C{str} giving the bytes which are to be considered
            I{safe} for inclusion in the request URI and not quoted.

        @return: A L{Deferred} which will be called back with a two-tuple of
            the arguments passed which would be passed to the WSGI application
            object for this configuration and request (ie, the environment and
            start_response callable).
        """
        root = WSGIResource(
            self.reactor, self.threadpool, applicationFactory())
        resourceSegments.reverse()
        for seg in resourceSegments:
            tmp = Resource()
            tmp.putChild(seg, root)
            root = tmp

        channel = channelFactory()
        channel.site = Site(root)
        request = requestFactory(channel, False)
        for k, v in headers:
            request.requestHeaders.addRawHeader(k, v)
        request.gotLength(0)
        if body:
            request.content = StringIO(body)
        uri = '/' + '/'.join([quote(seg, safe) for seg in requestSegments])
        if query is not None:
            uri += '?' + '&'.join(['='.join([quote(k, safe), quote(v, safe)])
                                   for (k, v) in query])
        request.requestReceived(method, uri, 'HTTP/' + version)
        return request


    def render(self, *a, **kw):
        result = Deferred()
        def applicationFactory():
            def application(*args):
                environ, startResponse = args
                result.callback(args)
                startResponse('200 OK', [])
                return iter(())
            return application
        self.lowLevelRender(
            Request, applicationFactory, self.channelFactory, *a, **kw)
        return result


    def requestFactoryFactory(self, requestClass=Request):
        d = Deferred()
        def requestFactory(*a, **kw):
            request = requestClass(*a, **kw)
            # If notifyFinish is called after lowLevelRender returns, it won't
            # do the right thing, because the request will have already
            # finished.  One might argue that this is a bug in
            # Request.notifyFinish.
            request.notifyFinish().chainDeferred(d)
            return request
        return d, requestFactory


    def getContentFromResponse(self, response):
        return response.split('\r\n\r\n', 1)[1]



class EnvironTests(WSGITestsMixin, TestCase):
    """
    Tests for the values in the C{environ} C{dict} passed to the application
    object by L{twisted.web.wsgi.WSGIResource}.
    """
    def environKeyEqual(self, key, value):
        def assertEnvironKeyEqual((environ, startResponse)):
            self.assertEqual(environ[key], value)
        return assertEnvironKeyEqual


    def test_environIsDict(self):
        """
        L{WSGIResource} calls the application object with an C{environ}
        parameter which is exactly of type C{dict}.
        """
        d = self.render('GET', '1.1', [], [''])
        def cbRendered((environ, startResponse)):
            self.assertIdentical(type(environ), dict)
        d.addCallback(cbRendered)
        return d


    def test_requestMethod(self):
        """
        The C{'REQUEST_METHOD'} key of the C{environ} C{dict} passed to the
        application contains the HTTP method in the request (RFC 3875, section
        4.1.12).
        """
        get = self.render('GET', '1.1', [], [''])
        get.addCallback(self.environKeyEqual('REQUEST_METHOD', 'GET'))

        # Also make sure a different request method shows up as a different
        # value in the environ dict.
        post = self.render('POST', '1.1', [], [''])
        post.addCallback(self.environKeyEqual('REQUEST_METHOD', 'POST'))

        return gatherResults([get, post])


    def test_scriptName(self):
        """
        The C{'SCRIPT_NAME'} key of the C{environ} C{dict} passed to the
        application contains the I{abs_path} (RFC 2396, section 3) to this
        resource (RFC 3875, section 4.1.13).
        """
        root = self.render('GET', '1.1', [], [''])
        root.addCallback(self.environKeyEqual('SCRIPT_NAME', '/'))

        emptyChild = self.render('GET', '1.1', [''], [''])
        emptyChild.addCallback(self.environKeyEqual('SCRIPT_NAME', '/'))

        leaf = self.render('GET', '1.1', ['foo'], ['foo'])
        leaf.addCallback(self.environKeyEqual('SCRIPT_NAME', '/foo'))

        container = self.render('GET', '1.1', ['foo', ''], ['foo', ''])
        container.addCallback(self.environKeyEqual('SCRIPT_NAME', '/foo/'))

        internal = self.render('GET', '1.1', ['foo'], ['foo', 'bar'])
        internal.addCallback(self.environKeyEqual('SCRIPT_NAME', '/foo'))

        unencoded = self.render(
            'GET', '1.1', ['foo', '/', 'bar\xff'], ['foo', '/', 'bar\xff'])
        # The RFC says "(not URL-encoded)", even though that makes
        # interpretation of SCRIPT_NAME ambiguous.
        unencoded.addCallback(
            self.environKeyEqual('SCRIPT_NAME', '/foo///bar\xff'))

        return gatherResults([
                root, emptyChild, leaf, container, internal, unencoded])


    def test_pathInfo(self):
        """
        The C{'PATH_INFO'} key of the C{environ} C{dict} passed to the
        application contains the suffix of the request URI path which is not
        included in the value for the C{'SCRIPT_NAME'} key (RFC 3875, section
        4.1.5).
        """
        assertKeyEmpty = self.environKeyEqual('PATH_INFO', '')

        root = self.render('GET', '1.1', [], [''])
        root.addCallback(assertKeyEmpty)

        emptyChild = self.render('GET', '1.1', [''], [''])
        emptyChild.addCallback(assertKeyEmpty)

        leaf = self.render('GET', '1.1', ['foo'], ['foo'])
        leaf.addCallback(assertKeyEmpty)

        container = self.render('GET', '1.1', ['foo', ''], ['foo', ''])
        container.addCallback(assertKeyEmpty)

        internalLeaf = self.render('GET', '1.1', ['foo'], ['foo', 'bar'])
        internalLeaf.addCallback(self.environKeyEqual('PATH_INFO', '/bar'))

        internalContainer = self.render('GET', '1.1', ['foo'], ['foo', ''])
        internalContainer.addCallback(self.environKeyEqual('PATH_INFO', '/'))

        unencoded = self.render('GET', '1.1', [], ['foo', '/', 'bar\xff'])
        unencoded.addCallback(
            self.environKeyEqual('PATH_INFO', '/foo///bar\xff'))

        return gatherResults([
                root, leaf, container, internalLeaf,
                internalContainer, unencoded])


    def test_queryString(self):
        """
        The C{'QUERY_STRING'} key of the C{environ} C{dict} passed to the
        application contains the portion of the request URI after the first
        I{?} (RFC 3875, section 4.1.7).
        """
        missing = self.render('GET', '1.1', [], [''], None)
        missing.addCallback(self.environKeyEqual('QUERY_STRING', ''))

        empty = self.render('GET', '1.1', [], [''], [])
        empty.addCallback(self.environKeyEqual('QUERY_STRING', ''))

        present = self.render('GET', '1.1', [], [''], [('foo', 'bar')])
        present.addCallback(self.environKeyEqual('QUERY_STRING', 'foo=bar'))

        unencoded = self.render('GET', '1.1', [], [''], [('/', '/')])
        unencoded.addCallback(self.environKeyEqual('QUERY_STRING', '/=/'))

        # "?" is reserved in the <searchpart> portion of a URL.  However, it
        # seems to be a common mistake of clients to forget to quote it. 
        # So, make sure we handle that invalid case.
        doubleQuestion = self.render(
            'GET', '1.1', [], [''], [('foo', '?bar')], safe='?')
        doubleQuestion.addCallback(
            self.environKeyEqual('QUERY_STRING', 'foo=?bar'))

        return gatherResults([
            missing, empty, present, unencoded, doubleQuestion])


    def test_contentType(self):
        """
        The C{'CONTENT_TYPE'} key of the C{environ} C{dict} passed to the
        application contains the value of the I{Content-Type} request header
        (RFC 3875, section 4.1.3).
        """
        missing = self.render('GET', '1.1', [], [''])
        missing.addCallback(self.environKeyEqual('CONTENT_TYPE', ''))

        present = self.render(
            'GET', '1.1', [], [''], None, [('content-type', 'x-foo/bar')])
        present.addCallback(self.environKeyEqual('CONTENT_TYPE', 'x-foo/bar'))

        return gatherResults([missing, present])


    def test_contentLength(self):
        """
        The C{'CONTENT_LENGTH'} key of the C{environ} C{dict} passed to the
        application contains the value of the I{Content-Length} request header
        (RFC 3875, section 4.1.2).
        """
        missing = self.render('GET', '1.1', [], [''])
        missing.addCallback(self.environKeyEqual('CONTENT_LENGTH', ''))

        present = self.render(
            'GET', '1.1', [], [''], None, [('content-length', '1234')])
        present.addCallback(self.environKeyEqual('CONTENT_LENGTH', '1234'))

        return gatherResults([missing, present])


    def test_serverName(self):
        """
        The C{'SERVER_NAME'} key of the C{environ} C{dict} passed to the
        application contains the best determination of the server hostname
        possible, using either the value of the I{Host} header in the request
        or the address the server is listening on if that header is not
        present (RFC 3875, section 4.1.14).
        """
        missing = self.render('GET', '1.1', [], [''])
        # 10.0.0.1 value comes from a bit far away -
        # twisted.test.test_web.DummyChannel.transport.getHost().host
        missing.addCallback(self.environKeyEqual('SERVER_NAME', '10.0.0.1'))

        present = self.render(
            'GET', '1.1', [], [''], None, [('host', 'example.org')])
        present.addCallback(self.environKeyEqual('SERVER_NAME', 'example.org'))

        return gatherResults([missing, present])


    def test_serverPort(self):
        """
        The C{'SERVER_PORT'} key of the C{environ} C{dict} passed to the
        application contains the port number of the server which received the
        request (RFC 3875, section 4.1.15).
        """
        portNumber = 12354
        def makeChannel():
            channel = DummyChannel()
            channel.transport = DummyChannel.TCP()
            channel.transport.port = portNumber
            return channel
        self.channelFactory = makeChannel

        d = self.render('GET', '1.1', [], [''])
        d.addCallback(self.environKeyEqual('SERVER_PORT', str(portNumber)))
        return d


    def test_serverProtocol(self):
        """
        The C{'SERVER_PROTOCOL'} key of the C{environ} C{dict} passed to the
        application contains the HTTP version number received in the request
        (RFC 3875, section 4.1.16).
        """
        old = self.render('GET', '1.0', [], [''])
        old.addCallback(self.environKeyEqual('SERVER_PROTOCOL', 'HTTP/1.0'))

        new = self.render('GET', '1.1', [], [''])
        new.addCallback(self.environKeyEqual('SERVER_PROTOCOL', 'HTTP/1.1'))

        return gatherResults([old, new])


    def test_headers(self):
        """
        HTTP request headers are copied into the C{environ} C{dict} passed to
        the application with a C{HTTP_} prefix added to their names.
        """
        singleValue = self.render(
            'GET', '1.1', [], [''], None, [('foo', 'bar'), ('baz', 'quux')])
        def cbRendered((environ, startResponse)):
            self.assertEqual(environ['HTTP_FOO'], 'bar')
            self.assertEqual(environ['HTTP_BAZ'], 'quux')
        singleValue.addCallback(cbRendered)

        multiValue = self.render(
            'GET', '1.1', [], [''], None, [('foo', 'bar'), ('foo', 'baz')])
        multiValue.addCallback(self.environKeyEqual('HTTP_FOO', 'bar,baz'))

        withHyphen = self.render(
            'GET', '1.1', [], [''], None, [('foo-bar', 'baz')])
        withHyphen.addCallback(self.environKeyEqual('HTTP_FOO_BAR', 'baz'))

        multiLine = self.render(
            'GET', '1.1', [], [''], None, [('foo', 'bar\n\tbaz')])
        multiLine.addCallback(self.environKeyEqual('HTTP_FOO', 'bar \tbaz'))

        return gatherResults([singleValue, multiValue, withHyphen, multiLine])


    def test_wsgiVersion(self):
        """
        The C{'wsgi.version'} key of the C{environ} C{dict} passed to the
        application has the value C{(1, 0)} indicating that this is a WSGI 1.0
        container.
        """
        version = self.render('GET', '1.1', [], [''])
        version.addCallback(self.environKeyEqual('wsgi.version', (1, 0)))
        return version


    def test_wsgiRunOnce(self):
        """
        The C{'wsgi.run_once'} key of the C{environ} C{dict} passed to the
        application is set to C{False}.
        """
        once = self.render('GET', '1.1', [], [''])
        once.addCallback(self.environKeyEqual('wsgi.run_once', False))
        return once


    def test_wsgiMultithread(self):
        """
        The C{'wsgi.multithread'} key of the C{environ} C{dict} passed to the
        application is set to C{True}.
        """
        thread = self.render('GET', '1.1', [], [''])
        thread.addCallback(self.environKeyEqual('wsgi.multithread', True))
        return thread


    def test_wsgiMultiprocess(self):
        """
        The C{'wsgi.multiprocess'} key of the C{environ} C{dict} passed to the
        application is set to C{False}.
        """
        process = self.render('GET', '1.1', [], [''])
        process.addCallback(self.environKeyEqual('wsgi.multiprocess', False))
        return process


    def test_wsgiURLScheme(self):
        """
        The C{'wsgi.url_scheme'} key of the C{environ} C{dict} passed to the
        application has the request URL scheme.
        """
        # XXX Does this need to be different if the request is for an absolute
        # URL?
        def channelFactory():
            channel = DummyChannel()
            channel.transport = DummyChannel.SSL()
            return channel

        self.channelFactory = DummyChannel
        http = self.render('GET', '1.1', [], [''])
        http.addCallback(self.environKeyEqual('wsgi.url_scheme', 'http'))

        self.channelFactory = channelFactory
        https = self.render('GET', '1.1', [], [''])
        https.addCallback(self.environKeyEqual('wsgi.url_scheme', 'https'))

        return gatherResults([http, https])


    def test_wsgiErrors(self):
        """
        The C{'wsgi.errors'} key of the C{environ} C{dict} passed to the
        application is a file-like object (as defined in the U{Input and Errors
        Streams<http://www.python.org/dev/peps/pep-0333/#input-and-error-streams>}
        section of PEP 333) which converts bytes written to it into events for
        the logging system.
        """
        events = []
        addObserver(events.append)
        self.addCleanup(removeObserver, events.append)

        errors = self.render('GET', '1.1', [], [''])
        def cbErrors((environ, startApplication)):
            errors = environ['wsgi.errors']
            errors.write('some message\n')
            errors.writelines(['another\nmessage\n'])
            errors.flush()
            self.assertEqual(events[0]['message'], ('some message\n',))
            self.assertEqual(events[0]['system'], 'wsgi')
            self.assertTrue(events[0]['isError'])
            self.assertEqual(events[1]['message'], ('another\nmessage\n',))
            self.assertEqual(events[1]['system'], 'wsgi')
            self.assertTrue(events[1]['isError'])
            self.assertEqual(len(events), 2)
        errors.addCallback(cbErrors)
        return errors


    def test_wsgiInput(self):
        """
        The C{'wsgi.input'} key of the C{environ} C{dict} passed to the
        application is a file-like object (as defined in the U{Input and Errors
        Streams<http://www.python.org/dev/peps/pep-0333/#input-and-error-streams>}
        section of PEP 333) which makes the request body available to the
        application.
        """
        def appFactoryFactory(reader):
            result = Deferred()
            def applicationFactory():
                def application(*args):
                    environ, startResponse = args
                    result.callback(reader(environ['wsgi.input']))
                    startResponse('200 OK', [])
                    return iter(())
                return application
            return result, applicationFactory

        inputRead, appFactory = appFactoryFactory(
            lambda input: [input.read(1), input.read()])
        self.lowLevelRender(
            Request, appFactory, DummyChannel,
            'GET', '1.1', [], [''], None, [],
            "hello, world\n"
            "how are you\n")
        inputRead.addCallback(
            self.assertEqual, ['h', 'ello, world\nhow are you\n'])

        # COMPATIBILITY NOTE: the size argument is excluded from the WSGI
        # specification, but is provided here anyhow, because useful libraries
        # such as python stdlib's cgi.py assume their input file-like-object
        # supports readline with a size argument. If you use it, be aware your
        # application may not be portable to other conformant WSGI servers.
        inputReadline, appFactory = appFactoryFactory(
            lambda input: [input.readline(), input.readline(None),
                           input.readline(-1), input.readline(20),
                           input.readline(5), input.readline(5),
                           input.readline(5)])
        self.lowLevelRender(
            Request, appFactory, DummyChannel,
            'GET', '1.1', [], [''], None, [],
            "hello, world\n"
            "how are you\n"
            "I am great\n"
            "goodbye now\n"
            "no data here\n")
        inputReadline.addCallback(
            self.assertEqual, [
                'hello, world\n', 'how are you\n', 'I am great\n',
                'goodbye now\n', 'no da', 'ta he', 're\n'])


        inputReadlinesNoArg, appFactory = appFactoryFactory(
            lambda input: input.readlines())
        self.lowLevelRender(
            Request, appFactory, DummyChannel,
            'GET', '1.1', [], [''], None, [],
            "foo\n"
            "bar\n")
        inputReadlinesNoArg.addCallback(
            self.assertEqual, ["foo\n", "bar\n"])


        inputReadlinesNone, appFactory = appFactoryFactory(
            lambda input: input.readlines(None))
        self.lowLevelRender(
            Request, appFactory, DummyChannel,
            'GET', '1.1', [], [''], None, [],
            "foo\n"
            "bar\n")
        inputReadlinesNone.addCallback(
            self.assertEqual, ["foo\n", "bar\n"])


        inputReadlinesLength, appFactory = appFactoryFactory(
            lambda input: input.readlines(6))
        self.lowLevelRender(
            Request, appFactory, DummyChannel,
            'GET', '1.1', [], [''], None, [],
            "foo\n"
            "bar\n")
        inputReadlinesLength.addCallback(
            self.assertEqual, ["foo\n", "bar\n"])


        inputIter, appFactory = appFactoryFactory(
            lambda input: list(input))
        self.lowLevelRender(
            Request, appFactory, DummyChannel,
            'GET', '1.1', [], [''], None, [],
            'foo\n'
            'bar\n')
        inputIter.addCallback(
            self.assertEqual, ['foo\n', 'bar\n'])

        return gatherResults([
                inputRead, inputReadline, inputReadlinesNoArg,
                inputReadlinesNone, inputReadlinesLength,
                inputIter])



class StartResponseTests(WSGITestsMixin, TestCase):
    """
    Tests for the I{start_response} parameter passed to the application object
    by L{WSGIResource}.
    """
    def test_status(self):
        """
        The response status passed to the I{start_response} callable is written
        as the status of the response to the request.
        """
        channel = DummyChannel()

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('107 Strange message', [])
                return iter(())
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertTrue(
                channel.transport.written.getvalue().startswith(
                    'HTTP/1.1 107 Strange message'))
        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])

        return d


    def test_headers(self):
        """
        The headers passed to the I{start_response} callable are included in
        the headers response.
        """
        channel = DummyChannel()

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('200 OK', [('foo', 'bar'), ('baz', 'quux')])
                return iter(())
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            responseLines = channel.transport.written.getvalue().split('\r\n')
            self.assertIn('Foo: bar', responseLines)
            self.assertIn('Baz: quux', responseLines)
        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])
        return d


    def test_delayedUntilReturn(self):
        """
        Nothing is written in response to a request when the I{start_response}
        callable is invoked.  If the iterator returned by the application
        object produces only empty strings, the response is written after the
        last element is produced.
        """
        channel = DummyChannel()

        intermediateValues = []
        def record():
            intermediateValues.append(channel.transport.written.getvalue())

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('200 OK', [('foo', 'bar'), ('baz', 'quux')])
                yield ''
                record()
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertEqual(intermediateValues, [''])
        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])

        return d


    def test_delayedUntilContent(self):
        """
        Nothing is written in response to a request when the I{start_response}
        callable is invoked.  Once a non-empty string has been produced by the
        iterator returned by the application object, the response status and
        headers are written.
        """
        channel = DummyChannel()

        intermediateValues = []
        def record():
            intermediateValues.append(channel.transport.written.getvalue())

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('200 OK', [('foo', 'bar')])
                yield ''
                record()
                yield 'foo'
                record()
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertFalse(intermediateValues[0])
            self.assertTrue(intermediateValues[1])
        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])

        return d


    def test_content(self):
        """
        Content produced by the iterator returned by the application object is
        written to the request as it is produced.
        """
        channel = DummyChannel()

        intermediateValues = []
        def record():
            intermediateValues.append(channel.transport.written.getvalue())

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('200 OK', [('content-length', '6')])
                yield 'foo'
                record()
                yield 'bar'
                record()
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertEqual(
                self.getContentFromResponse(intermediateValues[0]),
                'foo')
            self.assertEqual(
                self.getContentFromResponse(intermediateValues[1]),
                'foobar')
        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])

        return d


    def test_multipleStartResponse(self):
        """
        If the I{start_response} callable is invoked multiple times before a
        data for the response body is produced, the values from the last call
        are used.
        """
        channel = DummyChannel()

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('100 Foo', [])
                startResponse('200 Bar', [])
                return iter(())
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertTrue(
                channel.transport.written.getvalue().startswith(
                    'HTTP/1.1 200 Bar\r\n'))
        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])

        return d


    def test_startResponseWithException(self):
        """
        If the I{start_response} callable is invoked with a third positional
        argument before the status and headers have been written to the
        response, the status and headers become the newly supplied values.
        """
        channel = DummyChannel()

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('100 Foo', [], (Exception, Exception("foo"), None))
                return iter(())
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertTrue(
                channel.transport.written.getvalue().startswith(
                    'HTTP/1.1 100 Foo\r\n'))
        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])

        return d


    def test_startResponseWithExceptionTooLate(self):
        """
        If the I{start_response} callable is invoked with a third positional
        argument after the status and headers have been written to the
        response, the supplied I{exc_info} values are re-raised to the
        application.
        """
        channel = DummyChannel()

        class SomeException(Exception):
            pass

        try:
            raise SomeException()
        except:
            excInfo = exc_info()

        reraised = []

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('200 OK', [])
                yield 'foo'
                try:
                    startResponse('500 ERR', [], excInfo)
                except:
                    reraised.append(exc_info())
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertTrue(
                channel.transport.written.getvalue().startswith(
                    'HTTP/1.1 200 OK\r\n'))
            self.assertEqual(reraised[0][0], excInfo[0])
            self.assertEqual(reraised[0][1], excInfo[1])
            self.assertEqual(reraised[0][2].tb_next, excInfo[2])

        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])

        return d


    def test_write(self):
        """
        I{start_response} returns the I{write} callable which can be used to
        write bytes to the response body without buffering.
        """
        channel = DummyChannel()

        intermediateValues = []
        def record():
            intermediateValues.append(channel.transport.written.getvalue())

        def applicationFactory():
            def application(environ, startResponse):
                write = startResponse('100 Foo', [('content-length', '6')])
                write('foo')
                record()
                write('bar')
                record()
                return iter(())
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertEqual(
                self.getContentFromResponse(intermediateValues[0]),
                'foo')
            self.assertEqual(
                self.getContentFromResponse(intermediateValues[1]),
                'foobar')
        d.addCallback(cbRendered)

        request = self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''], None, [])

        return d



class ApplicationTests(WSGITestsMixin, TestCase):
    """
    Tests for things which are done to the application object and the iterator
    it returns.
    """
    def enableThreads(self):
        self.reactor = reactor
        self.threadpool = ThreadPool()
        self.threadpool.start()
        self.addCleanup(self.threadpool.stop)


    def test_close(self):
        """
        If the application object returns an iterator which also has a I{close}
        method, that method is called after iteration is complete.
        """
        channel = DummyChannel()

        class Result:
            def __init__(self):
                self.open = True

            def __iter__(self):
                for i in range(3):
                    if self.open:
                        yield str(i)

            def close(self):
                self.open = False

        result = Result()
        def applicationFactory():
            def application(environ, startResponse):
                startResponse('200 OK', [('content-length', '3')])
                return result
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertEqual(
                self.getContentFromResponse(
                    channel.transport.written.getvalue()),
                '012')
            self.assertFalse(result.open)
        d.addCallback(cbRendered)

        self.lowLevelRender(
            requestFactory, applicationFactory,
            lambda: channel, 'GET', '1.1', [], [''])

        return d


    def test_applicationCalledInThread(self):
        """
        The application object is invoked and iterated in a thread which is not
        the reactor thread.
        """
        self.enableThreads()
        invoked = []

        def applicationFactory():
            def application(environ, startResponse):
                def result():
                    for i in range(3):
                        invoked.append(get_ident())
                        yield str(i)
                invoked.append(get_ident())
                startResponse('200 OK', [('content-length', '3')])
                return result()
            return application

        d, requestFactory = self.requestFactoryFactory()
        def cbRendered(ignored):
            self.assertNotIn(get_ident(), invoked)
            self.assertEqual(len(set(invoked)), 1)
        d.addCallback(cbRendered)

        self.lowLevelRender(
            requestFactory, applicationFactory,
            DummyChannel, 'GET', '1.1', [], [''])

        return d


    def test_writeCalledFromThread(self):
        """
        The I{write} callable returned by I{start_response} calls the request's
        C{write} method in the reactor thread.
        """
        self.enableThreads()
        invoked = []

        class ThreadVerifier(Request):
            def write(self, bytes):
                invoked.append(get_ident())
                return Request.write(self, bytes)

        def applicationFactory():
            def application(environ, startResponse):
                write = startResponse('200 OK', [])
                write('foo')
                return iter(())
            return application

        d, requestFactory = self.requestFactoryFactory(ThreadVerifier)
        def cbRendered(ignored):
            self.assertEqual(set(invoked), set([get_ident()]))
        d.addCallback(cbRendered)

        self.lowLevelRender(
            requestFactory, applicationFactory, DummyChannel,
            'GET', '1.1', [], [''])

        return d


    def test_iteratedValuesWrittenFromThread(self):
        """
        Strings produced by the iterator returned by the application object are
        written to the request in the reactor thread.
        """
        self.enableThreads()
        invoked = []

        class ThreadVerifier(Request):
            def write(self, bytes):
                invoked.append(get_ident())
                return Request.write(self, bytes)

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('200 OK', [])
                yield 'foo'
            return application

        d, requestFactory = self.requestFactoryFactory(ThreadVerifier)
        def cbRendered(ignored):
            self.assertEqual(set(invoked), set([get_ident()]))
        d.addCallback(cbRendered)

        self.lowLevelRender(
            requestFactory, applicationFactory, DummyChannel,
            'GET', '1.1', [], [''])

        return d


    def test_statusWrittenFromThread(self):
        """
        The response status is set on the request object in the reactor thread.
        """
        self.enableThreads()
        invoked = []

        class ThreadVerifier(Request):
            def setResponseCode(self, code, message):
                invoked.append(get_ident())
                return Request.setResponseCode(self, code, message)

        def applicationFactory():
            def application(environ, startResponse):
                startResponse('200 OK', [])
                return iter(())
            return application

        d, requestFactory = self.requestFactoryFactory(ThreadVerifier)
        def cbRendered(ignored):
            self.assertEqual(set(invoked), set([get_ident()]))
        d.addCallback(cbRendered)

        self.lowLevelRender(
            requestFactory, applicationFactory, DummyChannel,
            'GET', '1.1', [], [''])

        return d
