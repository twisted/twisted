"""
A non-blocking container resource for WSGI web applications.
"""

import os

from twisted.internet import defer
from twisted.python import log
from twisted.web2 import http
from twisted.web2 import iweb
from twisted.web2 import resource
from twisted.web2 import responsecode
from twisted.web2 import stream
from twisted.web2.twcgi import createCGIEnvironment


class AlreadyStartedResponse(Exception):
    pass


class WSGIResource(resource.LeafResource):
    def __init__(self, application):
        resource.Resource.__init__(self)
        self.application = application

    def render(self, ctx):
        from twisted.internet import reactor
        # Do stuff with WSGIHandler.
        handler = WSGIHandler(self.application, ctx)
        # Run it in a thread
        reactor.callInThread(handler.run)
        def _print(x):
            print x
            return x
        return handler.responseDeferred.addCallback(_print)


class WSGIHandler(object):
    headers_sent = False
    def __init__(self, application, ctx):
        request = iweb.IRequest(ctx)
        self.environment = createCGIEnvironment(ctx, request)
        self.application = application
        self.request = request
        self.response = None
        self.responseDeferred = defer.Deferred()


    def setupEnvironment(self):
        env = self.environment
        if env.get('HTTPS'):
            url_scheme = 'https'
        else:
            url_scheme = 'http'
        env['wsgi.version']      = (1, 0)
        env['wsgi.url_scheme']   = url_scheme
        env['wsgi.input']        = 0  # IMPLEMENT ME
        env['wsgi.errors']       = 0  # IMPLEMENT ME
        env['wsgi.multithread']  = True
        env['wsgi.multiprocess'] = True
        env['wsgi.run_once']     = False
        

    def startWSGIResponse(self, status, response_headers, exc_info=None):
        if exc_info is not None:
            try:
                if self.headers_sent:
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                exc_info = None
        elif self.response is not None:
            raise AlreadyStartedResponse, 'startWSGIResponse(%r)' % status
        self.response = http.Response(status, stream=stream.ProducerStream())
        for key, value in response_headers:
            self.response.headers.addRawHeader(key, value)
        return self.write


    def run(self):
        print ".run"
        try:
            self.setupEnvironment()
            result = self.application(self.environment, self.startWSGIResponse)
            self.handleResult(result)
        except:
            log.err()
            pass


    def write(self, output):
        print ".write(%r)"%output
        from twisted.internet import reactor
        if not self.headers_sent:
            self.headers_sent = True
            reactor.callFromThread(self.responseDeferred.callback, self.response)
        reactor.callFromThread(self.response.stream.write, output)


    def handleResult(self, result):
        from twisted.internet import reactor
        for data in result:
            self.write(data)
        reactor.callFromThread(self.response.stream.finish)
        
