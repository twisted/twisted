import time
from twisted.web2.test.test_server import BaseCase
from twisted.web2 import resource, wsgi
from twisted.trial import util

WSGI = wsgi.WSGIResource

class TestContainer(BaseCase):
    wait_timeout = 10.0

    def test_getContainedResource(self):
        """Test that non-blocking WSGI applications render properly.
        """
        def application(environ, start_response):
            status = '200 OK'
            response_headers = [('Content-type','text/html')]
            writer = start_response(status, response_headers)
            writer('<html>')
            return ['<h1>Some HTML</h1>',
                    '</html>']

        self.assertResponse(
            (WSGI(application), 'http://host/'),
            (200, {}, '<html><h1>Some HTML</h1></html>'))

    def test_getBlockingResource(self):
        """Test that blocking WSGI applications render properly.
        """
        def application(environ, start_response):
            """Simplest possible application object"""
            status = '200 OK'
            response_headers = [('Content-type','text/html')]
            writer = start_response(status, response_headers)
            writer('<h1>A little bit')
            time.sleep(1)
            writer(' of HTML</h1>')
            time.sleep(1)
            return ['<p>Hello!</p>']

        self.assertResponse(
            (WSGI(application), 'http://host/'),
            (200, {}, '<h1>A little bit of HTML</h1><p>Hello!</p>'))

    def test_responseCode(self):
        """
        Test that WSGIResource handles strange response codes properly.
        """
        def application(environ, start_response):
            status = '314'
            response_headers = [('Content-type','text/html')]
            writer = start_response(status, response_headers)
            return []

        self.assertResponse(
            (WSGI(application), 'http://host/'),
            (314, {}, ''))

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

    def assertEnv(self, uri, env):
        keys = env.keys()
        keys.sort()
        envstring = ''.join(['%s=%r;' % (k, v) for k, v in env.items()])
        self.assertResponse(
            (WSGI(self.envApp(*keys)), uri),
            (200, {}, envstring))

    def test_url_scheme(self):
        """wsgi.url_scheme"""
        self.assertEnv('https://host/', {'wsgi.url_scheme': 'https'})
        self.assertEnv('http://host/', {'wsgi.url_scheme': 'http'})

    def test_server_protocol(self):
        """SERVER_PROTOCOL"""
        self.assertEnv('http://host/', {'SERVER_PROTOCOL': 'HTTP/1.1'})

    def test_server_port(self):
        """SERVER_PORT"""
        self.assertEnv('http://host/', {'SERVER_PORT': ''})
        self.assertEnv('http://host:523/', {'SERVER_PORT': '523'})
        self.assertEnv('https://host/', {'SERVER_PORT': ''})
        self.assertEnv('https://host:523/', {'SERVER_PORT': '523'})

        
    
