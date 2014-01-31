from __future__ import print_function
import sys

from twisted.internet import defer, endpoints, protocol, ssl, task
from pprint import pprint
from twisted.internet.ssl import platformTrust

def main(reactor, host, port):
    contextFactory = ssl.CertificateOptions(peerTrust=platformTrust())
    port = int(port)
    handshook = defer.Deferred()

    class HandshakeComplete(object):
        def getContext(self):
            ctx = contextFactory.getContext()
            def cb(conn, where, code):
                if where & ssl.SSL.SSL_CB_HANDSHAKE_DONE:
                    handshook.callback(None)
            ctx.set_info_callback(cb)
            return ctx

    class DelayedDisconnectProtocol(protocol.Protocol):
        def connectionLost(self, reason):
            if not hasattr(handshook, 'result'):
                handshook.errback(reason)

    proto = DelayedDisconnectProtocol()

    connected = endpoints.connectProtocol(
        endpoints.SSL4ClientEndpoint(reactor, host, port,
                                     sslContextFactory=HandshakeComplete()),
        proto
    )

    def error(reason):
        if reason.check(ssl.SSL.Error):
            print("SSL Connection Error:")
            pprint(reason.value)

    def printCertificate(ignored):
        x509 = proto.transport.getPeerCertificate()
        if x509 is not None:
            cert = ssl.Certificate(x509)
            print(cert.dumpPEM())

    return (
        connected
        .addCallback(lambda connected: handshook)
        .addCallbacks(printCertificate, error)
    )

task.react(main, sys.argv[1:])
