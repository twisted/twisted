# -*- test-case-name: twisted.web.test.test_webclient -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP client.
"""

import os, types
from urlparse import urlunparse
from urllib import splithost, splittype
import zlib

from zope.interface import implements

from twisted.python import log
from twisted.web import http
from twisted.internet import defer, protocol, task, reactor
from twisted.internet.interfaces import IProtocol
from twisted.python import failure
from twisted.python.util import InsensitiveDict
from twisted.python.components import proxyForInterface
from twisted.web import error
from twisted.web.iweb import UNKNOWN_LENGTH, IBodyProducer, IResponse
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

    @ivar _completelyDone: A boolean indicating whether any further requests are
        necessary after this one completes in order to provide a result to
        C{self.factory.deferred}.  If it is C{False}, then a redirect is going
        to be followed.  Otherwise, this protocol's connection is the last one
        before firing the result Deferred.  This is used to make sure the result
        Deferred is only fired after the connection is cleaned up.
    """

    quietLoss = 0
    followRedirect = True
    failed = 0

    _completelyDone = True

    _specialHeaders = set(('host', 'user-agent', 'cookie', 'content-length'))

    def connectionMade(self):
        method = getattr(self.factory, 'method', 'GET')
        self.sendCommand(method, self.factory.path)
        if self.factory.scheme == 'http' and self.factory.port != 80:
            host = '%s:%s' % (self.factory.host, self.factory.port)
        elif self.factory.scheme == 'https' and self.factory.port != 443:
            host = '%s:%s' % (self.factory.host, self.factory.port)
        else:
            host = self.factory.host
        self.sendHeader('Host', self.factory.headers.get("host", host))
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

            self._completelyDone = False
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
        """
        When the connection used to issue the HTTP request is closed, notify the
        factory if we have not already, so it can produce a result.
        """
        if not self.quietLoss:
            http.HTTPClient.connectionLost(self, reason)
            self.factory.noPage(reason)
        if self._completelyDone:
            # Only if we think we're completely done do we tell the factory that
            # we're "disconnected".  This way when we're following redirects,
            # only the last protocol used will fire the _disconnectedDeferred.
            self.factory._disconnectedDeferred.callback(None)


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

    @ivar _disconnectedDeferred: A L{Deferred} which only fires after the last
        connection associated with the request (redirects may cause multiple
        connections to be required) has closed.  The result Deferred will only
        fire after this Deferred, so that callers can be assured that there are
        no more event sources in the reactor once they get the result.
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
        self._disconnectedDeferred = defer.Deferred()
        self.deferred = defer.Deferred()
        # Make sure the first callback on the result Deferred pauses the
        # callback chain until the request connection is closed.
        self.deferred.addBoth(self._waitForDisconnect)
        self.response_headers = None


    def _waitForDisconnect(self, passthrough):
        """
        Chain onto the _disconnectedDeferred, preserving C{passthrough}, so that
        the result is only available after the associated connection has been
        closed.
        """
        self._disconnectedDeferred.addCallback(lambda ignored: passthrough)
        return self._disconnectedDeferred


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
        """
        When a connection attempt fails, the request cannot be issued.  If no
        result has yet been provided to the result Deferred, provide the
        connection failure reason as an error result.
        """
        if self.waiting:
            self.waiting = 0
            # If the connection attempt failed, there is nothing more to
            # disconnect, so just fire that Deferred now.
            self._disconnectedDeferred.callback(None)
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
from twisted.web._newclient import Response, ResponseFailed

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



