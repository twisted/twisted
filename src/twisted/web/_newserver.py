import attr
import copy

from zope.interface import implementer

from twisted.logger import Logger
from twisted.web.server import Request
from twisted.web.resource import getChildForRequest
from twisted.web.http import _genericHTTPChannelProtocolFactory, _REQUEST_TIMEOUT
from twisted.internet.interfaces import IProtocolFactory


class _TrashGarbageSiteDontUse(object):

    displayTracebacks = False




@implementer(IProtocolFactory)
@attr.s
class _Server(object):

    _protocol = attr.ib()
    _timeout = attr.ib()
    _resource = attr.ib()
    _requestFactory = attr.ib()
    _logger = attr.ib()
    _reactor = attr.ib()

    def getResourceFor(self, request):

        return getChildForRequest(self._resource, request)


    def buildProtocol(self, addr):

        p = self._protocol(None)
        p.factory = self
        p.callLater = self._reactor.callLater
        p.timeOut = self._timeout
        p.requestFactory = self._requestFactory
        p.site = _TrashGarbageSiteDontUse()
        p.site.getResourceFor = self.getResourceFor
        print(p)
        return p

    def doStart(self):
        pass

    def doStop(self):
        pass

    def log(self, what):
        print(what)


def server(resource, timeout=_REQUEST_TIMEOUT, requestFactory=Request, logger=None, reactor=None):

    if logger is None:
        logger = Logger()

    if reactor is None:
        from twisted.internet import reactor

    server = _Server(_genericHTTPChannelProtocolFactory, timeout, resource,
                     requestFactory, logger, reactor)

    return server
