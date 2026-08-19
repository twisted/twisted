#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

import echoserv

from twisted.internet import defer, protocol, ssl, task
from twisted.internet.endpoints import TCP6ServerEndpoint, wrapServerTLS
from twisted.python import log
from twisted.python.modules import getModule


def main(reactor):
    log.startLogging(sys.stdout)
    certData = getModule(__name__).filePath.sibling("server.pem").getContent()
    authData = getModule(__name__).filePath.sibling("server.pem").getContent()
    certificate = ssl.PrivateCertificate.loadPEM(certData)
    authority = ssl.Certificate.loadPEM(certData)
    factory = protocol.Factory.forProtocol(echoserv.Echo)
    tcpEndpoint = TCP6ServerEndpoint(reactor, 8000)
    endpoint = wrapServerTLS(certificate.options(authority), tcpEndpoint, reactor)
    endpoint.listen(factory)
    return defer.Deferred()


if __name__ == "__main__":
    import ssl_clientauth_server

    task.react(ssl_clientauth_server.main)
