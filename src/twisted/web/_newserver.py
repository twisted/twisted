# -*- test-case-name: twisted.web.test.test_newserver -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Next-Generation Web Sites for the Internet Zone Age.
"""

import attr

from os import urandom
from binascii import hexlify
from zope.interface import implementer

from twisted.logger import Logger, globalLogPublisher, formatEvent
from twisted.web.server import Request, GzipEncoderFactory, Session
from twisted.web.resource import (
    getChildForRequest, EncodingResourceWrapper, _wrap)
from twisted.web.http import (_genericHTTPChannelProtocolFactory,
                              datetimeToLogString,
                              _REQUEST_TIMEOUT, H2_ENABLED, _escape)
from twisted.internet.interfaces import (
    IProtocolFactory, IProtocolNegotiationFactory)


@attr.s
class _SessionFandangler(object):
    _site = attr.ib()
    _sessionFactory = attr.ib()
    _reactor = attr.ib(default=None)

    def makeSession(self):
        uid = hexlify(self._site._entropy(32))
        session = self._site.sessions[uid] = self._sessionFactory(
            self._site, uid, reactor=self._reactor)
        session.startCheckingExpiration()
        return session

    def getSession(self, uid):
        return self._site.sessions[uid]



@implementer(IProtocolFactory, IProtocolNegotiationFactory)
@attr.s
class Server(object):
    """
    A web server.

    Instantiating this object outside of L{makeServer} is B{not supported}.
    """
    _protocol = attr.ib()
    _displayTracebacks = attr.ib()
    _compressResponses = attr.ib()
    _trustedReverseProxyIPs = attr.ib()
    _timeout = attr.ib()
    _resource = attr.ib()
    _requestFactory = attr.ib()
    _sessionFactory = attr.ib()
    _logger = attr.ib()
    _reactor = attr.ib()


    def buildProtocol(self, addr):

        @attr.s
        class _TrashGarbageSiteDontUse(object):

            displayTracebacks = self._displayTracebacks
            _sessionFandangler = attr.ib(default=attr.Factory(
                lambda _self: _SessionFandangler(_self, self._sessionFactory,
                                                 self._reactor),
                takes_self=True))
            _entropy = attr.ib(default=urandom)
            sessions = attr.ib(default=attr.Factory(dict))

            def getResourceFor(self_, request):
                res = getChildForRequest(self._resource, request)
                if self._compressResponses:
                    res = _wrap(res,
                                EncodingResourceWrapper,[GzipEncoderFactory()])
                return res

            def makeSession(self):
                return self._sessionFandangler.makeSession()

            def getSession(self, uid):
                """
                Get a previously generated session.

                @param uid: Unique ID of the session.
                @type uid: L{bytes}.

                @raise: L{KeyError} if the session is not found.
                """
                return self._sessionFandangler.getSession(uid)

            def _getTrustedReverseProxyIPs(self_):
                """
                Get the IPs that are trusted to set X-Forwarded-For headers.

                @rtype: L{list} of L{str}
                """
                if self._trustedReverseProxyIPs is None:
                    return []
                return self._trustedReverseProxyIPs

        p = self._protocol(None)
        p.factory = self
        p.callLater = self._reactor.callLater
        p.timeOut = self._timeout
        p.requestFactory = self._requestFactory
        p.site = _TrashGarbageSiteDontUse()
        return p


    def doStart(self):
        """
        Start.
        """


    def doStop(self):
        """
        Stop.
        """


    def log(self, request):

        timestamp = datetimeToLogString(self._reactor.seconds())
        referrer = _escape(request.getHeader(b"referer") or b"-")
        agent = _escape(request.getHeader(b"user-agent") or b"-")
        line = (
            u'"{ip}" - "{method} {uri} {protocol}" '
            u'{code} {length} "{referrer}" "{agent}"'
            )

        self._logger.info(
            line,
            ip=_escape(request.getClientIP() or b"-"),
            timestamp=timestamp,
            method=_escape(request.method),
            uri=_escape(request.uri),
            protocol=_escape(request.clientproto),
            code=request.code,
            length=request.sentLength or u"-",
            referrer=referrer,
            agent=agent,
        )


    # IProtocolNegotiationFactory
    def acceptableProtocols(self):
        """
        Protocols this server can speak.
        """
        baseProtocols = [b'http/1.1']

        if H2_ENABLED:
            baseProtocols.insert(0, b'h2')

        return baseProtocols



def makeServer(resource, displayTracebacks=True, compressResponses=True,
               timeout=_REQUEST_TIMEOUT, requestFactory=Request,
               sessionFactory=Session, logger=None,
               trustedReverseProxyIPs=None, reactor=None):
    """
    Create a web server.

    @param resource: The resource to serve.
    @type resource: L{twisted.web.resource.Resource}

    @param displayTracebacks: Whether or not L{Resource}s will return
        tracebacks experienced during processing to the web client.
    @type displayTracebacks: L{bool}

    @param compressResponses: Whether or not to compress responses delivered by
        this L{server} with gzip.
    @type compressResponses: L{bool}

    @param timeout: The timeout for requests.
    @type timeout: L{int}

    @param requestFactory: A factory which is called with (channel) and creates
        L{Request} instances.  Default to L{Request}.
    @type requestFactory: C{callable} that returns objects that implement
        L{twisted.web.iweb.IRequest}

    @param sessionFactory: The Session class to use.  Default to L{Session}.
    @type sessionFactory: L{Session}

    @param logger: The logger for the server to use.
    @type logger: L{twisted.logger.Logger}

    @param trustedReverseProxyIPs: A C{list} of IPs which can send
        C{X-Forwarded-For} headers that C{Request} will use as the IP, instead
        of the origin IP.
    @type trustedReverseProxyIPs: L{list} of L{str}

    @param reactor: The C{Reactor} used for timekeeping.
    """

    if logger is None:
        logger = Logger('twisted.web.server')

    if reactor is None:
        from twisted.internet import reactor

    server = Server(protocol=_genericHTTPChannelProtocolFactory,
                    displayTracebacks=displayTracebacks,
                    compressResponses=compressResponses,
                    trustedReverseProxyIPs=trustedReverseProxyIPs,
                    timeout=timeout,
                    resource=resource,
                    requestFactory=requestFactory,
                    sessionFactory=sessionFactory,
                    logger=logger,
                    reactor=reactor,
    )

    # Set up the Logger source correctly
    logger.source = server
    return server



def makeCombinedLogFormatFileForServer(server, logFile,
                                       logPublisher=globalLogPublisher):
    """
    Make a Combined Log Format file, logging from C{server}.

    @param server: The server returned by L{makeServer}.

    @param logFile: A file-like object, opened in binary format.

    @param logPublisher: A log publisher to observe.
    @type logPublisher: A L{twisted.logger.ILogObserver} implementer.
    """

    def consume(event):
        # Heuristics to find what should actually be logged
        if event.get("log_source", None) is server and "agent" in event.keys():
            e = dict(event)
            e["log_format"] = (
                u'{ip} - - {timestamp} "{method} {uri} {protocol}" '
                u'{code} {length} "{referrer}" "{agent}"'
            )

            formatted = formatEvent(e).encode('utf-8') + b"\n"
            logFile.write(formatted)

    logPublisher.addObserver(consume)
    return lambda: logPublisher.removeObserver(consume)
