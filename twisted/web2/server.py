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
from twisted.web2 import http, iweb
from twisted.web2.responsecode import *
from twisted.web2 import http_headers, context, error, stream

from twisted.web2 import version as web2_version
from twisted import __version__ as twisted_version

VERSION = "Twisted/%s TwistedWeb/%s" % (twisted_version, web2_version)
_errorMarker = object()

def defaultHeadersFilter(request, response):
    if not response.headers.hasHeader('server'):
        response.headers.setHeader('server', VERSION)
    if not response.headers.hasHeader('date'):
        response.headers.setHeader('date', time.time())
    return response
defaultHeadersFilter.handleErrors = True

def preconditionfilter(request, response):
    newresponse = http.checkPreconditions(request, response)
    if newresponse is not None:
        return newresponse
    return response

ERROR_MESSAGES = {
    # 300
    # no MULTIPLE_CHOICES
    MOVED_PERMANENTLY: 'The document has permanently moved <a href="%(location)s">here</a>.',
    FOUND: 'The document has temporarily moved <a href="%(location)s">here</a>.',
    SEE_OTHER: 'The results are available <a href="%(location)s">here</a>.',
    # no NOT_MODIFIED
    USE_PROXY: "Access to this resource must be through the proxy %(location)s.",
    # 306 unused
    TEMPORARY_REDIRECT: 'The document has temporarily moved <a href="%(location)s">here</a>.',

    # 400
    BAD_REQUEST: "Your browser sent an invalid request.",
    UNAUTHORIZED: "You are not authorized to view the resource at %(uri)s. Perhaps you entered a wrong password, or perhaps your browser doesn't support authentication.",
    PAYMENT_REQUIRED: "Payment Required (useful result code, this...).",
    FORBIDDEN: "You don't have permission to access %(uri)s.",
    NOT_FOUND: "The resource %(uri)s cannot be found.",
    NOT_ALLOWED: "The requested method %(method)s is not supported by %(uri)s.",
    NOT_ACCEPTABLE: "No representation of %(uri)s that is acceptable to your client could be found.",
    PROXY_AUTH_REQUIRED: "You are not authorized to view the resource at %(uri)s. Perhaps you entered a wrong password, or perhaps your browser doesn't support authentication.",
    REQUEST_TIMEOUT: "Server timed out waiting for your client to finish sending the HTTP request.",
    CONFLICT: "Conflict (?)",
    GONE: "The resource %(uri)s has been permanently removed.",
    LENGTH_REQUIRED: "The resource %(uri)s requires a Content-Length header.",
    PRECONDITION_FAILED: "A precondition evaluated to false.",
    REQUEST_ENTITY_TOO_LARGE: "The provided request entity data is too longer than the maximum for the method %(method)s at %(uri)s.",
    REQUEST_URI_TOO_LONG: "The request URL is longer than the maximum on this server.",
    UNSUPPORTED_MEDIA_TYPE: "The provided request data has a format not understood by the resource at %(uri)s.",
    REQUESTED_RANGE_NOT_SATISFIABLE: "None of the ranges given in the Range request header are satisfiable by the resource %(uri)s.",
    EXPECTATION_FAILED: "The server does support one of the expectations given in the Expect header.",

    # 500
    INTERNAL_SERVER_ERROR: "An internal error occurred trying to process your request. Sorry.",
    NOT_IMPLEMENTED: "Some functionality requested is not implemented on this server.",
    BAD_GATEWAY: "An upstream server returned an invalid response.",
    SERVICE_UNAVAILABLE: "This server cannot service your request becaues it is overloaded.",
    GATEWAY_TIMEOUT: "An upstream server is not responding.",
    HTTP_VERSION_NOT_SUPPORTED: "HTTP Version not supported.",
    INSUFFICIENT_STORAGE_SPACE: "There is insufficient storage space available to perform that request.",
    NOT_EXTENDED: "This server does not support the a mandatory extension requested."
}

# Is there a good place to keep this function?
def _escape(original):
    if original is None:
        return None
    return original.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

