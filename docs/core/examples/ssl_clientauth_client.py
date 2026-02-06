#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import echoclient

from twisted.internet import defer, endpoints, protocol, ssl, task
from twisted.python.modules import getModule


async def main(reactor):
    factory = protocol.Factory.forProtocol(echoclient.EchoClient)
    certData = getModule(__name__).filePath.sibling("public.pem").getContent()
    authData = getModule(__name__).filePath.sibling("server.pem").getContent()
    clientCertificate = ssl.PrivateCertificate.loadPEM(authData)
    authority = ssl.Certificate.loadPEM(certData)
    options = ssl.optionsForClientTLS(
        "example.com",
        trustRoot=authority,
        clientCertificate=clientCertificate,
    )
    tcpEndpoint = endpoints.HostnameEndpoint(reactor, "localhost", 8000)
    endpoint = endpoints.wrapClientTLS(options, tcpEndpoint, reactor)
    done = defer.Deferred()
    echoClient = await endpoint.connect(factory)
    echoClient.dataReceived = lambda data: done.callback(data)
    print(await done)


if __name__ == "__main__":
    import ssl_clientauth_client

    task.react(ssl_clientauth_client.main)
