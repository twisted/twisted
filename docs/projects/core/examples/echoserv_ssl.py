#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

from twisted.internet import ssl, protocol, task, defer
from twisted.python import log

import echoserv

def main(reactor):
    with open('server.pem') as keyAndCert:
        certificate = ssl.PrivateCertificate.loadPEM(keyAndCert.read())
    log.startLogging(sys.stdout)
    factory = protocol.Factory.forProtocol(echoserv.Echo)
    reactor.listenSSL(8000, factory, certificate.options())
    return defer.Deferred()

if __name__ == '__main__':
    task.react(main)
