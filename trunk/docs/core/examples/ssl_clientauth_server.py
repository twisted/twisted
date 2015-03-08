#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

from twisted.internet import ssl, protocol, task, defer
from twisted.python import log
from twisted.python.modules import getModule

import echoserv

def main(reactor):
    log.startLogging(sys.stdout)
    certData = getModule(__name__).filePath.sibling('public.pem').getContent()
    authData = getModule(__name__).filePath.sibling('server.pem').getContent()
    authority = ssl.Certificate.loadPEM(certData)
    certificate = ssl.PrivateCertificate.loadPEM(authData)
    factory = protocol.Factory.forProtocol(echoserv.Echo)
    reactor.listenSSL(8000, factory, certificate.options(authority))
    return defer.Deferred()

if __name__ == '__main__':
    import ssl_clientauth_server
    task.react(ssl_clientauth_server.main)
