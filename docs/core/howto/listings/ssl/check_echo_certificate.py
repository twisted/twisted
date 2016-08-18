from __future__ import print_function
import sys
from twisted.internet import defer, endpoints, protocol, ssl, task

with open("../../../examples/server.pem") as f:
    certificate = ssl.Certificate.loadPEM(f.read())

def main(reactor, host, port=443):
    options = ssl.optionsForClientTLS(host.decode("utf-8"),
                                      trustRoot=certificate)
    port = int(port)
    done = defer.Deferred()

    class ShowCertificate(protocol.Protocol):
        def connectionMade(self):
            self.transport.write(b"GET / HTTP/1.0\r\n\r\n")
        def dataReceived(self, data):
            certificate = ssl.Certificate(self.transport.getPeerCertificate())
            print(certificate)
            self.transport.loseConnection()
        def connectionLost(self, reason):
            if reason.check(ssl.SSL.Error):
                print(reason.value)
            done.callback(None)

    endpoints.connectProtocol(
        endpoints.SSL4ClientEndpoint(reactor, host, port, options),
        ShowCertificate()
    )
    return done

task.react(main, sys.argv[1:])
