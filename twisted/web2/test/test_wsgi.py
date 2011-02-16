# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import time
from twisted.web2.test.test_server import BaseCase
from twisted.internet import reactor, interfaces, defer
from twisted.python import log

if interfaces.IReactorThreads(reactor, None) is not None:
    from twisted.web2.wsgi import WSGIResource as WSGI
else:
    WSGI = None


class TestError(Exception):
    pass


class TestContainer(BaseCase):
    """
    Tests various applications with the WSGI container.
    """

    def flushErrors(self, result, error):
        """
        Flush the specified C{error] and forward C{result}.
        """
        self.flushLoggedErrors(error)
        return result

    def test_getContainedResource(self):
        """
        Test that non-blocking WSGI applications render properly.
        """
        def application(environ, start_response):
            status = '200 OK'
            response_headers = [('Content-type','text/html')]
            writer = start_response(status, response_headers)
            writer('<html>')
            return ['<h1>Some HTML</h1>',
                    '</html>']

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (200, {"Content-Length": None}, '<html><h1>Some HTML</h1></html>'))

    def test_getBlockingResource(self):
        """
        Test that blocking WSGI applications render properly.
        """
        def application(environ, start_response):
            """
            Simplest possible application object.
            """
            status = '200 OK'
            response_headers = [('Content-type','text/html')]
            writer = start_response(status, response_headers)
            writer('<h1>A little bit')
            time.sleep(1)
            writer(' of HTML</h1>')
            time.sleep(1)
            return ['<p>Hello!</p>']

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (200, {"Content-Length": None},
            '<h1>A little bit of HTML</h1><p>Hello!</p>'))

    def test_responseCode(self):
        """
        Test that WSGIResource handles strange response codes properly.
        """
        def application(environ, start_response):
            status = '314'
            response_headers = [('Content-type','text/html')]
            writer = start_response(status, response_headers)
            return []

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (314, {"Content-Length": 0}, ''))

    def test_errorfulResource(self):
        def application(environ, start_response):
            raise TestError("This is an expected error")

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (500, {}, None)).addBoth(self.flushErrors, TestError)

    def test_errorfulResource2(self):
        def application(environ, start_response):
            write = start_response("200 OK", {})
            write("Foo")
            raise TestError("This is an expected error")

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (200, {"Content-Length": None}, "Foo"), failure=True
            ).addBoth(self.flushErrors, TestError)

    def test_errorfulIterator(self):
        def iterator():
            raise TestError("This is an expected error")

        def application(environ, start_response):
            start_response("200 OK", {})
            return iterator()

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (500, {}, None)).addBoth(self.flushErrors, TestError)

    def test_errorfulIterator2(self):
        def iterator():
            yield "Foo"
            yield "Bar"
            raise TestError("This is also expected")

        def application(environ, start_response):
            start_response("200 OK", {})
            return iterator()

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (200, {"Content-Length": None}, "FooBar"), failure=True
            ).addBoth(self.flushErrors, TestError)

    def test_didntCallStartResponse(self):
        def application(environ, start_response):
            return ["Foo"]

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (500, {}, None)).addBoth(self.flushErrors, RuntimeError)

    def test_calledStartResponseLate(self):
        def application(environ, start_response):
            start_response("200 OK", {})
            yield "Foo"

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (200, {"Content-Length": None}, "Foo"))

    def test_returnList(self):
        def application(environ, start_response):
            write = start_response("200 OK", {})
            return ["Foo", "Bar"]

        return self.assertResponse(
            (WSGI(application), 'http://host/'),
            (200, {"Content-Length": 6}, "FooBar"))

    def test_readAllInput(self):
        def application(environ, start_response):
            input = environ['wsgi.input']
            out = input.read(-1)
            start_response("200 OK", {})
            return [out]

        return self.assertResponse(
            (WSGI(application), 'http://host/', {}, None, None, '',
            "This is some content"),
            (200, {"Content-Length": 20}, "This is some content"))

    def test_readInputLines(self):
        def application(environ, start_response):
            input = environ['wsgi.input']
            out = 'X'.join(input.readlines())
            start_response("200 OK", {})
            return [out]

        d = self.assertResponse(
            (WSGI(application), 'http://host/', {}, None, None, '', "a\nb\nc"),
            (200, {"Content-Length": 7}, "a\nXb\nXc"))

        d.addCallback(lambda d: self.assertResponse(
            (WSGI(application), 'http://host/', {}, None, None, '', "a\nb\n"),
            (200, {"Content-Length": 5}, "a\nXb\n")))
        return d

    def test_readInputLineSizeNegZero(self):
        """
        Test that calling wsgi.input.readline works with -1 and 0 and none.
        """
        def application(environ, start_response):
            input = environ['wsgi.input']

            out = [input.read(5)] # 'Line '
            out.extend(["X", input.readline(-1)]) # 'blah blah\n'
            out.extend(["X", input.readline(0)])  # ''
            out.extend(["X", input.readline(None)]) # 'Oh Line\n'
            out.extend(["X", input.readline()])   # ''

            start_response("200 OK", {})
            return out

        return self.assertResponse(
            (WSGI(application), 'http://host/', {}, None, None, '',
             "Line blah blah\nOh Line\n"),
            (200, {"Content-Length": 27},
             "Line Xblah blah\nXXOh Line\nX"))

    def test_readInputLineSize(self):
        """
        Test that readline() with a size works.
        """
        def application(environ, start_response):
            input = environ['wsgi.input']

            out = [input.read(5)]           # 'Line '
            out.extend(["X", input.readline(5)]) # 'blah '
            out.extend(["X", input.readline()])  # 'blah\n'
            out.extend(["X", input.readline(1)])     # 'O'
            out.extend(["X", input.readline()])  # 'h Line\n'

            start_response("200 OK", {})
            return out

        return self.assertResponse(
            (WSGI(application), 'http://host/', {}, None, None, '',
             "Line blah blah\nOh Line\n"),
            (200, {"Content-Length": 27},
             "Line Xblah Xblah\nXOXh Line\n"))

    def test_readInputMixed(self):
        def application(environ, start_response):
            input = environ['wsgi.input']
            out = [input.read(5)]
            out.extend(["X", input.readline()])
            out.extend(["X", input.read(1)])
            out.extend(["X", input.readline()])

            start_response("200 OK", {})
            return out

        return self.assertResponse(
            (WSGI(application), 'http://host/', {}, None, None, '',
             "Line blah blah\nOh Line\n"),
            (200, {"Content-Length": 26}, "Line Xblah blah\nXOXh Line\n"))

    def test_readiter(self):
        """
        Test that using wsgi.input as an iterator works.
        """
        def application(environ, start_response):
            input = environ['wsgi.input']
            out = 'X'.join(input)

            start_response("200 OK", {})
            return [out]

        return self.assertResponse(
            (WSGI(application), 'http://host/', {}, None, None, '',
             "Line blah blah\nOh Line\n"),
            (200, {"Content-Length": 24}, "Line blah blah\nXOh Line\n"))


