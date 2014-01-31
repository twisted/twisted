import sys

from twisted.internet import defer, endpoints, protocol, ssl, task
from pprint import pprint
from twisted.internet.ssl import platformTrust

def printCertificate((proto, reason)):
    x509 = proto.transport.getPeerCertificate()
    if x509 is not None:
        cert = ssl.Certificate(x509)
        print(cert.dumpPEM())
    if reason.check(ssl.SSL.Error):
        print("SSL Connection Error:")
        pprint(reason.value)

def main(reactor, host, port):
    contextFactory = ssl.CertificateOptions(peerTrust=platformTrust())
    handshook = defer.Deferred()
    class HandshakeComplete(object):
        def getContext(self):
            ctx = contextFactory.getContext()
            def cb(conn, where, code):
                if where & ssl.SSL.SSL_CB_HANDSHAKE_DONE:
                    handshook.callback(None)
            ctx.set_info_callback(cb)
            return ctx

    ep = endpoints.SSL4ClientEndpoint(reactor, host, port,
                                      sslContextFactory=contextFactory)

    class DelayedDisconnectProtocol(protocol.Protocol):
        def connectionLost(self, reason):
            self.onConnectionLost.callback((self, reason))

    proto = DelayedDisconnectProtocol()

    return (endpoints.connectProtocol(ep, proto)
            .addCallback(lambda connected: handshook)
            .addCallback(printCertificate))

task.react(main, sys.argv[1:])
