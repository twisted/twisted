# -*- test-case-name: twisted.web2.test.test_server -*-
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
from twisted.web2 import rangefilter
from twisted.web2 import version as web2_version
from twisted.web2.error import defaultErrorHandler
from twisted import __version__ as twisted_version

VERSION = "Twisted/%s TwistedWeb/%s" % (twisted_version, web2_version)
_errorMarker = object()


def defaultHeadersFilter(request, response, ctx):
    if not response.headers.hasHeader('server'):
        response.headers.setHeader('server', VERSION)
    if not response.headers.hasHeader('date'):
        response.headers.setHeader('date', time.time())
    return response
defaultHeadersFilter.handleErrors = True

def preconditionfilter(request, response, ctx):
    newresponse = http.checkPreconditions(request, response)
    if newresponse is not None:
        return newresponse
    return response

def doTrace(request):
    request = iweb.IRequest(request)
    txt = "%s %s HTTP/%d.%d\r\n" % (request.method, request.uri,
                                    request.clientproto[0], request.clientproto[1])

    l=[]
    for name, valuelist in request.headers.getAllRawHeaders():
        for value in valuelist:
            l.append("%s: %s\r\n" % (name, value))
    txt += ''.join(l)

    return http.Response(
        OK,
        {'content-type': http_headers.MimeType('message', 'http')}, 
        txt)

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
    """
    Indicates to Request._handleSegment that it should stop handling
    path segments.
    """
    pass


