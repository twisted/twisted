#!/usr/bin/python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

from twisted.internet import defer, endpoints, protocol, task
from twisted.python import log

import echoserv

def main(reactor):
    log.startLogging(sys.stdout)
    # Set up a factory to create connection handlers for our server
    factory = protocol.Factory.forProtocol(echoserv.Echo)
    # Set the descriptor we'll pass to serverFromString.
    #   ssl: Use SSL for the socket (as opposed to TCP (unsecured) or another
    #     kind of connection
    #   8000: The port number on which to listen
    #   caCertsDir=.: Look to the current directory ('.') for the CA
    #     certificates against which to verify client certificates.
    #     You'll probably specify a different directory for your application;
    #     '.' works for the example scripts directory here.
    #   requireCert=yes: This makes the socket reject client connections that
    #     do not provide a certificate that passes validation using the CA
    #     certs in caCertsDir.
    descriptor = "ssl:8000:caCertsDir=.:requireCert=yes"
    # Pass the reactor and descriptor to serverFromString so we can have an
    # endpoint
    endpoint = endpoints.serverFromString(reactor, descriptor)
    # Listen on the endpoint using the factory
    endpoint.listen(factory)
    return defer.Deferred()

if __name__ == '__main__':
    import ssl_clientauth_server_endpoints
    task.react(ssl_clientauth_server_endpoints.main)