from __future__ import generators

from urllib import quote, string

import UserDict, math, time
from cStringIO import StringIO

from twisted.web2 import http_headers, iweb, stream, responsecode
from twisted.internet import defer, address
from twisted.python import components
from twisted.spread import pb

from zope.interface import implements

class HeaderAdapter(UserDict.DictMixin):
    def __init__(self, headers):
        self._headers = headers
        
    def __getitem__(self, name):
        raw = self._headers.getRawHeaders(name)
        if raw is None:
            raise KeyError(name)
        return ', '.join(raw)

    def __setitem__(self, name, value):
        self._headers.setRawHeaders([value])
        
    def __delitem__(self, name):
        if not self._headers.hasHeader(name):
            raise KeyError(name)
        self._headers.removeHeader(name)

    def iteritems(self):
        for k,v in self._headers.getAllRawHeaders():
            yield k, ', '.join(v)

    def keys(self):
        return [k for k, _ in self.iteritems()]

    def __iter__(self):
        for k, _ in self.iteritems():
            yield k

    def has_key(self, name):
        return self._headers.hasHeader(name)

def makeOldRequestAdapter(original):
    # Cache the adapter. Replace this with a more better generalized
    # mechanism when one becomes available.
    if not hasattr(original, '_oldRequest'):
        original._oldRequest = OldRequestAdapter(original)
    return original._oldRequest

def _addressToTuple(addr):
    if isinstance(addr, address.IPv4Address):
        return ('INET', addr.host, addr.port)
    elif isinstance(addr, address.UNIXAddress):
        return ('UNIX', addr.name)
    else:
        return tuple(addr)

class OldRequestAdapter(pb.Copyable, components.Componentized, object):
    """Adapt old requests to new request
    """
    implements(iweb.IOldRequest)
    
    def _getFrom(where, name):
        def _get(self):
            return getattr(getattr(self, where), name)
        return property(_get)

    def _getsetFrom(where, name):
        def _get(self):
            return getattr(getattr(self, where), name)
        def _set(self, new):
            setattr(getattr(self, where), name, new)
        def _del(self):
            delattr(getattr(self, where), name)
        return property(_get, _set, _del)

    def _getsetHeaders(where):
        def _get(self):
            headers = getattr(self, where).headers
            return HeaderAdapter(headers)

        def _set(self, newheaders):
            headers = http_headers.Headers()
            for n,v in newheaders.items():
                headers.setRawHeaders(n, (v,))
            newheaders = headers
            getattr(self, where).headers = newheaders
            
        return property(_get, _set)
    
    
    code = _getsetFrom('response', 'code')
    code_message = ""
    
    method = _getsetFrom('request', 'method')
    uri = _getsetFrom('request', 'uri')
    def _getClientproto(self):
        return "HTTP/%d.%d" % self.request.clientproto
    clientproto = property(_getClientproto)
    
    received_headers = _getsetHeaders('request')
    headers = _getsetHeaders('response')
    path = _getsetFrom('request', 'path')
    
    # cookies = # Do I need this?
    # received_cookies = # Do I need this?
    content = StringIO() #### FIXME
    args = _getsetFrom('request', 'args')
    # stack = # WTF is stack?
    prepath = _getsetFrom('request', 'prepath')
    postpath = _getsetFrom('request', 'postpath')

    def _getClient(self):
        return "WTF"
    client = property(_getClient)
    
    def _getHost(self):
        return address.IPv4Address("TCP", self.request.host, self.request.port)
    host = property(_getHost)
    
    def __init__(self, request):
        from twisted.web2 import http
        components.Componentized.__init__(self)
        self.request = request
        self.response = http.Response(stream=stream.ProducerStream())
        # This deferred will be fired by the first call to write on OldRequestAdapter
        # and will cause the headers to be output.
        self.deferredResponse = defer.Deferred()

    def getStateToCopyFor(self, issuer):
        # This is for distrib compatibility
        x = {}

        x['prepath'] = self.prepath
        x['postpath'] = self.postpath
        x['method'] = self.method
        x['uri'] = self.uri

        x['clientproto'] = self.clientproto
        self.content.seek(0, 0)
        x['content_data'] = self.content.read()
        x['remote'] = pb.ViewPoint(issuer, self)

        x['host'] = _addressToTuple(self.request.chanRequest.channel.transport.getHost())
        x['client'] = _addressToTuple(self.request.chanRequest.channel.transport.getPeer())

        return x

    def getTypeToCopy(self):
        # lie to PB so the ResourcePublisher doesn't have to know web2 exists
        # which is good because web2 doesn't exist.
        return 'twisted.web.server.Request'

    def registerProducer(self, producer, streaming):
        self.response.stream.registerProducer(producer, streaming)
        
    def unregisterProducer(self):
        self.response.stream.unregisterProducer()
        
    def finish(self):
        if self.deferredResponse is not None:
            d = self.deferredResponse
            self.deferredResponse = None
            d.callback(self.response)
        self.response.stream.finish()
        
    def write(self, data):
        if self.deferredResponse is not None:
            d = self.deferredResponse
            self.deferredResponse = None
            d.callback(self.response)
        self.response.stream.write(data)
        
    def getHeader(self, name):
        raw = self.request.headers.getRawHeaders(name)
        if raw is None:
            return None
        return ', '.join(raw)

    def setHeader(self, name, value):
        """Set an outgoing HTTP header.
        """
        self.response.headers.setRawHeaders(name, [value])
        
    def setResponseCode(self, code, message=None):
        # message ignored
        self.response.code = code

    def setLastModified(self, when):
        # Never returns CACHED -- can it and still be compliant?
        when = long(math.ceil(when))
        self.response.headers.setHeader('last-modified', when)
        return None

    def setETag(self, etag):
        self.response.headers.setRawHeaders('etag', [etag])
        return None

    def getAllHeaders(self):
        return dict(self.headers.iteritems())

    def getRequestHostname(self):
        return self.request.host


    def getCookie(self, key):
        for cookie in self.request.headers.getHeader('cookie', ()):
            if cookie.name == key:
                return cookie.value
            
        return None

    def addCookie(self, k, v, expires=None, domain=None, path=None, max_age=None, comment=None, secure=None):
        if expires is None and max_age is not None:
            expires=max_age-time.time()
        cookie = http_headers.Cookie(k,v, expires=expires, domain=domain, path=path, comment=comment, secure=secure)
        self.response.headers.setHeader('set-cookie', self.request.headers.getHeader('set-cookie', ())+(cookie,))

    def notifyFinish(self):
        ### FIXME
        return None