def defaultErrorHandler(request, response):
    if response.stream is not None:
        # Already got an error message
        return response
    if response.code < 300:
        # We only do error messages
        return response

    
    message = ERROR_MESSAGES.get(response.code, None)
    if message is None:
        # No message specified for that code
        return response
    
    message = message % {
        'uri':_escape(request.uri),
        'location':_escape(response.headers.getHeader('location')),
        'method':_escape(request.method)
        }

    title = RESPONSES.get(response.code, "")
    body = ("<html><head><title>%d %s</title></head>"
            "<body><h1>%s</h1>%s</body></html>") % (
        response.code, title, title, message)
    response.stream = stream.MemoryStream(body)
    return response
defaultErrorHandler.handleErrors = True

import rangefilter

def doTrace(request):
    request = iweb.IRequest(request)
    response = http.Response(OK)
    response.headers.setHeader('content-type', http_headers.MimeType('message', 'http'))
    txt = "%s %s HTTP/%d.%d\r\n" % (request.method, request.uri,
                                    request.clientproto[0], request.clientproto[1])

    l=[]
    for name, valuelist in request.headers.getAllRawHeaders():
        for value in valuelist:
            l.append("%s: %s\r\n" % (name, value))
    txt += ''.join(l)

    import stream
    response.stream = stream.MemoryStream(txt)
    return response

def getEntireStream(stream):
    data = StringIO.StringIO()
    
    def _getData():
        return defer.maybeDeferred(stream.read).addCallback(_gotData)

    def _gotData(result):
        if result is None:
            data.reset()
            return data
        else:
            data.write(result)
            return _getData()
        
    return _getData()
    
def parsePOSTData(request):
    def _gotURLEncodedData(data):
        #print "_gotURLEncodedData"
        request.args.update(cgi.parse_qs(data.read(), 1))
        
    def _gotMultipartData(data):
        #print "_gotMultipartData"
        try:
            data.reset()
            d=cgi.parse_multipart(data, dict(ctype.params))
            data.reset()
            #print "_gotMultipartData:",d, dict(ctype.params), data.read()
            request.args.update(d)
        except KeyError, e:
            if e.args[0] == 'content-disposition':
                # Parse_multipart can't cope with missing
                # content-dispostion headers in multipart/form-data
                # parts, so we catch the exception and tell the client
                # it was a bad request.
                raise HTTPError(responsecode.BAD_REQUEST)
            raise

    if request.stream.length == 0:
        return defer.succeed(None)
    
    parser = None
    ctype = request.headers.getHeader('content-type')
    if ctype is None:
        return defer.succeed(None)
    
    if ctype.mediaType == 'application' and ctype.mediaSubtype == 'x-www-form-urlencoded':
        parser = _gotURLEncodedData
    elif ctype.mediaType == 'multipart' and ctype.mediaSubtype == 'form-data':
        parser = _gotMultipartData
        
    if parser:
        return getEntireStream(request.stream).addCallback(parser)
    return defer.succeed(None)

class StopTraversal(object):
    pass

