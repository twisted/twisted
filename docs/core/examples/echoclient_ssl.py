#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import echoclient

from twisted.internet import defer, endpoints, protocol, ssl, task
from twisted.python.modules import getModule


async def main(reactor):
    factory = protocol.Factory.forProtocol(echoclient.EchoClient)
    certData = getModule(__name__).filePath.sibling("public.pem").getContent()
    authority = ssl.Certificate.loadPEM(certData)
    options = ssl.optionsForClientTLS("example.com", trustRoot=authority)
    tcpEndpoint = endpoints.HostnameEndpoint(reactor, "localhost", 8000)
    endpoint = endpoints.wrapClientTLS(options, tcpEndpoint, reactor)
    done = defer.Deferred()
    echoClient = await endpoint.connect(factory)
    echoClient.dataReceived = lambda data: done.callback(data)
    print(await done)


if __name__ == "__main__":
    import echoclient_ssl

    task.react(echoclient_ssl.main)
