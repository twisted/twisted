#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

from twisted.internet import ssl, task, protocol, endpoints, defer
from twisted.protocols.basic import LineReceiver
from twisted.python.modules import getModule
from twisted.python.util import sibpath

# This is a simple example showing how to use
# twisted.internet.ssl.trustRootFromCertificates() to make an object
# for an explict list of trusted certificates that can be passed as
# the trustRoot= argument to optionsForClientTLS(). In this case, the
# list has just 1 entry. You will need to un-comment the line
# "cert_file = 'google-root.pem'" to see a failure case.
#
# StartSSL is the actual issuer of twistedmatrix.com's certificate, so
# using 'startssl-ca.pem' should work properly and using
# 'google-root.pem' should fail. In this case, "work" means you should
# see some "receive: " lines (probably a "302 Found" redirect) whereas
# "fail" means you should see an error from connectionLost with a
# message like 'certificate verify failed'
#
# Note that the failure mode for TLS in this case might seem a little
# odd: you will get a successful connectionMade() call, but then
# immediately receive a connectionLost() with an SSL.Error as the
# reason.


class SimpleProtocol(LineReceiver):
    def __init__(self, *args, **kw):
        self._closed = []

    def when_closed(self):
        d = defer.Deferred()
        self._closed.append(d)
        return d

    def connectionMade(self):
        print("Connection made, doing GET")
        self.transport.write('GET / HTTP/1.1\r\n\r\n')

    def lineReceived(self, line):
        print("receive:", line)
        if line.strip() == '':
            self.transport.loseConnection()

    def connectionLost(self, reason):
        print("Connection lost:", reason.value)
        for d in self._closed:
            d.callback(None)
        self._closed = []


@defer.inlineCallbacks
def main(reactor):
    cert_file = sibpath(__file__, 'startssl-ca.pem')
    # cert_file = sibpath(__file__, 'google-root.pem')  # uncomment this line to see a failure
    with open(cert_file, 'r') as f:
        root_cert = ssl.Certificate.loadPEM(f.read())

    factory = protocol.Factory.forProtocol(SimpleProtocol)
    options = ssl.optionsForClientTLS(
        u'twistedmatrix.com',
        trustRoot=ssl.trustRootFromCertificates([root_cert])
    )
    endpoint = endpoints.SSL4ClientEndpoint(
        reactor, 'www.twistedmatrix.com', 443, options,
    )
    proto = yield endpoint.connect(factory)
    yield proto.when_closed()

if __name__ == '__main__':
    task.react(main)
