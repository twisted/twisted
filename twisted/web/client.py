# -*- test-case-name: twisted.web.test.test_webclient -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP client.
"""

import os, types
from urlparse import urlunparse

from twisted.python import log
from twisted.web import http
from twisted.internet import defer, protocol, reactor
from twisted.python import failure
from twisted.python.util import InsensitiveDict
from twisted.web import error
from twisted.web.http_headers import Headers
from twisted.python.compat import set


class PartialDownloadError(error.Error):
    """
    Page was only partially downloaded, we got disconnected in middle.

    @ivar response: All of the response body which was downloaded.
    """


class HTTPPageGetter(http.HTTPClient):
    """
    Gets a resource via HTTP, then quits.

    Typically used with L{HTTPClientFactory}.  Note that this class does not, by
    itself, do anything with the response.  If you want to download a resource
    into a file, use L{HTTPPageDownloader} instead.
    """

    quietLoss = 0
    followRedirect = True
    failed = 0

    _specialHeaders = set(('host', 'user-agent', 'cookie', 'content-length'))

    def connectionMade(self):
        method = getattr(self.factory, 'method', 'GET')
        self.sendCommand(method, self.factory.path)
        self.sendHeader('Host', self.factory.headers.get("host", self.factory.host))
        self.sendHeader('User-Agent', self.factory.agent)
        data = getattr(self.factory, 'postdata', None)
        if data is not None:
            self.sendHeader("Content-Length", str(len(data)))

        cookieData = []
        for (key, value) in self.factory.headers.items():
            if key.lower() not in self._specialHeaders:
                # we calculated it on our own
                self.sendHeader(key, value)
            if key.lower() == 'cookie':
                cookieData.append(value)
        for cookie, cookval in self.factory.cookies.items():
            cookieData.append('%s=%s' % (cookie, cookval))
        if cookieData:
            self.sendHeader('Cookie', '; '.join(cookieData))
        self.endHeaders()
        self.headers = {}

        if data is not None:
            self.transport.write(data)

    def handleHeader(self, key, value):
        """
        Called every time a header is received. Stores the header information
        as key-value pairs in the C{headers} attribute.

        @type key: C{str}
        @param key: An HTTP header field name.

        @type value: C{str}
        @param value: An HTTP header field value.
        """
        key = key.lower()
        l = self.headers.setdefault(key, [])
        l.append(value)

    def handleStatus(self, version, status, message):
        self.version, self.status, self.message = version, status, message
        self.factory.gotStatus(version, status, message)

    def handleEndHeaders(self):
        self.factory.gotHeaders(self.headers)
        m = getattr(self, 'handleStatus_'+self.status, self.handleStatusDefault)
        m()

    def handleStatus_200(self):
        pass

    handleStatus_201 = lambda self: self.handleStatus_200()
    handleStatus_202 = lambda self: self.handleStatus_200()

    def handleStatusDefault(self):
        self.failed = 1

    def handleStatus_301(self):
        l = self.headers.get('location')
        if not l:
            self.handleStatusDefault()
            return
        url = l[0]
        if self.followRedirect:
            scheme, host, port, path = \
                _parse(url, defaultPort=self.transport.getPeer().port)

            self.factory._redirectCount += 1
            if self.factory._redirectCount >= self.factory.redirectLimit:
                err = error.InfiniteRedirection(
                    self.status,
                    'Infinite redirection detected',
                    location=url)
                self.factory.noPage(failure.Failure(err))
                self.quietLoss = True
                self.transport.loseConnection()
                return

            self.factory.setURL(url)

            if self.factory.scheme == 'https':
                from twisted.internet import ssl
                contextFactory = ssl.ClientContextFactory()
                reactor.connectSSL(self.factory.host, self.factory.port,
                                   self.factory, contextFactory)
            else:
                reactor.connectTCP(self.factory.host, self.factory.port,
                                   self.factory)
        else:
            self.handleStatusDefault()
            self.factory.noPage(
                failure.Failure(
                    error.PageRedirect(
                        self.status, self.message, location = url)))
        self.quietLoss = True
        self.transport.loseConnection()

    def handleStatus_302(self):
        if self.afterFoundGet:
            self.handleStatus_303()
        else:
            self.handleStatus_301()


    def handleStatus_303(self):
        self.factory.method = 'GET'
        self.handleStatus_301()

    def connectionLost(self, reason):
        if not self.quietLoss:
            http.HTTPClient.connectionLost(self, reason)
            self.factory.noPage(reason)

    def handleResponse(self, response):
        if self.quietLoss:
            return
        if self.failed:
            self.factory.noPage(
                failure.Failure(
                    error.Error(
                        self.status, self.message, response)))
        if self.factory.method == 'HEAD':
            # Callback with empty string, since there is never a response
            # body for HEAD requests.
            self.factory.page('')
        elif self.length != None and self.length != 0:
            self.factory.noPage(failure.Failure(
                PartialDownloadError(self.status, self.message, response)))
        else:
            self.factory.page(response)
        # server might be stupid and not close connection. admittedly
        # the fact we do only one request per connection is also
        # stupid...
        self.transport.loseConnection()

    def timeout(self):
        self.quietLoss = True
        self.transport.loseConnection()
        self.factory.noPage(defer.TimeoutError("Getting %s took longer than %s seconds." % (self.factory.url, self.factory.timeout)))


class HTTPPageDownloader(HTTPPageGetter):

    transmittingPage = 0

    def handleStatus_200(self, partialContent=0):
        HTTPPageGetter.handleStatus_200(self)
        self.transmittingPage = 1
        self.factory.pageStart(partialContent)

    def handleStatus_206(self):
        self.handleStatus_200(partialContent=1)

    def handleResponsePart(self, data):
        if self.transmittingPage:
            self.factory.pagePart(data)

    def handleResponseEnd(self):
        if self.length:
            self.transmittingPage = 0
            self.factory.noPage(
                failure.Failure(
                    PartialDownloadError(self.status)))
        if self.transmittingPage:
            self.factory.pageEnd()
            self.transmittingPage = 0
        if self.failed:
            self.factory.noPage(
                failure.Failure(
                    error.Error(
                        self.status, self.message, None)))
            self.transport.loseConnection()


class HTTPClientFactory(protocol.ClientFactory):
    """Download a given URL.

    @type deferred: Deferred
    @ivar deferred: A Deferred that will fire when the content has
          been retrieved. Once this is fired, the ivars `status', `version',
          and `message' will be set.

    @type status: str
    @ivar status: The status of the response.

    @type version: str
    @ivar version: The version of the response.

    @type message: str
    @ivar message: The text message returned with the status.

    @type response_headers: dict
    @ivar response_headers: The headers that were specified in the
          response from the server.

    @type method: str
    @ivar method: The HTTP method to use in the request.  This should be one of
        OPTIONS, GET, HEAD, POST, PUT, DELETE, TRACE, or CONNECT (case
        matters).  Other values may be specified if the server being contacted
        supports them.

    @type redirectLimit: int
    @ivar redirectLimit: The maximum number of HTTP redirects that can occur
          before it is assumed that the redirection is endless.

    @type afterFoundGet: C{bool}
    @ivar afterFoundGet: Deviate from the HTTP 1.1 RFC by handling redirects
        the same way as most web browsers; if the request method is POST and a
        302 status is encountered, the redirect is followed with a GET method

    @type _redirectCount: int
    @ivar _redirectCount: The current number of HTTP redirects encountered.
    """

    protocol = HTTPPageGetter

    url = None
    scheme = None
    host = ''
    port = None
    path = None

    def __init__(self, url, method='GET', postdata=None, headers=None,
                 agent="Twisted PageGetter", timeout=0, cookies=None,
                 followRedirect=True, redirectLimit=20,
                 afterFoundGet=False):
        self.followRedirect = followRedirect
        self.redirectLimit = redirectLimit
        self._redirectCount = 0
        self.timeout = timeout
        self.agent = agent
        self.afterFoundGet = afterFoundGet
        if cookies is None:
            cookies = {}
        self.cookies = cookies
        if headers is not None:
            self.headers = InsensitiveDict(headers)
        else:
            self.headers = InsensitiveDict()
        if postdata is not None:
            self.headers.setdefault('Content-Length', len(postdata))
            # just in case a broken http/1.1 decides to keep connection alive
            self.headers.setdefault("connection", "close")
        self.postdata = postdata
        self.method = method

        self.setURL(url)

        self.waiting = 1
        self.deferred = defer.Deferred()
        self.response_headers = None

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.url)

    def setURL(self, url):
        self.url = url
        scheme, host, port, path = _parse(url)
        if scheme and host:
            self.scheme = scheme
            self.host = host
            self.port = port
        self.path = path

    def buildProtocol(self, addr):
        p = protocol.ClientFactory.buildProtocol(self, addr)
        p.followRedirect = self.followRedirect
        p.afterFoundGet = self.afterFoundGet
        if self.timeout:
            timeoutCall = reactor.callLater(self.timeout, p.timeout)
            self.deferred.addBoth(self._cancelTimeout, timeoutCall)
        return p

    def _cancelTimeout(self, result, timeoutCall):
        if timeoutCall.active():
            timeoutCall.cancel()
        return result

    def gotHeaders(self, headers):
        self.response_headers = headers
        if headers.has_key('set-cookie'):
            for cookie in headers['set-cookie']:
                cookparts = cookie.split(';')
                cook = cookparts[0]
                cook.lstrip()
                k, v = cook.split('=', 1)
                self.cookies[k.lstrip()] = v.lstrip()

    def gotStatus(self, version, status, message):
        self.version, self.status, self.message = version, status, message

    def page(self, page):
        if self.waiting:
            self.waiting = 0
            self.deferred.callback(page)

    def noPage(self, reason):
        if self.waiting:
            self.waiting = 0
            self.deferred.errback(reason)

    def clientConnectionFailed(self, _, reason):
        if self.waiting:
            self.waiting = 0
            self.deferred.errback(reason)


class HTTPDownloader(HTTPClientFactory):
    """Download to a file."""

    protocol = HTTPPageDownloader
    value = None

    def __init__(self, url, fileOrName,
                 method='GET', postdata=None, headers=None,
                 agent="Twisted client", supportPartial=0,
                 timeout=0, cookies=None, followRedirect=1,
                 redirectLimit=20, afterFoundGet=False):
        self.requestedPartial = 0
        if isinstance(fileOrName, types.StringTypes):
            self.fileName = fileOrName
            self.file = None
            if supportPartial and os.path.exists(self.fileName):
                fileLength = os.path.getsize(self.fileName)
                if fileLength:
                    self.requestedPartial = fileLength
                    if headers == None:
                        headers = {}
                    headers["range"] = "bytes=%d-" % fileLength
        else:
            self.file = fileOrName
        HTTPClientFactory.__init__(
            self, url, method=method, postdata=postdata, headers=headers,
            agent=agent, timeout=timeout, cookies=cookies,
            followRedirect=followRedirect, redirectLimit=redirectLimit,
            afterFoundGet=afterFoundGet)


    def gotHeaders(self, headers):
        HTTPClientFactory.gotHeaders(self, headers)
        if self.requestedPartial:
            contentRange = headers.get("content-range", None)
            if not contentRange:
                # server doesn't support partial requests, oh well
                self.requestedPartial = 0
                return
            start, end, realLength = http.parseContentRange(contentRange[0])
            if start != self.requestedPartial:
                # server is acting wierdly
                self.requestedPartial = 0


    def openFile(self, partialContent):
        if partialContent:
            file = open(self.fileName, 'rb+')
            file.seek(0, 2)
        else:
            file = open(self.fileName, 'wb')
        return file

    def pageStart(self, partialContent):
        """Called on page download start.

        @param partialContent: tells us if the download is partial download we requested.
        """
        if partialContent and not self.requestedPartial:
            raise ValueError, "we shouldn't get partial content response if we didn't want it!"
        if self.waiting:
            try:
                if not self.file:
                    self.file = self.openFile(partialContent)
            except IOError:
                #raise
                self.deferred.errback(failure.Failure())

    def pagePart(self, data):
        if not self.file:
            return
        try:
            self.file.write(data)
        except IOError:
            #raise
            self.file = None
            self.deferred.errback(failure.Failure())


    def noPage(self, reason):
        """
        Close the storage file and errback the waiting L{Deferred} with the
        given reason.
        """
        if self.waiting:
            self.waiting = 0
            if self.file:
                try:
                    self.file.close()
                except:
                    log.err(None, "Error closing HTTPDownloader file")
            self.deferred.errback(reason)


    def pageEnd(self):
        self.waiting = 0
        if not self.file:
            return
        try:
            self.file.close()
        except IOError:
            self.deferred.errback(failure.Failure())
            return
        self.deferred.callback(self.value)



def _parse(url, defaultPort=None):
    """
    Split the given URL into the scheme, host, port, and path.

    @type url: C{str}
    @param url: An URL to parse.

    @type defaultPort: C{int} or C{None}
    @param defaultPort: An alternate value to use as the port if the URL does
    not include one.

    @return: A four-tuple of the scheme, host, port, and path of the URL.  All
    of these are C{str} instances except for port, which is an C{int}.
    """
    url = url.strip()
    parsed = http.urlparse(url)
    scheme = parsed[0]
    path = urlunparse(('', '') + parsed[2:])

    if defaultPort is None:
        if scheme == 'https':
            defaultPort = 443
        else:
            defaultPort = 80

    host, port = parsed[1], defaultPort
    if ':' in host:
        host, port = host.split(':')
        try:
            port = int(port)
        except ValueError:
            port = defaultPort

    if path == '':
        path = '/'

    return scheme, host, port, path


def _makeGetterFactory(url, factoryFactory, contextFactory=None,
                       *args, **kwargs):
    """
    Create and connect an HTTP page getting factory.

    Any additional positional or keyword arguments are used when calling
    C{factoryFactory}.

    @param factoryFactory: Factory factory that is called with C{url}, C{args}
        and C{kwargs} to produce the getter

    @param contextFactory: Context factory to use when creating a secure
        connection, defaulting to C{None}

    @return: The factory created by C{factoryFactory}
    """
    scheme, host, port, path = _parse(url)
    factory = factoryFactory(url, *args, **kwargs)
    if scheme == 'https':
        from twisted.internet import ssl
        if contextFactory is None:
            contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory)
    else:
        reactor.connectTCP(host, port, factory)
    return factory


def getPage(url, contextFactory=None, *args, **kwargs):
    """
    Download a web page as a string.

    Download a page. Return a deferred, which will callback with a
    page (as a string) or errback with a description of the error.

    See L{HTTPClientFactory} to see what extra arguments can be passed.
    """
    return _makeGetterFactory(
        url,
        HTTPClientFactory,
        contextFactory=contextFactory,
        *args, **kwargs).deferred


def downloadPage(url, file, contextFactory=None, *args, **kwargs):
    """
    Download a web page to a file.

    @param file: path to file on filesystem, or file-like object.

    See HTTPDownloader to see what extra args can be passed.
    """
    factoryFactory = lambda url, *a, **kw: HTTPDownloader(url, file, *a, **kw)
    return _makeGetterFactory(
        url,
        factoryFactory,
        contextFactory=contextFactory,
        *args, **kwargs).deferred


# The code which follows is based on the new HTTP client implementation.  It
# should be significantly better than anything above, though it is not yet
# feature equivalent.

from twisted.internet.protocol import ClientCreator
from twisted.web.error import SchemeNotSupported
from twisted.web._newclient import ResponseDone, Request, HTTP11ClientProtocol
from twisted.web._newclient import Response

try:
    from twisted.internet.ssl import ClientContextFactory
except ImportError:
    class WebClientContextFactory(object):
        """
        A web context factory which doesn't work because the necessary SSL
        support is missing.
        """
        def getContext(self, hostname, port):
            raise NotImplementedError("SSL support unavailable")
else:
    class WebClientContextFactory(ClientContextFactory):
        """
        A web context factory which ignores the hostname and port and does no
        certificate verification.
        """
        def getContext(self, hostname, port):
            return ClientContextFactory.getContext(self)



class _WebToNormalContextFactory(object):
    """
    Adapt a web context factory to a normal context factory.

    @ivar _webContext: A web context factory which accepts a hostname and port
        number to its C{getContext} method.

    @ivar _hostname: The hostname which will be passed to
        C{_webContext.getContext}.

    @ivar _port: The port number which will be passed to
        C{_webContext.getContext}.
    """
    def __init__(self, webContext, hostname, port):
        self._webContext = webContext
        self._hostname = hostname
        self._port = port


    def getContext(self):
        """
        Called the wrapped web context factory's C{getContext} method with a
        hostname and port number and return the resulting context object.
        """
        return self._webContext.getContext(self._hostname, self._port)



class Agent(object):
    """
    L{Agent} is a very basic HTTP client.  It supports I{HTTP} and I{HTTPS}
    scheme URIs (but performs no certificate checking by default).  It does not
    support persistent connections.

    @ivar _reactor: The L{IReactorTCP} and L{IReactorSSL} implementation which
        will be used to set up connections over which to issue requests.

    @ivar _contextFactory: A web context factory which will be used to create
        SSL context objects for any SSL connections the agent needs to make.

    @since: 9.0
    """
    _protocol = HTTP11ClientProtocol

    def __init__(self, reactor, contextFactory=WebClientContextFactory()):
        self._reactor = reactor
        self._contextFactory = contextFactory


    def _wrapContextFactory(self, host, port):
        """
        Create and return a normal context factory wrapped around
        C{self._contextFactory} in such a way that C{self._contextFactory} will
        have the host and port information passed to it.

        @param host: A C{str} giving the hostname which will be connected to in
            order to issue a request.

        @param port: An C{int} giving the port number the connection will be on.

        @return: A context factory suitable to be passed to C{reactor.connectSSL}.
        """
        return _WebToNormalContextFactory(self._contextFactory, host, port)


    def _connect(self, scheme, host, port):
        """
        Connect to the given host and port, using a transport selected based on
        scheme.

        @param scheme: A string like C{'http'} or C{'https'} (the only two
            supported values) to use to determine how to establish the
            connection.

        @param host: A C{str} giving the hostname which will be connected to in
            order to issue a request.

        @param port: An C{int} giving the port number the connection will be on.

        @return: A L{Deferred} which fires with a connected instance of
            C{self._protocol}.
        """
        cc = ClientCreator(self._reactor, self._protocol)
        if scheme == 'http':
            d = cc.connectTCP(host, port)
        elif scheme == 'https':
            d = cc.connectSSL(host, port, self._wrapContextFactory(host, port))
        else:
            d = defer.fail(SchemeNotSupported(
                    "Unsupported scheme: %r" % (scheme,)))
        return d


    def request(self, method, uri, headers=None, bodyProducer=None):
        """
        Issue a new request.

        @param method: The request method to send.
        @type method: C{str}

        @param uri: The request URI send.
        @type uri: C{str}

        @param headers: The request headers to send.  If no I{Host} header is
            included, one will be added based on the request URI.
        @type headers: L{Headers}

        @param bodyProducer: An object which will produce the request body or,
            if the request body is to be empty, L{None}.
        @type bodyProducer: L{IBodyProducer} provider

        @return: A L{Deferred} which fires with the result of the request (a
            L{Response} instance), or fails if there is a problem setting up a
            connection over which to issue the request.  It may also fail with
            L{SchemeNotSupported} if the scheme of the given URI is not
            supported.
        @rtype: L{Deferred}
        """
        scheme, host, port, path = _parse(uri)
        d = self._connect(scheme, host, port)
        if headers is None:
            headers = Headers()
        if not headers.hasHeader('host'):
            # This is a lot of copying.  It might be nice if there were a bit
            # less.
            headers = Headers(dict(headers.getAllRawHeaders()))
            headers.addRawHeader(
                'host', self._computeHostValue(scheme, host, port))
        def cbConnected(proto):
            return proto.request(Request(method, path, headers, bodyProducer))
        d.addCallback(cbConnected)
        return d


    def _computeHostValue(self, scheme, host, port):
        """
        Compute the string to use for the value of the I{Host} header, based on
        the given scheme, host name, and port number.
        """
        if (scheme, port) in (('http', 80), ('https', 443)):
            return host
        return '%s:%d' % (host, port)



__all__ = [
    'PartialDownloadError',
    'HTTPPageGetter', 'HTTPPageDownloader', 'HTTPClientFactory', 'HTTPDownloader',
    'getPage', 'downloadPage',

    'ResponseDone', 'Response', 'Agent']
