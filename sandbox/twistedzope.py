"""Run the Zope3 Publisher using Twisted's HTTP server."""

from cStringIO import StringIO

from Zope.Publisher.Publish import publish
from Zope.Publisher.HTTP.HTTPRequest import HTTPRequest
from Zope.Publisher.HTTP.HTTPResponse import HTTPResponse
from Zope.Publisher.HTTP.BrowserPayload import BrowserRequestPayload
from Zope.Publisher.HTTP.BrowserPayload import BrowserResponsePayload
from Zope.Publisher.DefaultPublication import DefaultPublication

from twisted.protocols import protocol
from twisted.web import server


rename_headers = {
    'CONTENT_LENGTH' : 'CONTENT_LENGTH',
    'CONTENT_TYPE'   : 'CONTENT_TYPE',
    'CONNECTION'     : 'CONNECTION_TYPE',
    }


class ZopeHTTPRequest(server.Request):
    
    # methods for HTTPResponse
    def setResponseStatus(self, status, reason):
        self.setResponseCode(status)
    
    def setResponseHeaders(self, d):
        for k, v in d.items():
            self.setHeader(k, v)
    
    # is this OK?
    appendResponseHeaders = setResponseHeaders
    
    
    
    def process(self):
        factory = self.factory
        env = self.create_environment()
        instream = StringIO(self.content)
        resp = HTTPResponse(factory.response_payload, self, self)
        req = HTTPRequest(factory.request_payload, resp, instream, env)
        publish(req)
        self.finish()
    
    def create_environment(self):
        path = self.path
        
        while path and path[0] == '/':
            path = path[1:]
        # already unquoted!
        # if '%' in path:
        #     path = unquote(path)

        env = {}
        env['REQUEST_METHOD'] = self.method.upper()
        env['SERVER_NAME'] = "localhost"
        env['SERVER_SOFTWARE'] = "Twisted + Zope"
        env['SERVER_PROTOCOL'] = "HTTP/1.0"
        env['SCRIPT_NAME']=''
        env['PATH_INFO']='/' + path
        x = self.uri.split('?', 2)
        if len(x) == 2:
            env['QUERY_STRING'] = x[1]
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'

        env_has = env.has_key
        
        for key, value in self.getAllHeaders().items():
            value = value.strip()
            key = key.upper().replace('-', '_') # do I need the replace?
            mykey = rename_headers.get(key, None)
            if mykey is None:
                mykey = 'HTTP_%s' % key
            if not env_has(mykey):
                env[mykey] = value
        return env


class HTTPFactory(protocol.ServerFactory):

    def buildProtocol(self, addr):
        """Generate a request attached to this site.
        """
        r = ZopeHTTPRequest()
        r.factory = self
        return r
    
    def __init__(self, publication):
        self.publication = publication
        self.request_payload = BrowserRequestPayload(publication)
        self.response_payload = BrowserResponsePayload()


if __name__ == '__main__':
    class tested_object:
        " "
        tries = 0
    
        def __call__(self, URL):
            return 'URL invoked: %s\n' % URL
        
        def redirect_method(self, RESPONSE):
            "Generates a redirect using the redirect() method."
            RESPONSE.redirect("http://somewhere.com/redirect")


    from twisted.internet import main, app
    application = app.Application("zope")
    application.listenTCP(8080, HTTPFactory(DefaultPublication(tested_object())))
    application.run(save=0)
