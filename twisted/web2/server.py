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

import operator
import cgi
import copy
import time
import os
from urllib import quote
import urlparse
try:
    from twisted.protocols._c_urlarg import unquote
except ImportError:
    from urllib import unquote

# Twisted Imports
from twisted.internet import reactor, defer
from twisted.python import log, components
from twisted import copyright

# Sibling Imports
import resource
import http
import iweb
import responsecode
from twisted.web2 import util as webutil, http_headers


# Support for other methods may be implemented on a per-resource basis.
supportedMethods = ('GET', 'HEAD', 'POST')


class UnsupportedMethod(Exception):
    """Raised by a resource when faced with a strange request method.

    RFC 2616 (HTTP 1.1) gives us two choices when faced with this situtation:
    If the type of request is known to us, but not allowed for the requested
    resource, respond with NOT_ALLOWED.  Otherwise, if the request is something
    we don't know how to deal with in any case, respond with NOT_IMPLEMENTED.

    When this exception is raised by a Resource's render method, the server
    will make the appropriate response.

    This exception's first argument MUST be a sequence of the methods the
    resource *does* support.
    """

    allowedMethods = ()

    def __init__(self, allowedMethods, *args):
        if not operator.isSequenceType(allowedMethods):
            s = ("First argument must be a sequence of supported methodds, "
                 "but my first argument is not a sequence.")
            raise TypeError, s
        Exception.__init__(self, allowedMethods, *args)
        self.allowedMethods = allowedMethods
        

server_version = "TwistedWeb/2.0a1"
class Request(http.Request, components.Componentized):
    site = None
    prepathuri = None
    def __init__(self, *args, **kw):
        self.notifications = []
        if kw.has_key('site'):
            self.site = kw['site']
            del kw['site']
        if kw.has_key('prepathuri'):
            self.prepathuri = kw['prepathuri']
            del kw['prepathuri']
        
        components.Componentized.__init__(self)
        http.Request.__init__(self, *args, **kw)

    def defaultHeaders(self):
        self.out_headers.setHeader('server', server_version)
        self.out_headers.setHeader('date', time.time())
        self.out_headers.setHeader('content-type', http_headers.MimeType('text','html', (('charset', 'UTF-8'),)))

    def parseURL(self):
        (self.scheme, self.host, self.path,
         self.fragment, argstring, fragment) = urlparse.urlparse(self.uri)
        self.args = cgi.parse_qs(argstring, True)
        
    def getHost(self):
        if self.host:
            return self.host
        host = self.in_headers.getHeader('host')
        if not host:
            if self.clientproto >= (1,1):
                request.setResponseCode(400)
                request.write('')
                return
            host = self.chanRequest.channel.transport.getHost().host
        return host

    def process(self):
        "Process a request."
        # get site from channel
        if not self.site:
            self.site = self.chanRequest.channel.site
        self.defaultHeaders()
        self.parseURL()
        self.host = self.getHost()
        if not self.host:
            return
        # Resource Identification
        if self.prepathuri:
            prepath = map(unquote, self.prepathuri[1:].split('/'))
            self.postpath = map(unquote, self.path[1:].split('/'))
            
            if self.postpath[:len(prepath)] == prepath:
                self.prepath = prepath
                self.postpath = self.postpath[len(prepath):]
        else:
            self.prepath = []
            self.postpath = map(unquote, self.path[1:].split('/'))
        # make content string.
        # FIXME: make resource interface for choosing how to
        # handle content.
        self.content = StringIO.StringIO()
        self.deferredResource = self.site.getResourceFor(self)
        self.deferredResource.addErrback(self.processingFailed)
        
    def handleContentChunk(self, data):
        self.content.write(data)
    
    def handleContentComplete(self):
        # This sets up a seperate deferred chain because we don't want the
        # errbacks for rendering to be called for errors from before.
        self.deferredResource.addCallback(self._renderAndFinish)
        
    def _renderAndFinish(self, resource):
        d = defer.maybeDeferred(self.renderResource, resource)
        d.addCallback(self._cbFinishRender)
        d.addErrback(self._checkValidMethod)
        d.addErrback(self.processingFailed)
        
    def renderResource(self, resrc):
        from nevow import inevow
        if components.implements(resrc, inevow.IResource):
            render = resrc.renderHTTP
        else:
            render = resrc.render
        m = getattr(resrc, 'requestAdapter', None)
        if m:
            req = m(self)
        else:
            req = self
        return render(req)
    
    def _checkValidMethod(self, reason):
        reason.trap(UnsupportedMethod)
        self.setResponseCode(responsecode.NOT_IMPLEMENTED)
        self.out_headers.setHeader('content-type',('text','html',()))
        self.write('')
        self.finish()

    def returnErrorPage(self, error):
        ErrorPage.createFromRequest(self)
    
    def processingFailed(self, reason):
        log.err(reason)
        if self.startedWriting:
            # If we've already started writing, there's nothing to be done
            # but give up and rudely close the connection.
            # Anything else runs the risk of e.g. corrupting caches.
            self.chanRequest.abortConnection()
            return reason
        if self.site.displayTracebacks:
            body = ("<html><head><title>"
                    "web.Server Traceback (most recent call last)"
                    "</title></head>"
                    "<body>"
                    "<b>web.Server Traceback (most recent call last):</b>\n\n"
                    "%s\n\n</body></html>\n"
                    % webutil.formatFailure(reason))
        else:
            body = ("<html><head><title>Processing Failed</title></head><body>"
                    "<b>Processing Failed</b></body></html>")
        self.setResponseCode(responsecode.INTERNAL_SERVER_ERROR)
        self.out_headers.setHeader('content-type',http_headers.MimeType('text','html'))
        self.out_headers.setHeader('content-length', len(body))
        self.write(body)
        self.finish()
        return reason

    def _cbFinishRender(self, html):
        resource = iweb.IResource(html, None)
        if resource:
            d = defer.maybeDeferred(resource.render, self)
            d.addCallback(self._cbFinishRender)
            d.addErrback(self.processingFailed)
            return d
        if isinstance(html, str):
            self.write(html)
            self.finish()
        else:
            self.processingFailed(TypeError("html is not a string"))
        return html
            
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
    displayTracebacks = True
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

    def getResourceFor(self, request):
        """Get a resource for a request.

        This iterates through the resource heirarchy, calling
        locateChild on each resource it finds for a path element,
        stopping when it hits an element where isLeaf is true.
        """
        request.site = self
        # Sitepath is used to determine cookie names between distributed
        # servers and disconnected sites.
        request.sitepath = copy.copy(request.prepath)
        if not request.postpath:
            return defer.succeed(iweb.IResource(self.resource))
        print self.resource.__class__
        return self.getChild(iweb.IResource(self.resource), request,
                             tuple(request.postpath))

    def getChild(self, res, request, path):
        d = defer.maybeDeferred(res.locateChild, request,  path)
        d.addCallback(self.handleSegment, request, path, res)
        return d

    def handleSegment(self, result, request, path, res):
        from nevow import inevow
        newres, newpath = result
        if components.implements(newres, inevow.IResource):
            pass
        else:
            newres = iweb.IResource(newres, persist=True)
        
        size = len(path)-len(newpath)
        request.prepath.extend(request.postpath[:size])
        del request.postpath[:size]
        
        if not newpath:
            return newres
        if newres is res:
            assert newpath is not path, ("URL traversal cycle detected when "
                                         "attempting to locateChild %r from "
                                         "resource %r." % (path, res))
            assert len(newpath) < len(path), "Infinite loop impending..."
        return self.getChild(newres, request, newpath)