#        return self.request.notifyFinish()
    
    def getHost(self):
        return self.host
    
    def setHost(self, host, port, ssl=0):
        self.request.host = host
        self.request.port = port
        self.request.scheme = ssl and 'https' or 'http'

    def isSecure(self):
        return self.request.scheme == 'https'
    
    def getClientIP(self):
        if isinstance(self.request.chanRequest.getRemoteHost(), address.IPv4Address):
            return self.client.host
        else:
            return None
        return self.request.chanRequest.getRemoteHost()
        return "127.0.0.1"

    def getClient(self):
        return "127.0.0.1"

### FIXME:
    def getUser(self):
        return ""

    def getPassword(self):
        return ""

# Identical to original methods -- hopefully these don't have to change
    def sibLink(self, name):
        "Return the text that links to a sibling of the requested resource."
        if self.postpath:
            return (len(self.postpath)*"../") + name
        else:
            return name

    def childLink(self, name):
        "Return the text that links to a child of the requested resource."
        lpp = len(self.postpath)
        if lpp > 1:
            return ((lpp-1)*"../") + name
        elif lpp == 1:
            return name
        else: # lpp == 0
            if len(self.prepath) and self.prepath[-1]:
                return self.prepath[-1] + '/' + name
            else:
                return name

    def redirect(self, url):
        """Utility function that does a redirect.
        
        The request should have finish() called after this.
        """
        self.setResponseCode(responsecode.FOUND)
        self.setHeader("location", url)
    
    def prePathURL(self):
        port = self.getHost().port
        if self.isSecure():
            default = 443
        else:
            default = 80
        if port == default:
            hostport = ''
        else:
            hostport = ':%d' % port
        return quote('http%s://%s%s/%s' % (
            self.isSecure() and 's' or '',
            self.getRequestHostname(),
            hostport,
            string.join(self.prepath, '/')), "/:")

#     def URLPath(self):
#         from twisted.python import urlpath
#         return urlpath.URLPath.fromRequest(self)