class FileBodyProducer(object):
    """
    L{FileBodyProducer} produces bytes from an input file object incrementally
    and writes them to a consumer.

    Since file-like objects cannot be read from in an event-driven manner,
    L{FileBodyProducer} uses a L{Cooperator} instance to schedule reads from
    the file.  This process is also paused and resumed based on notifications
    from the L{IConsumer} provider being written to.

    The file is closed after it has been read, or if the producer is stopped
    early.

    @ivar _inputFile: Any file-like object, bytes read from which will be
        written to a consumer.

    @ivar _cooperate: A method like L{Cooperator.cooperate} which is used to
        schedule all reads.

    @ivar _readSize: The number of bytes to read from C{_inputFile} at a time.
    """
    implements(IBodyProducer)

    # Python 2.4 doesn't have these symbolic constants
    _SEEK_SET = getattr(os, 'SEEK_SET', 0)
    _SEEK_END = getattr(os, 'SEEK_END', 2)

    def __init__(self, inputFile, cooperator=task, readSize=2 ** 16):
        self._inputFile = inputFile
        self._cooperate = cooperator.cooperate
        self._readSize = readSize
        self.length = self._determineLength(inputFile)


    def _determineLength(self, fObj):
        """
        Determine how many bytes can be read out of C{fObj} (assuming it is not
        modified from this point on).  If the determination cannot be made,
        return C{UNKNOWN_LENGTH}.
        """
        try:
            seek = fObj.seek
            tell = fObj.tell
        except AttributeError:
            return UNKNOWN_LENGTH
        originalPosition = tell()
        seek(0, self._SEEK_END)
        end = tell()
        seek(originalPosition, self._SEEK_SET)
        return end - originalPosition


    def stopProducing(self):
        """
        Permanently stop writing bytes from the file to the consumer by
        stopping the underlying L{CooperativeTask}.
        """
        self._inputFile.close()
        self._task.stop()


    def startProducing(self, consumer):
        """
        Start a cooperative task which will read bytes from the input file and
        write them to C{consumer}.  Return a L{Deferred} which fires after all
        bytes have been written.

        @param consumer: Any L{IConsumer} provider
        """
        self._task = self._cooperate(self._writeloop(consumer))
        d = self._task.whenDone()
        def maybeStopped(reason):
            # IBodyProducer.startProducing's Deferred isn't support to fire if
            # stopProducing is called.
            reason.trap(task.TaskStopped)
            return defer.Deferred()
        d.addCallbacks(lambda ignored: None, maybeStopped)
        return d


    def _writeloop(self, consumer):
        """
        Return an iterator which reads one chunk of bytes from the input file
        and writes them to the consumer for each time it is iterated.
        """
        while True:
            bytes = self._inputFile.read(self._readSize)
            if not bytes:
                self._inputFile.close()
                break
            consumer.write(bytes)
            yield None


    def pauseProducing(self):
        """
        Temporarily suspend copying bytes from the input file to the consumer
        by pausing the L{CooperativeTask} which drives that activity.
        """
        self._task.pause()


    def resumeProducing(self):
        """
        Undo the effects of a previous C{pauseProducing} and resume copying
        bytes to the consumer by resuming the L{CooperativeTask} which drives
        the write activity.
        """
        self._task.resume()



class _AgentMixin(object):
    """
    Base class offering facilities for L{Agent}-type classes.

    @since: 11.1
    """

    def _connectAndRequest(self, method, uri, headers, bodyProducer,
                           requestPath=None):
        """
        Internal helper to make the request.

        @param requestPath: If specified, the path to use for the request
            instead of the path extracted from C{uri}.
        """
        scheme, host, port, path = _parse(uri)
        if requestPath is None:
            requestPath = path
        d = self._connect(scheme, host, port)
        if headers is None:
            headers = Headers()
        if not headers.hasHeader('host'):
            headers = headers.copy()
            headers.addRawHeader(
                'host', self._computeHostValue(scheme, host, port))
        def cbConnected(proto):
            return proto.request(
                Request(method, requestPath, headers, bodyProducer))
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



