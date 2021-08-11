#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import echoclient

from twisted.internet import defer, endpoints, protocol, ssl, task
from twisted.python.modules import getModule


@defer.inlineCallbacks
def main(reactor):
    factory = protocol.Factory.forProtocol(echoclient.EchoClient)
    certData = getModule(__name__).filePath.sibling("public.pem").getContent()
    authData = getModule(__name__).filePath.sibling("server.pem").getContent()
    clientCertificate = ssl.PrivateCertificate.loadPEM(authData)
    authority = ssl.Certificate.loadPEM(certData)
    options = ssl.optionsForClientTLS("example.com", authority, clientCertificate)
    endpoint = endpoints.SSL4ClientEndpoint(reactor, "localhost", 8000, options)
    echoClient = yield endpoint.connect(factory)

    done = defer.Deferred()
    echoClient.connectionLost = lambda reason: done.callback(None)
    yield done


if __name__ == "__main__":
    import ssl_clientauth_client

    task.react(ssl_clientauth_client.main)
