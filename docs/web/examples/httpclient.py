#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to make a simple http client.

Usage:
    httpclient.py <url>

Don't forget the http:// when you type the web address!
"""

from __future__ import print_function

import sys
from pprint import pprint

from twisted import version
from twisted.python import log
from twisted.internet.defer import Deferred
from twisted.internet import reactor
from twisted.internet.protocol import Protocol
from twisted.web.iweb import UNKNOWN_LENGTH
from twisted.web.http_headers import Headers
from twisted.web.client import Agent, ResponseDone


class WriteToStdout(Protocol):
    def connectionMade(self):
        self.onConnLost = Deferred()

    def dataReceived(self, data):
        """
        Print out the html page received.
        """
        print('Got some:', data)

    def connectionLost(self, reason):
        if not reason.check(ResponseDone):
            reason.printTraceback()
        else:
            print('Response done')
        self.onConnLost.callback(None)


def main(reactor, url):
    """
    We create a custom UserAgent and send a GET request to a web server.
    """
    userAgent = 'Twisted/%s (httpclient.py)' % (version.short(),)
    agent = Agent(reactor)
    d = agent.request(
        'GET', url, Headers({'user-agent': [userAgent]}))
    def cbResponse(response):
        """
        Prints out the response returned by the web server.
        """
        pprint(vars(response))
        proto = WriteToStdout()
        if response.length is not UNKNOWN_LENGTH:
            print('The response body will consist of', response.length, 'bytes.')
        else:
            print('The response body length is unknown.')
        response.deliverBody(proto)
        return proto.onConnLost
    d.addCallback(cbResponse)
    d.addErrback(log.err)
    d.addBoth(lambda ign: reactor.callWhenRunning(reactor.stop))
    reactor.run()


if __name__ == '__main__':
    main(reactor, *sys.argv[1:])
