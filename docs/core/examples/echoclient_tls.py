#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import ssl, task, protocol, endpoints, defer
from twisted.python.modules import getModule

import echoclient

@defer.inlineCallbacks
def main(reactor):
    factory = protocol.Factory.forProtocol(echoclient.EchoClient)
    certData = getModule(__name__).filePath.sibling('public.pem').getContent()
    authority = ssl.Certificate.loadPEM(certData)
    options = ssl.optionsForClientTLS(u'example.com', authority)
    endpoint = endpoints.TLS4ClientEndpoint(reactor, 'localhost', 8000,
                                            options)
    echoClient = yield endpoint.connect(factory)

    done = defer.Deferred()
    echoClient.connectionLost = lambda reason: done.callback(None)
    yield done

if __name__ == '__main__':
    import echoclient_tls
    task.react(echoclient_tls.main)
