"""Run the Zope3 Publisher using Twisted's HTTP server."""

import string

from Zope.Publisher.Publish import publish
from Zope.Publisher.Browser.BrowserRequest import BrowserRequest

from twisted.protocols import http
from twisted.internet import reactor, protocol
from twisted.python import log


rename_headers = {
    'CONTENT_LENGTH' : 'CONTENT_LENGTH',
    'CONTENT_TYPE'   : 'CONTENT_TYPE',
    'CONNECTION'     : 'CONNECTION_TYPE',
    }


class ZopeHTTPRequest(log.Logger, http.Request):
    
    def write(self, data):
        reactor.callFromThread(http.Request.write, self, data)
    
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
        """Process a request.

        Doesn't do the actual processing, instead runs self._process in
        the thread pool.
        """
        reactor.callInThread(self._process)
    
    def _process(self):
        """Do the real processing of a request.

        Runs in a thread pool.
        """
        env = self.create_environment()
        self.content.seek(0, 0)
        req = BrowserRequest(self.content, self, env)
        req.setPublication(self.channel.publication)
        response = req._createResponse(self)
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


class HTTPFactory(http.HTTPFactory):

    def buildProtocol(self, addr):
        """Generate a request attached to this site.
        """
        h = http.HTTPChannel()
        h.requestFactory = ZopeHTTPRequest
        h.factory = self
        h.publication = self.publication
        return h
    
    def __init__(self, publication):
        http.HTTPFactory.__init__(self)
        self.publication = publication
    

if __name__ == '__main__':

    from Zope.App.ZopePublication.Browser.Publication import BrowserPublication
    from ZODB.FileStorage import FileStorage
    from ZODB.DB import DB
    from Zope.App import config

    config("site.zcml")
    db = DB(FileStorage("Data.fs"))
    pub = BrowserPublication(db)
    
    reactor.listenTCP(8080, HTTPFactory(pub))
    reactor.run()
