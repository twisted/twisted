from __future__ import generators

from urllib import quote, string

import UserDict, math
from cStringIO import StringIO

from twisted.web2 import http_headers, iweb, http, stream
from twisted.web import http as old_http
from twisted.internet import defer
from twisted.python import components

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

class OldRequestAdapter(components.Componentized):
    """Adapt old requests to new request
    """

    implements(iweb.IOldRequest)
    
    def __new__(claz, original):
        # Cache the adapter. Replace this with a more better generalized
        # mechanism when one becomes available.
        if not hasattr(original, '_oldRequest'):
            original._oldRequest = object.__new__(claz, original)
        return original._oldRequest
    
    def _getFrom(where, name):
        def _get(self):
            return getattr(getattr(self, where), name)
        return property(_get)

    def _getsetFrom(where, name):
        def _get(self):
            return getattr(getattr(self, where), name)
        def _set(self, new):
            setattr(getattr(self, where), name, new)
        return property(_get, _set)

    def _getHeaders(where):
        def _get(self):
            headers = getattr(self, where).headers
            return HeaderAdapter(headers)
        return property(_get)
    
    code = _getsetFrom('response', 'code')
    code_message = ""
    
    method = _getsetFrom('request', 'method')
    uri = _getsetFrom('request', 'uri')
    clientproto = _getsetFrom('request', 'clientproto')
    
    received_headers = _getHeaders('request')
    headers = _getHeaders('response')
    path = _getsetFrom('request', 'path')
    
    # cookies = # Do I need this?
    # received_cookies = # Do I need this?
    content = StringIO() #### FIXME
    args = {} #### FIXME
    # stack = # WTF is stack?
    prepath = _getsetFrom('request', 'prepath')
    postpath = _getsetFrom('request', 'postpath')
    # client = ####
    # host = ####
    
    def __init__(self, request):
        self.request = request
        self.response = http.Response(stream=stream.ProducerStream())

    def _getData(self):
        return defer.succeed(None)
    def registerProducer(self, producer, streaming):
        self.response.stream.registerProducer(producer, streaming)
        
    def unregisterProducer(self):
        self.response.stream.unregisterProducer()
        
    def finish(self):
        self.response.stream.finish()
        
    def write(self, data):
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
        # FIXME
        when = long(math.ceil(when))
        self.response.headers.setHeader('Last-Modified', when)
        try:
            self.original.checkPreconditions()
        except http.HTTPError, err:
            self.original.code = err.response.code
            return old_http.CACHED
        return None

    def setETag(self, etag):
        # FIXME
        self.original.out_headers.setRawHeaders('ETag', etag)
        try:
            self.original.checkPreconditions()
        except http.HTTPError, err:
            self.original.code = err.responsecode
            return old_http.CACHED

    def getAllHeaders(self):
        return dict(self.request.headers.iteritems())

    def getRequestHostname(self):
        return self.request.host.split(':')[0]


### TODO:
    def getCookie(self, key):
        # get cookie
        return None

    def addCookie(self, k, v, expires=None, domain=None, path=None, max_age=None, comment=None, secure=None):
        if expires is None and max_age is not None:
            expires=max_age-time.time()
        cookie = http_headers.Cookie(k,v, expires=expires, domain=domain, path=path, comment=comment, secure=secure)
        # add Cookie
        
    def getHost(self):
        # FIXME, need a real API to acccess this.
        return self.original.chanRequest.channel.transport.getHost()

    def setHost(self, host, port, ssl=0):
        pass
    
    def getClientIP(self):
        return "127.0.0.1"

    def isSecure(self):
        return False

    def getUser(self):
        return ""

    def getPassword(self):
        return ""

    def getClient(self):
        return "127.0.0.1"

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
        self.setResponseCode(FOUND)
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

    def URLPath(self):
        from twisted.python import urlpath
        return urlpath.URLPath.fromRequest(self)

    def rememberRootURL(self):
        """
        Remember the currently-processed part of the URL for later
        recalling.
        """
        url = self.prePathURL()
        # remove one segment
        self.appRootURL = url[:url.rindex("/")]

    def getRootURL(self):
        """
        Get a previously-remembered URL.
        """
        return self.appRootURL

class OldResourceAdapter(object):
    implements(iweb.IResource)
    
    def __init__(self, original):
        self.__dict__['_OldResourceAdapter__original']=original
        
    def locateChild(self, ctx, segments):
        self.__original.locateChild(ctx, segments)
    
    def renderHTTP(self, ctx):
        oldRequest = iweb.IOldRequest(ctx)
        return oldRequest._getData().addCallback(self._processForm, ctx).addCallback(self._reallyRender, ctx)

    def _processForm(self, ignored, ctx):
        # Do form processing of request content
        pass

    def _finish(self, data, ctx):
        oldRequest = iweb.IOldRequest(ctx)
        oldRequest.write(data)
        oldRequest.finish()
        return oldRequest.response

    def _reallyRender(self, ignored, ctx):
        return defer.maybeDeferred(self.__original.renderHTTP, ctx).addCallback(self._finish, ctx)

    def __getattr__(self, name):
        return getattr(self.__original, name)

    def __setattr__(self, name):
        return setattr(self.__original, name)
