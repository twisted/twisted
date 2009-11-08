#!/usr/bin/python
# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

import sys
from pprint import pprint

from twisted import version
from twisted.python import log
from twisted.internet.defer import Deferred
from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator, Protocol
from twisted.web.iweb import UNKNOWN_LENGTH
from twisted.web.client import _parse
from twisted.web.http_headers import Headers
# Use some private APIs for now.  They'll be exposed someplace public later
# on.
from twisted.web._newclient import ResponseDone, HTTP11ClientProtocol, Request

class WriteToStdout(Protocol):
    def connectionMade(self):
        self.onConnLost = Deferred()

    def dataReceived(self, data):
        print 'Got some:', data

    def connectionLost(self, reason):
        if not reason.check(ResponseDone):
            reason.printTraceback()
        else:
            print 'Response done'
        self.onConnLost.callback(None)


def main(reactor, url):
    cc = ClientCreator(reactor, HTTP11ClientProtocol)
    scheme, host, port, path = _parse(url)
    if scheme != 'http':
        raise SystemExit("Unsupported scheme: %r" % (scheme,))
    d = cc.connectTCP(host, port)
    def cbConnected(proto):
        return proto.request(Request(
                'GET', path,
                Headers({'host': [host], 'user-agent': ['Twisted/%s (httpclient.py)' % (version.short(),)]}),
                None))
    d.addCallback(cbConnected)
    def cbResponse(response):
        pprint(vars(response))
        proto = WriteToStdout()
        if response.length is not UNKNOWN_LENGTH:
            print 'The response body will consist of', response.length, 'bytes.'
        else:
            print 'The response body length is unknown.'
        response.deliverBody(proto)
        return proto.onConnLost
    d.addCallback(cbResponse)
    d.addErrback(log.err)
    d.addBoth(lambda ign: reactor.callWhenRunning(reactor.stop))
    reactor.run()


if __name__ == '__main__':
    main(reactor, *sys.argv[1:])
