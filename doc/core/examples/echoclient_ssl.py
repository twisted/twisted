#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

if __name__ == '__main__':
    import echoclient_ssl
    raise SystemExit(echoclient_ssl.main())

import sys

from twisted.internet.protocol import ClientFactory
from twisted.protocols.basic import LineReceiver
from twisted.internet import ssl, reactor

from echoclient import EchoClientFactory

def main():
    factory = EchoClientFactory()
    reactor.connectSSL('localhost', 8000, factory, ssl.CertificateOptions())
    reactor.run()