class Request(http.Request):
    implements(iweb.IRequest)
    
    site = None
    _initialprepath = None
    responseFilters = [rangefilter.rangefilter, defaultErrorHandler, defaultHeadersFilter]
    
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
            
            if path[:len(prepath)] == prepath:
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
                raise http.HTTPError(BAD_REQUEST)
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
            resp = self.preprocessRequest()
            if resp is not None:
                self._cbFinishRender(resp, requestContext).addErrback(self._processingFailed, requestContext)
                return
            self.parseURL()
            self.host = self.getHost()
        except:
            failedDeferred = self._processingFailed(failure.Failure(), requestContext)
            failedDeferred.addCallback(self._renderAndFinish)
            return


        deferredContext = self._getChild(requestContext,
                                              self.site.getRootResource(),
                                              self.postpath)
        deferredContext.addErrback(self._processingFailed, requestContext)
        deferredContext.addCallback(self._renderAndFinish)

    def preprocessRequest(self):
        if self.method == "OPTIONS" and self.uri == "*":
            response = http.Response(OK)
            response.headers.setHeader('Allow', ('GET', 'HEAD', 'OPTIONS', 'TRACE'))
            return response
        # This is where CONNECT would go if we wanted it
        return None
    
    def _getChild(self, ctx, res, path):
        """Create a PageContext for res, call res.locateChild, and pass the
        result on to _handleSegment."""
        
        # Create a context object to represent this new resource
        newctx = context.PageContext(tag=res, parent=ctx)
        newctx.remember(tuple(self.prepath), iweb.ICurrentSegments)
        newctx.remember(tuple(self.postpath), iweb.IRemainingSegments)

        if not path:
            return defer.succeed(newctx)

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
            raise http.HTTPError(NOT_FOUND)

        # If we got a deferred then we need to call back later, once the
        # child is actually available.
        if isinstance(newres, defer.Deferred):
            return newres.addCallback(
                lambda actualRes: self._handleSegment(
                    (actualRes, newpath), path, pageContext))

        if newpath is StopTraversal:
            if newres is pageContext.tag:
                return pageContext
            else:
                raise ValueError("locateChild must not return StopTraversal with a resource other than self.")
            
        newres = iweb.IResource(newres)
        if newres is pageContext.tag:
            assert not newpath is path, "URL traversal cycle detected when attempting to locateChild %r from resource %r." % (path, pageContext.tag)
            assert len(newpath) < len(path), "Infinite loop impending..."
            
        # We found a Resource... update the request.prepath and postpath
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
        if reason.check(http.HTTPError) is not None:
            # If the exception was an HTTPError, leave it alone
            d = defer.succeed(reason.value.response)
        else:
            # Otherwise, it was a random exception, so give a
            # ICanHandleException implementer a chance to render the page.
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
        response.code = INTERNAL_SERVER_ERROR
        response.headers.setHeader('content-type', http_headers.MimeType('text','html'))
        response.headers.setHeader('content-length', len(body))
        response.stream = stream.MemoryStream(body)
        self.writeResponse(response)

    def _cbFinishRender(self, result, ctx):
        def filterit(response, f):
            if (hasattr(f, 'handleErrors') or
                (response.code >= 200 and response.code < 300 and response.code != 204)):
                return f(self, response)
            else:
                return response

        response = iweb.IResponse(result)
        if response:
            d = defer.succeed(response)
            for f in self.responseFilters:
                d.addCallback(filterit, f)
            d.addCallback(self.writeResponse)
            return d

        resource = iweb.IResource(result, None)
        if resource:
            pageContext = context.PageContext(tag=resource, parent=ctx)
            d = defer.maybeDeferred(resource.renderHTTP, pageContext)
            d.addCallback(self._cbFinishRender, pageContext)
            return d

        raise TypeError("html is not a resource or a response")
    
    def notifyFinish(self):
        """Notify when finishing the request

        @return: A deferred. The deferred will be triggered when the
        request is finished -- with a C{None} value if the request
        finishes successfully or with an error if the request is stopped
        by the client.
        """
        self.notifications.append(defer.Deferred())
        return self.notifications[-1]

    def _error(self, reason):
        http.Request._error(self, reason)
        for d in self.notifications:
            d.errback(reason)
        self.notifications = []

    def _finished(self, x):
        http.Request._finished(self, x)
        for d in self.notifications:
            d.callback(None)
        self.notifications = []

class Site(http.HTTPFactory):

    counter = 0
    version = "TwistedWeb/%s" % copyright.version
    
    def __init__(self, resource, **kwargs):
        """Initialize.
        """
        if not 'requestFactory' in kwargs:
            kwargs['requestFactory'] = Request
        http.HTTPFactory.__init__(self, **kwargs)
        self.sessions = {}
        self.context = context.SiteContext()
        self.resource = resource

    def remember(self, obj, inter=None):
        """Remember the given object for the given interfaces (or all interfaces
        obj implements) in the site's context.

        The site context is the parent of all other contexts. Anything
        remembered here will be available throughout the site.
        """
        self.context.remember(obj, inter)
        
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
    