# But nevow wants it to look like this... :(
    def URLPath(self):
        from nevow import url
        return url.URL.fromContext(self)

    def rememberRootURL(self, url=None):
        """
        Remember the currently-processed part of the URL for later
        recalling.
        """
        if url is None:
            url = self.prePathURL()
            # remove one segment
            self.appRootURL = url[:url.rindex("/")]
        else:
            self.appRootURL = url

    def getRootURL(self):
        """
        Get a previously-remembered URL.
        """
        return self.appRootURL

    
    session = None

    def getSession(self, sessionInterface = None):
        # Session management
        if not self.session:
            # FIXME: make sitepath be something
            cookiename = string.join(['TWISTED_SESSION'] + self.sitepath, "_")
            sessionCookie = self.getCookie(cookiename)
            if sessionCookie:
                try:
                    self.session = self.site.getSession(sessionCookie)
                except KeyError:
                    pass
            # if it still hasn't been set, fix it up.
            if not self.session:
                self.session = self.site.makeSession()
                self.addCookie(cookiename, self.session.uid, path='/')
        self.session.touch()
        if sessionInterface:
            return self.session.getComponent(sessionInterface)
        return self.session


class OldNevowResourceAdapter(object):
    implements(iweb.IResource)
    
    def __init__(self, original):
        # Can't use self.__original= because of __setattr__.
        self.__dict__['_OldNevowResourceAdapter__original']=original
        
    def __getattr__(self, name):
        return getattr(self.__original, name)

    def __setattr__(self, name, value):
        setattr(self.__original, name, value)

    def __delattr__(self, name):
        delattr(self.__original, name)

    def locateChild(self, ctx, segments):
        from twisted.web2.server import parsePOSTData
        request = iweb.IRequest(ctx)
        if request.method == "POST":
            return parsePOSTData(request).addCallback(
                lambda x: self.__original.locateChild(ctx, segments))
        return self.__original.locateChild(ctx, segments)
    
    def renderHTTP(self, ctx):
        from twisted.web2.server import parsePOSTData
        request = iweb.IRequest(ctx)
        if request.method == "POST":
            return parsePOSTData(request).addCallback(self.__reallyRender, ctx)
        return self.__reallyRender(None, ctx)

    def __reallyRender(self, ignored, ctx):
        # This deferred will be called when our resource is _finished_
        # writing, and will make sure we write the rest of our data
        # and finish the connection.
        defer.maybeDeferred(self.__original.renderHTTP, ctx).addCallback(self.__finish, ctx)

        # Sometimes the __original.renderHTTP will write() before we
        # even get this far, and we don't want to return
        # oldRequest.deferred if it's already been set to None.
        oldRequest = iweb.IOldRequest(ctx)
        if oldRequest.deferredResponse is None:
            return oldRequest.response
        return oldRequest.deferredResponse

    def __finish(self, data, ctx):
        oldRequest = iweb.IOldRequest(ctx)
        oldRequest.write(data)
        oldRequest.finish()


class OldResourceAdapter(object):
    implements(iweb.IOldNevowResource)

    def __init__(self, original):
        self.original = original

    def __repr__(self):
        return "<%s @ 0x%x adapting %r>" % (self.__class__.__name__, id(self), self.original)

    def locateChild(self, req, segments):
        import server
        request = iweb.IOldRequest(req)
        if self.original.isLeaf:
            return self, server.StopTraversal
        name = segments[0]
        if name == '':
            res = self
        else:
            request.prepath.append(request.postpath.pop(0))
            res = self.original.getChildWithDefault(name, request)
            request.postpath.insert(0, request.prepath.pop())
            
            if isinstance(res, defer.Deferred):
                return res.addCallback(lambda res: (res, segments[1:]))
            
        return res, segments[1:]

    def _handle_NOT_DONE_YET(self, data, request):
        from twisted.web.server import NOT_DONE_YET
        if data == NOT_DONE_YET:
            # Return a deferred that will never fire, so the finish
            # callback doesn't happen. This is because, when returning
            # NOT_DONE_YET, the page is responsible for calling finish.
            return defer.Deferred()
        else:
            return data

    def renderHTTP(self, req):
        request = iweb.IOldRequest(req)
        result = defer.maybeDeferred(self.original.render, request).addCallback(
            self._handle_NOT_DONE_YET, request)
        return result

__all__ = []