class Request(http.Request):
    """
    vars:
    site 
    scheme
    host
    port
    path
    params
    querystring
    
    args
    
    prepath
    postpath

    @ivar path: The path only (arguments not included).
    @ivar args: All of the arguments, including URL and POST arguments.
    @type args: A mapping of strings (the argument names) to lists of values.
                i.e., ?foo=bar&foo=baz&quux=spam results in
                {'foo': ['bar', 'baz'], 'quux': ['spam']}.
    """
    implements(iweb.IRequest)
    
    site = None
    _initialprepath = None
    responseFilters = [rangefilter.rangefilter, preconditionfilter,
                       defaultErrorHandler, defaultHeadersFilter]
    
    def __init__(self, *args, **kw):
        if kw.has_key('site'):
            self.site = kw['site']
            del kw['site']
        if kw.has_key('prepathuri'):
            self._initialprepath = kw['prepathuri']
            del kw['prepathuri']

        # Copy response filters from the class
        self.responseFilters = self.responseFilters[:]

        http.Request.__init__(self, *args, **kw)

    def addResponseFilter(self, f, atEnd=False):
        if atEnd:
            self.responseFilters.append(f)
        else:
            self.responseFilters.insert(0, f)

    def unparseURL(self, scheme=None, host=None, port=None,
                   path=None, params=None, querystring=None, fragment=None):
        """Turn the request path into a url string. For any pieces of
        the url that are not specified, use the value from the
        request. The arguments have the same meaning as the same named
        attributes of Request."""
        
        if scheme is None: scheme = self.scheme
        if host is None: host = self.host
        if port is None: port = self.port
        if path is None: path = self.path
        if params is None: params = self.params
        if querystring is None: query = self.querystring
        if fragment is None: fragment = ''
        
        if port == http.defaultPortForScheme.get(scheme, 0):
            hostport = host
        else:
            hostport = host + ':' + port
        
        return urlparse.urlunparse((
            scheme, hostport, path,
            params, querystring, fragment))
        
    def _parseURL(self):
        if self.uri[0] == '/':
            # Can't use urlparse for request_uri because urlparse
            # wants to be given an absolute or relative URI, not just
            # an abs_path, and thus gets '//foo' wrong.
            self.scheme = self.host = self.path = self.params = self.querystring = ''
            if '?' in self.uri:
                self.path, self.querystring = self.uri.split('?', 1)
            else:
                self.path = self.uri
            if ';' in self.path:
                self.path, self.params = self.path.split(';', 1)
        else:
            # It is an absolute uri, use standard urlparse
            (self.scheme, self.host, self.path,
             self.params, self.querystring, fragment) = urlparse.urlparse(self.uri)

        self.args = cgi.parse_qs(self.querystring, True)
        
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
        #print "_parseURL", self.uri, self.scheme, self.host, self.port, self.path, self.params, self.querystring

    def _fixupURLParts(self):
        hostaddr, secure = self.chanRequest.getHostInfo()
        if not self.scheme:
            self.scheme = ('http', 'https')[secure]
            
        if self.host:
            self.host, self.port = http.splitHostPort(self.scheme, self.host)
        else:
            # If GET line wasn't an absolute URL
            host = self.headers.getHeader('host')
            if host:
                self.host, self.port = http.splitHostPort(self.scheme, host)
            else:
                # When no hostname specified anywhere, either raise an
                # error, or use the interface hostname, depending on
                # protocol version
                if self.clientproto >= (1,1):
                    raise http.HTTPError(BAD_REQUEST)
                self.host = hostaddr.host
                self.port = hostaddr.port


    def process(self):
        "Process a request."
        requestContext = context.RequestContext(tag=self, parent=self.site.context)
        
        try:
            self.checkExpect()
            resp = self.preprocessRequest()
            if resp is not None:
                self._cbFinishRender(resp, requestContext).addErrback(self._processingFailed, requestContext)
                return
            self._parseURL()
            self._fixupURLParts()
        except:
            failedDeferred = self._processingFailed(failure.Failure(), requestContext)
            failedDeferred.addCallback(self._renderAndFinish)
            return
        
        deferredContext = self._getChild(requestContext,
                                         self.site.resource,
                                         self.postpath)
        deferredContext.addErrback(self._processingFailed, requestContext)
        deferredContext.addCallback(self._renderAndFinish)

    def preprocessRequest(self):
        """Do any request processing that doesn't follow the normal
        resource lookup procedure. "OPTIONS *" is handled here, for
        example. This would also be the place to do any CONNECT
        processing."""
        
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

        try:
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
                # We need to rethink how to do this.
                #if newres is pageContext.tag:
                    return pageContext
                #else:
                #    raise ValueError("locateChild must not return StopTraversal with a resource other than self.")

            newres = iweb.IResource(newres)
            if newres is pageContext.tag:
                assert not newpath is path, "URL traversal cycle detected when attempting to locateChild %r from resource %r." % (path, pageContext.tag)
                assert len(newpath) < len(path), "Infinite loop impending..."

            # We found a Resource... update the request.prepath and postpath
            for x in xrange(len(path) - len(newpath)):
                self.prepath.append(self.postpath.pop(0))
        except:
            # Handle errors here in the appropriate pageContext
            return self._processingFailed(failure.Failure(), pageContext)
        # But don't add an errback to this
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
                handler = iweb.ICanHandleException(ctx, default=self)
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
        
        response = http.Response(
            INTERNAL_SERVER_ERROR,
            {'content-type': http_headers.MimeType('text','html'),
             'content-length': len(body)},
            body)
        self.writeResponse(response)

    def _cbFinishRender(self, result, ctx):
        def filterit(response, f):
            if (hasattr(f, 'handleErrors') or
                (response.code >= 200 and response.code < 300 and response.code != 204)):
                return f(self, response, ctx)
            else:
                return response

        response = iweb.IResponse(result, None)
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

    def renderHTTP_exception(self, ctx, reason):
        log.msg("Exception rendering:", isErr=1)
        log.err(reason)
        
        body = ("<html><head><title>Internal Server Error</title></head>"
                "<body><h1>Internal Server Error</h1>An error occurred rendering the requested page. More information is available in the server log.</body></html>")
        
        return http.Response(
            INTERNAL_SERVER_ERROR,
            {'content-type': http_headers.MimeType('text','html'),
             'content-length': len(body)},
            body)

class Site:
    def __init__(self, resource):
        """Initialize.
        """
        self.context = context.SiteContext()
        self.resource = iweb.IResource(resource)

    def __call__(self, *args, **kwargs):
        return Request(site=self, *args, **kwargs)
    
    def remember(self, obj, inter=None):
        """Remember the given object for the given interfaces (or all interfaces
        obj implements) in the site's context.

        The site context is the parent of all other contexts. Anything
        remembered here will be available throughout the site.
        """
        self.context.remember(obj, inter)
