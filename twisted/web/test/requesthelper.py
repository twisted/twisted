# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Helpers related to HTTP requests, used by tests.
"""

from __future__ import division, absolute_import

__all__ = ['DummyChannel', 'DummyRequest']

from io import BytesIO

from zope.interface import implementer

from twisted.python.deprecate import deprecated
from twisted.python.versions import Version
from twisted.internet.defer import Deferred
from twisted.internet.address import IPv4Address
from twisted.internet.interfaces import ISSLTransport

from twisted.web.http_headers import Headers
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Session, Site


class DummyChannel:
    class TCP:
        port = 80
        disconnected = False

        def __init__(self):
            self.written = BytesIO()
            self.producers = []

        def getPeer(self):
            return IPv4Address("TCP", '192.168.1.1', 12344)

        def write(self, data):
            if not isinstance(data, bytes):
                raise TypeError("Can only write bytes to a transport, not %r" % (data,))
            self.written.write(data)

        def writeSequence(self, iovec):
            for data in iovec:
                self.write(data)

        def getHost(self):
            return IPv4Address("TCP", '10.0.0.1', self.port)

        def registerProducer(self, producer, streaming):
            self.producers.append((producer, streaming))

        def loseConnection(self):
            self.disconnected = True


    @implementer(ISSLTransport)
    class SSL(TCP):
        pass

    site = Site(Resource())

    def __init__(self):
        self.transport = self.TCP()


    def requestDone(self, request):
        pass



class DummyRequest(object):
    """
    Represents a dummy or fake request.

    @ivar _finishedDeferreds: C{None} or a C{list} of L{Deferreds} which will
        be called back with C{None} when C{finish} is called or which will be
        errbacked if C{processingFailed} is called.

    @type headers: C{dict}
    @ivar headers: A mapping of header name to header value for all request
        headers.

    @type outgoingHeaders: C{dict}
    @ivar outgoingHeaders: A mapping of header name to header value for all
        response headers.

    @type responseCode: C{int}
    @ivar responseCode: The response code which was passed to
        C{setResponseCode}.

    @type written: C{list} of C{bytes}
    @ivar written: The bytes which have been written to the request.
    """
    uri = b'http://dummy/'
    method = b'GET'
    client = None

    def registerProducer(self, prod,s):
        self.go = 1
        while self.go:
            prod.resumeProducing()

    def unregisterProducer(self):
        self.go = 0


    def __init__(self, postpath, session=None):
        self.sitepath = []
        self.written = []
        self.finished = 0
        self.postpath = postpath
        self.prepath = []
        self.session = None
        self.protoSession = session or Session(0, self)
        self.args = {}
        self.outgoingHeaders = {}
        self.requestHeaders = Headers()
        self.responseHeaders = Headers()
        self.responseCode = None
        self.headers = {}
        self._finishedDeferreds = []
        self._serverName = b"dummy"
        self.clientproto = b"HTTP/1.0"

    def getHeader(self, name):
        """
        Retrieve the value of a request header.

        @type name: C{bytes}
        @param name: The name of the request header for which to retrieve the
            value.  Header names are compared case-insensitively.

        @rtype: C{bytes} or L{NoneType}
        @return: The value of the specified request header.
        """
        return self.headers.get(name.lower(), None)


    def getAllHeaders(self):
        """
        Retrieve all the values of the request headers as a dictionary.

        @return: The entire C{headers} L{dict}.
        """
        return self.headers


    def setHeader(self, name, value):
        """TODO: make this assert on write() if the header is content-length
        """
        self.outgoingHeaders[name.lower()] = value

    def getSession(self):
        if self.session:
            return self.session
        assert not self.written, "Session cannot be requested after data has been written."
        self.session = self.protoSession
        return self.session


    def render(self, resource):
        """
        Render the given resource as a response to this request.

        This implementation only handles a few of the most common behaviors of
        resources.  It can handle a render method that returns a string or
        C{NOT_DONE_YET}.  It doesn't know anything about the semantics of
        request methods (eg HEAD) nor how to set any particular headers.
        Basically, it's largely broken, but sufficient for some tests at least.
        It should B{not} be expanded to do all the same stuff L{Request} does.
        Instead, L{DummyRequest} should be phased out and L{Request} (or some
        other real code factored in a different way) used.
        """
        result = resource.render(self)
        if result is NOT_DONE_YET:
            return
        self.write(result)
        self.finish()


    def write(self, data):
        if not isinstance(data, bytes):
            raise TypeError("write() only accepts bytes")
        self.written.append(data)

    def notifyFinish(self):
        """
        Return a L{Deferred} which is called back with C{None} when the request
        is finished.  This will probably only work if you haven't called
        C{finish} yet.
        """
        finished = Deferred()
        self._finishedDeferreds.append(finished)
        return finished


    def finish(self):
        """
        Record that the request is finished and callback and L{Deferred}s
        waiting for notification of this.
        """
        self.finished = self.finished + 1
        if self._finishedDeferreds is not None:
            observers = self._finishedDeferreds
            self._finishedDeferreds = None
            for obs in observers:
                obs.callback(None)


    def processingFailed(self, reason):
        """
        Errback and L{Deferreds} waiting for finish notification.
        """
        if self._finishedDeferreds is not None:
            observers = self._finishedDeferreds
            self._finishedDeferreds = None
            for obs in observers:
                obs.errback(reason)


    def addArg(self, name, value):
        self.args[name] = [value]


    def setResponseCode(self, code, message=None):
        """
        Set the HTTP status response code, but takes care that this is called
        before any data is written.
        """
        assert not self.written, "Response code cannot be set after data has been written: %s." % "@@@@".join(self.written)
        self.responseCode = code
        self.responseMessage = message


    def setLastModified(self, when):
        assert not self.written, "Last-Modified cannot be set after data has been written: %s." % "@@@@".join(self.written)


    def setETag(self, tag):
        assert not self.written, "ETag cannot be set after data has been written: %s." % "@@@@".join(self.written)


    def getClientIP(self):
        """
        Return the IPv4 address of the client which made this request, if there
        is one, otherwise C{None}.
        """
        if isinstance(self.client, IPv4Address):
            return self.client.host
        return None


    def getRequestHostname(self):
        """
        Get a dummy hostname associated to the HTTP request.

        @rtype: C{bytes}
        @returns: a dummy hostname
        """
        return self._serverName


    def getHost(self):
        """
        Get a dummy transport's host.

        @rtype: C{IPv4Address}
        @returns: a dummy transport's host
        """
        return IPv4Address('TCP', '127.0.0.1', 80)


    def getClient(self):
        """
        Get the client's IP address, if it has one.

        @return: The same value as C{getClientIP}.
        @rtype: L{bytes}
        """
        return self.getClientIP()

DummyRequest.getClient = deprecated(
    Version("Twisted", 15, 0, 0),
    "Twisted Names to resolve hostnames")(DummyRequest.getClient)
