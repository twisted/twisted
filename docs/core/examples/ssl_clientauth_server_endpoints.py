#!/usr/bin/python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

from twisted.internet import defer, endpoints, protocol, task
from twisted.python import log

import echoserv

def main(reactor):
    log.startLogging(sys.stdout)
    factory = protocol.Factory.forProtocol(echoserv.Echo)
    descriptor = "ssl:8000:verifyCACerts=public.pem:requireCert=yes"
    endpoint = endpoints.serverFromString(reactor, descriptor)
    endpoint.listen(factory)
    return defer.Deferred()

if __name__ == '__main__':
    import ssl_clientauth_server_endpoints
    task.react(ssl_clientauth_server_endpoints.main)