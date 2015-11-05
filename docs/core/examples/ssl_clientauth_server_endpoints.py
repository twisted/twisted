#!/usr/bin/python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
#
# This example demonstrates how to use endpoints.serverFromString() to create
# a listening TLS port.
#
# To run this example you will need at least one X.509 key and certificate for
# the server and one for the client.
#
# You can generate a server self-signed certificate with the following
# command. Make sure CN is localhost or the address you will later use to
# connect to the server.
#
# $ openssl req -x509 -nodes -newkey rsa:2048 \
#       -keyout server-key.pem -out server-cert.pem -days 3
#
# For the client side, you can create a similar self signed certificate:
#
# $ openssl req -x509 -nodes -newkey rsa:2048 \
#       -keyout client-key.pem -out client-cert.pem -days 3
#
# Put the CA certificates accepted by the server into a commons directory.
#
# $ mkdir ca-certs
# $ cp client-cert.pem ca-certs
#
# It will create a listening SSL port which will reply back the received data.
#
# To connect to the new port as a client you can use the `openssl s_client`
# helper.
#
# To connect without a certificate:
#
# $ openssl s_client -connect localhost:8000 -key client-key.pem
#
# $ openssl s_client -connect localhost:8000 \
#       -key client-key.pem -cert client-cert.pem
#
from __future__ import print_function
import sys

from twisted.internet import defer, endpoints, protocol, task
from twisted.python import log


class EchoProtocol(protocol.Protocol):
    """
    A simple protocol implementation which will write back the received data
    and inform about the connection made / lost.
    """

    def connectionMade(self):
        print('{} Connection made'.format(self.transport.getPeer()))


    def connectionLost(self, reason):
        print('{} Connection lost: {}'.format(
            self.transport.getPeer(), reason.getErrorMessage()))


    def dataReceived(self, data):
        """
        As soon as any data is received, write it back.
        """
        print(data)
        self.transport.write(data)


def main(reactor):
    log.startLogging(sys.stdout)

    # Set up a factory to create connection handlers for our server
    factory = protocol.Factory.forProtocol(EchoProtocol)

    # Set the descriptor we'll pass to serverFromString.
    #   ssl: Use SSL for the socket (as opposed to TCP (unsecured) or another
    #     kind of connection
    #   8000: The port number on which to listen
    #   clientCACertsPath=some_path: Check path of CA certificates against
    #     which to verify client certificates.
    #   requireCert=yes: This makes the socket reject client connections that
    #     do not provide a certificate that passes validation using the CA
    #     certs in caCertsDir.
    descriptor = (
        'ssl:8000:'
        'privateKey=server-key.pem:'
        'certKey=server-cert.pem:'
        'clientCACertsPath=ca-certs:'
        'requireCert=no'
        )

    # Pass the reactor and descriptor to serverFromString so we can have an
    # endpoint.
    endpoint = endpoints.serverFromString(reactor, descriptor)

    # Listen on the endpoint using the factory
    endpoint.listen(factory)

    print('Server started as {}'.format(descriptor))
    print('Connect to it from another terminal.')

    return defer.Deferred()


if __name__ == '__main__':
    task.react(main)
