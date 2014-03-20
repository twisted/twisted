#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

if __name__ == '__main__':
    import echoserv_ssl
    raise SystemExit(echoserv_ssl.main())

import sys

from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet import ssl, reactor
from twisted.python import log

import echoserv

def main():
    with open('server.pem') as keyAndCert:
        cert = ssl.PrivateCertificate.loadPEM(keyAndCert.read())

    log.startLogging(sys.stdout)
    factory = Factory()
    factory.protocol = echoserv.Echo
    reactor.listenSSL(8000, factory, cert.options())
    reactor.run()
