"""Run the Zope3 Publisher using Twisted's HTTP server."""

import string

from Zope.Publisher.Publish import publish
from Zope.Publisher.HTTP.HTTPRequest import HTTPRequest
from Zope.Publisher.HTTP.HTTPResponse import HTTPResponse

from twisted.protocols import protocol, http


rename_headers = {
    'CONTENT_LENGTH' : 'CONTENT_LENGTH',
    'CONTENT_TYPE'   : 'CONTENT_TYPE',
    'CONNECTION'     : 'CONNECTION_TYPE',
    }


class ZopeHTTPRequest(http.Request):
    
    # methods for HTTPResponse
    def setResponseStatus(self, status, reason):
        self.setResponseCode(status)
    
    def setResponseHeaders(self, d):
        for k, v in d.items():
            self.setHeader(k, v)
    
    def appendResponseHeaders(self, l):
        for i in l:
            k, v = string.split(i, ': ', 2)
            self.setHeader(k, v)
    
        
    def process(self):
        factory = self.channel.factory
        env = self.create_environment()
        self.content.seek(0, 0)
        req = HTTPRequest(self.content, self, env)
        req.setPublication(factory.publication)
        response = req.getResponse()
        response.setHeaderOutput(self)
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
        h = http.HTTPChannel()
        h.requestFactory = ZopeHTTPRequest
        h.factory = self
        return h
    
    def __init__(self, publication):
        self.publication = publication


if __name__ == '__main__':

    from Zope.Publisher.DefaultPublication import DefaultPublication
   
    class tested_object:
        """An example object to be published."""
        tries = 0
    
        def __call__(self, REQUEST):
            self.tries += 1
            result = ""
            result += "Number of times: %d\n" % self.tries
            for key in REQUEST.keys():
                result += "%r = %r\n" % (key, REQUEST.get(key))
            return result
        
        def redirect_method(self, RESPONSE):
            "Generates a redirect using the redirect() method."
            RESPONSE.redirect("http://somewhere.com/redirect")


    from twisted.internet import main, app
    application = app.Application("zope")
    application.listenTCP(8080, HTTPFactory(DefaultPublication(tested_object())))
    application.run(save=0)