class TestWSGIEnvironment(BaseCase):
    """
    Test that the WSGI container does everything we expect it to do
    with the WSGI environment dictionary.
    """
    def envApp(self, *varnames):
        """
        Return a WSGI application that writes environment variables.
        """
        def _app(environ, start_response):
            status = '200'
            response_headers = [('Content-type','text/html')]
            writer = start_response(status, response_headers)
            return ['%s=%r;' % (k, environ.get(k, '')) for k in varnames]
        return _app

    def assertEnv(self, uri, env, version=None, prepath=''):
        """
        Check the value of the rendering envirnment against
        the string returned by the testing WSGIApp.
        """
        keys = env.keys()
        keys.sort()
        envstring = ''.join(['%s=%r;' % (k, v) for k, v in env.items()])
        return self.assertResponse(
            (WSGI(self.envApp(*keys)), uri, None, None, version, prepath),
            (200, {}, envstring))

    def test_wsgi_url_scheme(self):
        """
        Check the value of C{wsgi.url_scheme} variable for the http and the
        https cases.
        """
        return defer.gatherResults([
            self.assertEnv('https://host/', {'wsgi.url_scheme': 'https'}),
            self.assertEnv('http://host/', {'wsgi.url_scheme': 'http'})
        ])

    def test_SERVER_PROTOCOL(self):
        """
        Check the value the C{SERVER_PROTOCOL} variable in the WSGI environment.
        """
        return self.assertEnv('http://host/', {'SERVER_PROTOCOL': 'HTTP/1.1'})

    def test_SERVER_PORT(self):
        """
        Check the value of the C{SERVER_PORT} variable in the WSGI environment,
        for different kind of URLs.
        """
        return defer.gatherResults([
            self.assertEnv('http://host/', {'SERVER_PORT': '80'}),
            self.assertEnv('http://host:523/', {'SERVER_PORT': '523'}),
            self.assertEnv('https://host/', {'SERVER_PORT': '443'}),
            self.assertEnv('https://host:523/', {'SERVER_PORT': '523'}),
            self.assertEnv('/foo', {'SERVER_PORT': '80'}, version=(1,0))
        ])

    def test_SCRIPT_NAME(self):
        """
        Check the value of C{SCRIPT_NAME}, depending of the prepath field.
        """
        return defer.gatherResults([
            self.assertEnv('http://host/', {'SCRIPT_NAME': ''}),
            self.assertEnv('http://host/myscript/foobar',
                {'SCRIPT_NAME': '/myscript', 'PATH_INFO': '/foobar'}, prepath='/myscript'),
            self.assertEnv('http://host/myscript/foobar/',
                {'SCRIPT_NAME': '/myscript/foobar', 'PATH_INFO': '/'}, prepath='/myscript/foobar'),
            self.assertEnv('http://host/myscript/foobar?bar=baz',
                {'SCRIPT_NAME': '/myscript', 'PATH_INFO': '/foobar'}, prepath='/myscript')
        ])


if WSGI is None:
    for cls in (TestContainer, TestWSGIEnvironment):
        setattr(cls, 'skip', 'Required thread support is missing, skipping')

