#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
tls_alpn_npn_client
~~~~~~~~~~~~~~~~~~~

This test script demonstrates the usage of the acceptableProtocols API as a
client peer.

It performs next protocol negotiation using NPN and ALPN.

It will print what protocol was negotiated and exit.
The global variables are provided as input values.

This is set up to run against the server from
tls_alpn_npn_server.py from the directory that contains this example.

It assumes that you have a self-signed server certificate, named
`server-cert.pem` and located in the working directory.
"""
from __future__ import print_function

from twisted.internet import ssl, protocol, endpoints, task, defer
from twisted.python.filepath import FilePath

# The hostname the remote server to contact.
TARGET_HOST = u'localhost'

# The port to contact.
TARGET_PORT = 8080

# The list of protocols we'd be prepared to speak after the TLS negotiation is
# complete.
# The order of the protocols here is an order of preference: most servers will
# attempt to respect our preferences when doing the negotiation. This indicates
# that we'd prefer to use HTTP/2 if possible (where HTTP/2 is using the token
# 'h2'), but would also accept HTTP/1.1.
# The bytes here are sent literally on the wire, and so there is no room for
# ambiguity about text encodings.
# Try changing this list by adding, removing, and reordering protocols to see
# how it affects the result.
ACCEPTABLE_PROTOCOLS = [b'h2', b'http/1.1']

# Some safe initial data to send. This data is specific to HTTP/2: it is part
# of the HTTP/2 client preface (see RFC 7540 Section 3.5). This is used to
# signal to the remote server that it is aiming to speak HTTP/2, and to prevent
# a remote HTTP/1.1 server from expecting a 'proper' HTTP/1.1 request.
#
# FIXME: https://twistedmatrix.com/trac/ticket/6024
# This is only required because there is no event that fires when the TLS
# handshake is done. Instead, we wait for one that is implicitly after the
# TLS handshake is done: dataReceived. To trigger the remote peer to send data,
# we send some ourselves.
TLS_TRIGGER_DATA = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'


def main(reactor):
    certData = FilePath('server-cert.pem').getContent()
    serverCertificate = ssl.Certificate.loadPEM(certData)
    options = ssl.optionsForClientTLS(
        hostname=TARGET_HOST,
        trustRoot=serverCertificate,
        # `acceptableProtocols` is the targeted option for this example.
        acceptableProtocols=ACCEPTABLE_PROTOCOLS,
    )

    class BasicH2Request(protocol.Protocol):
        def connectionMade(self):
            print("Connection made")
            # Add a deferred that fires where we're done with the connection.
            # This deferred is returned to the reactor, and when we call it
            # back the reactor will clean up the protocol.
            self.complete = defer.Deferred()

            # Write some data to trigger the SSL handshake.
            self.transport.write(TLS_TRIGGER_DATA)

        def dataReceived(self, data):
            # We can only safely be sure what the next protocol is when we know
            # the TLS handshake is over. This is generally *not* in the call to
            # connectionMade, but instead only when we've received some data
            # back.
            print('Next protocol is: %s' % self.transport.negotiatedProtocol)
            self.transport.loseConnection()

            # If this is the first data write, we can tell the reactor we're
            # done here by firing the callback we gave it.
            if self.complete is not None:
                self.complete.callback(None)
                self.complete = None

        def connectionLost(self, reason):
            # If we haven't received any data, an error occurred. Otherwise,
            # we lost the connection on purpose.
            if self.complete is not None:
                print(("Connection lost due to error %s" % (reason,)))
                self.complete.callback(None)
            else:
                print("Connection closed cleanly")

    return endpoints.connectProtocol(
        endpoints.SSL4ClientEndpoint(
            reactor,
            TARGET_HOST,
            TARGET_PORT,
            options
        ),
        BasicH2Request()
    ).addCallback(lambda protocol: protocol.complete)

task.react(main)
