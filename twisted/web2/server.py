# -*- test-case-name: twisted.web.test.test_web -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""This is a web-sever which integrates with the twisted.internet
infrastructure.
"""

# System Imports
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import operator, cgi, time, urlparse
from urllib import quote
try:
    from twisted.protocols._c_urlarg import unquote
except ImportError:
    from urllib import unquote

from zope.interface import implements
# Twisted Imports
from twisted.internet import reactor, defer
from twisted.python import log, components, failure
from twisted import copyright

# Sibling Imports
from twisted.web2 import resource, http, iweb, responsecode
from twisted.web2 import http_headers, context, error

from twisted.web2 import version as web2_version


_errorMarker = object()

def defaultHeadersFilter(request, response):
    if not response.headers.hasHeader('server'):
        response.headers.setHeader('server', web2_version)
    if not response.headers.hasHeader('date'):
        response.headers.setHeader('date', time.time())
    return response

import rangefilter

class Request(http.Request):
    implements(iweb.IRequest)
    
    site = None
    _initialprepath = None
    responseFilters = [rangefilter.rangefilter, defaultHeadersFilter]
    
    def __init__(self, *args, **kw):
        self.notifications = []
        if kw.has_key('site'):
            self.site = kw['site']
            del kw['site']
        if kw.has_key('prepathuri'):
            self._initialprepath = kw['prepathuri']
            del kw['prepathuri']
        
        http.Request.__init__(self, *args, **kw)
        
    def parseURL(self):
        (self.scheme, self.host, self.path,
         self.params, argstring, fragment) = urlparse.urlparse(self.uri)
        
        self.args = cgi.parse_qs(argstring, True)

        path = map(unquote, self.path[1:].split('/'))
        if self._initialprepath:
            # We were given an initial prepath -- this is for supporting
            # CGI-ish applications where part of the path has already
            # been processed
            prepath = map(unquote, self._initialprepath[1:].split('/'))
            
            if self.postpath[:len(prepath)] == prepath:
                self.prepath = prepath
                self.postpath = path[len(prepath):]
            else:
                self.prepath = []
                self.postpath = path
        else:
            self.prepath = []
            self.postpath = path
        self.sitepath = self.prepath[:]
        

    def getHost(self):
        if self.host:
            return self.host
        host = self.headers.getHeader('host')
        if not host:
            if self.clientproto >= (1,1):
                raise error.Error(responsecode.BAD_REQUEST)
            host = self.chanRequest.channel.transport.getHost().host
        return host

    def process(self):
        "Process a request."
        # get site from channel
        if not self.site:
            self.site = self.chanRequest.channel.site

        requestContext = context.RequestContext(tag=self)
        
        try:
            self.checkExpect()
            #self.defaultHeaders()
            #response.headers.setHeader('content-type', http_headers.MimeType('text','html', charset='UTF-8'))
            self.parseURL()
            self.host = self.getHost()
        except error.Error:
            self._processingFailed(requestContext)
            return
        
        # make content string.
        # FIXME: make resource interface for choosing how to
        # handle content.
        self.content = StringIO.StringIO()

        self.deferredContext = self._getChild(requestContext,
                                              self.site.getRootResource(),
                                              self.postpath)
        self.deferredContext.addErrback(self._processingFailed, requestContext)
        
    def handleContentChunk(self, data):
        # FIXME: this sucks.
        self.content.write(data)
    
    def handleContentComplete(self):
        # This sets up a seperate deferred chain because we don't want the
        # errbacks for rendering to be called for errors from before.
        self.deferredContext.addCallback(self._renderAndFinish)
        
    def _getChild(self, ctx, res, path):
        """Create a PageContext for res, call res.locateChild, and pass the
        result on to _handleSegment."""
        
        # Create a context object to represent this new resource
        newctx = context.PageContext(tag=res, parent=ctx)
        newctx.remember(tuple(self.prepath), iweb.ICurrentSegments)
        newctx.remember(tuple(self.postpath), iweb.IRemainingSegments)

        if not path:
            return newctx

        return defer.maybeDeferred(
            res.locateChild, newctx, path
        ).addErrback(
            self._processingFailed, newctx
        ).addCallback(
            self._handleSegment, path, newctx
        )
        
    def _handleSegment(self, result, path, pageContext):
        """Handle the result of a locateChild call done in _getChild."""
        
        if result is _errorMarker:
            # The error page handler has already handled this, abort.
            return result
        
        newres, newpath = result
        # If the child resource is None then display a error page
        if newres is None:
            return self._processingFailed(error.Error(code=responsecode.NOT_FOUND), pageContext)

        # If we got a deferred then we need to call back later, once the
        # child is actually available.
        if isinstance(newres, defer.Deferred):
            return newres.addCallback(
                lambda actualRes: self._handleSegment(
                    (actualRes, newpath), path, pageContext))

        newres = iweb.IResource(newres, persist=True)
        if newres is pageContext.tag:
            assert not newpath is path, "URL traversal cycle detected when attempting to locateChild %r from resource %r." % (path, res)
            assert  len(newpath) < len(path), "Infinite loop impending..."

        ## We found a Resource... update the request.prepath and postpath
        for x in xrange(len(path) - len(newpath)):
            self.prepath.append(self.postpath.pop(0))

        return self._getChild(pageContext, newres, newpath)


    def _renderAndFinish(self, pageContext):
        if pageContext is _errorMarker:
            # If the location step raised an exception, the error
            # handler has already rendered the error page.
            return pageContext
        
        d = defer.maybeDeferred(pageContext.tag.renderHTTP, pageContext)
        d.addCallback(self._cbFinishRender, pageContext)
        d.addErrback(self._processingFailed, pageContext)
        
    def _processingFailed(self, reason, ctx):
        # Give a ICanHandleException implementer a chance to render the page.
        
        def _processingFailed_inner(ctx, reason):
            handler = iweb.ICanHandleException(ctx)
            return handler.renderHTTP_exception(ctx, reason)
        
        d = defer.maybeDeferred(_processingFailed_inner, ctx, reason)
        d.addCallback(self._cbFinishRender, ctx)
        d.addErrback(self._processingReallyFailed, ctx, reason)
        d.addBoth(lambda result: _errorMarker)
        return d
    
    def _processingReallyFailed(self, reason, ctx, origReason):
        log.msg("Exception rendering error page:", isErr=1)
        log.err(reason)
        log.msg("Original exception:", isErr=1)
        log.err(origReason)
        
        body = ("<html><head><title>Internal Server Error</title></head>"
                "<body><h1>Internal Server Error</h1>An error occurred rendering the requested page. Additionally, an error occured rendering the error page.</body></html>")
        
        response = http.Response()
        response.code = responsecode.INTERNAL_SERVER_ERROR
        response.headers.setHeader('content-type', http_headers.MimeType('text','html'))
        response.headers.setHeader('content-length', len(body))
        response.stream = stream.MemoryStream(body)
        return response

    def _cbFinishRender(self, result, ctx):
        resource = iweb.IResource(result, None)
        if resource:
            pageContext = context.PageContext(tag=resource, parent=ctx)
            d = defer.maybeDeferred(resource.renderHTTP, pageContext)
            d.addCallback(self._cbFinishRender, pageContext)
            return d
        else:
            response = iweb.IResponse(result)
            if response:
                d = defer.succeed(response)
                for f in self.responseFilters:
                    d.addCallback(lambda response: f(self, response))
                d.addCallback(self.writeResponse)
            else:
                raise TypeError("html is not a resource or a response")
        return
    
    def notifyFinish(self):
        """Notify when finishing the request

        @return: A deferred. The deferred will be triggered when the
        request is finished -- with a C{None} value if the request
        finishes successfully or with an error if the request is stopped
        by the client.
        """
        self.notifications.append(defer.Deferred())
        return self.notifications[-1]

    def connectionLost(self, reason):
        for d in self.notifications:
            d.errback(reason)
        self.notifications = []

    def finish(self):
        http.Request.finish(self)
        for d in self.notifications:
            d.callback(None)
        self.notifications = []

class Site(http.HTTPFactory):

    counter = 0
    requestFactory = Request
    version = "TwistedWeb/%s" % copyright.version
    
    def __init__(self, resource, timeout=60*60*12):
        """Initialize.
        """
        http.HTTPFactory.__init__(self, timeout=timeout)
        self.sessions = {}
        self.resource = resource

    def __getstate__(self):
        d = self.__dict__.copy()
        d['sessions'] = {}
        return d

    def mkuid(self):
        """Generate an opaque, unique ID for a user's session."""
        import md5, random
        self.counter = self.counter + 1
        digest = md5.new("%s_%s" % (random.random() , self.counter))
        return digest.hexdigest()

    def setSession(self, session):
        """Generate a new Session instance, and store it for future reference.
        """
        self.sessions[uid] = session

    def getSession(self, uid):
        """Get a previously generated session, by its unique ID.
        This raises a KeyError if the session is not found.
        """
        return self.sessions[uid]

    def buildProtocol(self, addr):
        """Generate a channel attached to this site.
        """
        channel = http.HTTPFactory.buildProtocol(self, addr)
        channel.site = self
        return channel

    def getRootResource(self):
        return self.resource
    