class Agent(_AgentMixin):
    """
    L{Agent} is a very basic HTTP client.  It supports I{HTTP} and I{HTTPS}
    scheme URIs (but performs no certificate checking by default).  It does not
    support persistent connections.

    @ivar _reactor: The L{IReactorTCP} and L{IReactorSSL} implementation which
        will be used to set up connections over which to issue requests.

    @ivar _contextFactory: A web context factory which will be used to create
        SSL context objects for any SSL connections the agent needs to make.

    @ivar _connectTimeout: If not C{None}, the timeout passed to C{connectTCP}
        or C{connectSSL} for specifying the connection timeout.

    @ivar _bindAddress: If not C{None}, the address passed to C{connectTCP} or
        C{connectSSL} for specifying the local address to bind to.

    @since: 9.0
    """
    _protocol = HTTP11ClientProtocol

    def __init__(self, reactor, contextFactory=WebClientContextFactory(),
                 connectTimeout=None, bindAddress=None):
        self._reactor = reactor
        self._contextFactory = contextFactory
        self._connectTimeout = connectTimeout
        self._bindAddress = bindAddress


    def _wrapContextFactory(self, host, port):
        """
        Create and return a normal context factory wrapped around
        C{self._contextFactory} in such a way that C{self._contextFactory} will
        have the host and port information passed to it.

        @param host: A C{str} giving the hostname which will be connected to in
            order to issue a request.

        @param port: An C{int} giving the port number the connection will be
            on.

        @return: A context factory suitable to be passed to
            C{reactor.connectSSL}.
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

        @param port: An C{int} giving the port number the connection will be
            on.

        @return: A L{Deferred} which fires with a connected instance of
            C{self._protocol}.
        """
        cc = ClientCreator(self._reactor, self._protocol)
        kwargs = {}
        if self._connectTimeout is not None:
            kwargs['timeout'] = self._connectTimeout
        kwargs['bindAddress'] = self._bindAddress
        if scheme == 'http':
            d = cc.connectTCP(host, port, **kwargs)
        elif scheme == 'https':
            d = cc.connectSSL(host, port, self._wrapContextFactory(host, port),
                              **kwargs)
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
            L{twisted.web.iweb.IResponse} provider), or fails if there is a
            problem setting up a connection over which to issue the request.
            It may also fail with L{SchemeNotSupported} if the scheme of the
            given URI is not supported.
        @rtype: L{Deferred}
        """
        return self._connectAndRequest(method, uri, headers, bodyProducer)



class _HTTP11ClientFactory(protocol.ClientFactory):
    """
    A simple factory for L{HTTP11ClientProtocol}, used by L{ProxyAgent}.

    @since: 11.1
    """
    protocol = HTTP11ClientProtocol



class ProxyAgent(_AgentMixin):
    """
    An HTTP agent able to cross HTTP proxies.

    @ivar _factory: The factory used to connect to the proxy.

    @ivar _proxyEndpoint: The endpoint used to connect to the proxy, passing
        the factory.

    @since: 11.1
    """

    _factory = _HTTP11ClientFactory

    def __init__(self, endpoint):
        self._proxyEndpoint = endpoint


    def _connect(self, scheme, host, port):
        """
        Ignore the connection to the expected host, and connect to the proxy
        instead.
        """
        return self._proxyEndpoint.connect(self._factory())


    def request(self, method, uri, headers=None, bodyProducer=None):
        """
        Issue a new request via the configured proxy.
        """
        return self._connectAndRequest(method, uri, headers, bodyProducer,
                                       requestPath=uri)



class _FakeUrllib2Request(object):
    """
    A fake C{urllib2.Request} object for C{cookielib} to work with.

    @see: U{http://docs.python.org/library/urllib2.html#request-objects}

    @type uri: C{str}
    @ivar uri: Request URI.

    @type headers: L{twisted.web.http_headers.Headers}
    @ivar headers: Request headers.

    @type type: C{str}
    @ivar type: The scheme of the URI.

    @type host: C{str}
    @ivar host: The host[:port] of the URI.

    @since: 11.1
    """
    def __init__(self, uri):
        self.uri = uri
        self.headers = Headers()
        self.type, rest = splittype(self.uri)
        self.host, rest = splithost(rest)


    def has_header(self, header):
        return self.headers.hasHeader(header)


    def add_unredirected_header(self, name, value):
        self.headers.addRawHeader(name, value)


    def get_full_url(self):
        return self.uri


    def get_header(self, name, default=None):
        headers = self.headers.getRawHeaders(name, default)
        if headers is not None:
            return headers[0]
        return None


    def get_host(self):
        return self.host


    def get_type(self):
        return self.type


    def is_unverifiable(self):
        # In theory this shouldn't be hardcoded.
        return False



class _FakeUrllib2Response(object):
    """
    A fake C{urllib2.Response} object for C{cookielib} to work with.

    @type response: C{twisted.web.iweb.IResponse}
    @ivar response: Underlying Twisted Web response.

    @since: 11.1
    """
    def __init__(self, response):
        self.response = response


    def info(self):
        class _Meta(object):
            def getheaders(zelf, name):
                return self.response.headers.getRawHeaders(name, [])
        return _Meta()



class CookieAgent(object):
    """
    L{CookieAgent} extends the basic L{Agent} to add RFC-compliant
    handling of HTTP cookies.  Cookies are written to and extracted
    from a C{cookielib.CookieJar} instance.

    The same cookie jar instance will be used for any requests through this
    agent, mutating it whenever a I{Set-Cookie} header appears in a response.

    @type _agent: L{twisted.web.client.Agent}
    @ivar _agent: Underlying Twisted Web agent to issue requests through.

    @type cookieJar: C{cookielib.CookieJar}
    @ivar cookieJar: Initialized cookie jar to read cookies from and store
        cookies to.

    @since: 11.1
    """
    def __init__(self, agent, cookieJar):
        self._agent = agent
        self.cookieJar = cookieJar


    def request(self, method, uri, headers=None, bodyProducer=None):
        """
        Issue a new request to the wrapped L{Agent}.

        Send a I{Cookie} header if a cookie for C{uri} is stored in
        L{CookieAgent.cookieJar}. Cookies are automatically extracted and
        stored from requests.

        If a C{'cookie'} header appears in C{headers} it will override the
        automatic cookie header obtained from the cookie jar.

        @see: L{Agent.request}
        """
        if headers is None:
            headers = Headers()
        lastRequest = _FakeUrllib2Request(uri)
        # Setting a cookie header explicitly will disable automatic request
        # cookies.
        if not headers.hasHeader('cookie'):
            self.cookieJar.add_cookie_header(lastRequest)
            cookieHeader = lastRequest.get_header('Cookie', None)
            if cookieHeader is not None:
                headers = headers.copy()
                headers.addRawHeader('cookie', cookieHeader)

        d = self._agent.request(method, uri, headers, bodyProducer)
        d.addCallback(self._extractCookies, lastRequest)
        return d


    def _extractCookies(self, response, request):
        """
        Extract response cookies and store them in the cookie jar.

        @type response: L{twisted.web.iweb.IResponse}
        @param response: Twisted Web response.

        @param request: A urllib2 compatible request object.
        """
        resp = _FakeUrllib2Response(response)
        self.cookieJar.extract_cookies(resp, request)
        return response



class GzipDecoder(proxyForInterface(IResponse)):
    """
    A wrapper for a L{Response} instance which handles gzip'ed body.

    @ivar original: The original L{Response} object.

    @since: 11.1
    """

    def __init__(self, response):
        self.original = response
        self.length = UNKNOWN_LENGTH


    def deliverBody(self, protocol):
        """
        Override C{deliverBody} to wrap the given C{protocol} with
        L{_GzipProtocol}.
        """
        self.original.deliverBody(_GzipProtocol(protocol, self.original))



class _GzipProtocol(proxyForInterface(IProtocol)):
    """
    A L{Protocol} implementation which wraps another one, transparently
    decompressing received data.

    @ivar _zlibDecompress: A zlib decompress object used to decompress the data
        stream.

    @ivar _response: A reference to the original response, in case of errors.

    @since: 11.1
    """

    def __init__(self, protocol, response):
        self.original = protocol
        self._response = response
        self._zlibDecompress = zlib.decompressobj(16 + zlib.MAX_WBITS)


    def dataReceived(self, data):
        """
        Decompress C{data} with the zlib decompressor, forwarding the raw data
        to the original protocol.
        """
        try:
            rawData = self._zlibDecompress.decompress(data)
        except zlib.error:
            raise ResponseFailed([failure.Failure()], self._response)
        if rawData:
            self.original.dataReceived(rawData)


    def connectionLost(self, reason):
        """
        Forward the connection lost event, flushing remaining data from the
        decompressor if any.
        """
        try:
            rawData = self._zlibDecompress.flush()
        except zlib.error:
            raise ResponseFailed([reason, failure.Failure()], self._response)
        if rawData:
            self.original.dataReceived(rawData)
        self.original.connectionLost(reason)



class ContentDecoderAgent(object):
    """
    An L{Agent} wrapper to handle encoded content.

    It takes care of declaring the support for content in the
    I{Accept-Encoding} header, and automatically decompresses the received data
    if it's effectively using compression.

    @param decoders: A list or tuple of (name, decoder) objects. The name
        declares which decoding the decoder supports, and the decoder must
        return a response object when called/instantiated. For example,
        C{(('gzip', GzipDecoder))}. The order determines how the decoders are
        going to be advertized to the server.

    @since: 11.1
    """

    def __init__(self, agent, decoders):
        self._agent = agent
        self._decoders = dict(decoders)
        self._supported = ','.join([decoder[0] for decoder in decoders])


    def request(self, method, uri, headers=None, bodyProducer=None):
        """
        Send a client request which declares supporting compressed content.

        @see: L{Agent.request}.
        """
        if headers is None:
            headers = Headers()
        else:
            headers = headers.copy()
        headers.addRawHeader('accept-encoding', self._supported)
        deferred = self._agent.request(method, uri, headers, bodyProducer)
        return deferred.addCallback(self._handleResponse)


    def _handleResponse(self, response):
        """
        Check if the response is encoded, and wrap it to handle decompression.
        """
        contentEncodingHeaders = response.headers.getRawHeaders(
            'content-encoding', [])
        contentEncodingHeaders = ','.join(contentEncodingHeaders).split(',')
        while contentEncodingHeaders:
            name = contentEncodingHeaders.pop().strip()
            decoder = self._decoders.get(name)
            if decoder is not None:
                response = decoder(response)
            else:
                # Add it back
                contentEncodingHeaders.append(name)
                break
        if contentEncodingHeaders:
            response.headers.setRawHeaders(
                'content-encoding', [','.join(contentEncodingHeaders)])
        else:
            response.headers.removeHeader('content-encoding')
        return response



class RedirectAgent(object):
    """
    An L{Agent} wrapper which handles HTTP redirects.

    The implementation is rather strict: 301 and 302 behaves like 307, not
    redirecting automatically on methods different from C{GET} and C{HEAD}.

    @param redirectLimit: The maximum number of times the agent is allowed to
        follow redirects before failing with a L{error.InfiniteRedirection}.

    @since: 11.1
    """

    def __init__(self, agent, redirectLimit=20):
        self._agent = agent
        self._redirectLimit = redirectLimit


    def request(self, method, uri, headers=None, bodyProducer=None):
        """
        Send a client request following HTTP redirects.

        @see: L{Agent.request}.
        """
        deferred = self._agent.request(method, uri, headers, bodyProducer)
        return deferred.addCallback(
            self._handleResponse, method, uri, headers, 0)


    def _handleRedirect(self, response, method, uri, headers, redirectCount):
        """
        Handle a redirect response, checking the number of redirects already
        followed, and extracting the location header fields.
        """
        if redirectCount >= self._redirectLimit:
            err = error.InfiniteRedirection(
                response.code,
                'Infinite redirection detected',
                location=uri)
            raise ResponseFailed([failure.Failure(err)], response)
        locationHeaders = response.headers.getRawHeaders('location', [])
        if not locationHeaders:
            err = error.RedirectWithNoLocation(
                response.code, 'No location header field', uri)
            raise ResponseFailed([failure.Failure(err)], response)
        location = locationHeaders[0]
        deferred = self._agent.request(method, location, headers)
        return deferred.addCallback(
            self._handleResponse, method, uri, headers, redirectCount + 1)


    def _handleResponse(self, response, method, uri, headers, redirectCount):
        """
        Handle the response, making another request if it indicates a redirect.
        """
        if response.code in (http.MOVED_PERMANENTLY, http.FOUND,
                             http.TEMPORARY_REDIRECT):
            if method not in ('GET', 'HEAD'):
                err = error.PageRedirect(response.code, location=uri)
                raise ResponseFailed([failure.Failure(err)], response)
            return self._handleRedirect(response, method, uri, headers,
                                        redirectCount)
        elif response.code == http.SEE_OTHER:
            return self._handleRedirect(response, 'GET', uri, headers,
                                        redirectCount)
        return response



__all__ = [
    'PartialDownloadError', 'HTTPPageGetter', 'HTTPPageDownloader',
    'HTTPClientFactory', 'HTTPDownloader', 'getPage', 'downloadPage',
    'ResponseDone', 'Response', 'ResponseFailed', 'Agent', 'CookieAgent',
    'ProxyAgent', 'ContentDecoderAgent', 'GzipDecoder', 'RedirectAgent']
