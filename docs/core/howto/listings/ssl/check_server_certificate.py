from __future__ import print_function
import sys
from twisted.internet import defer, endpoints, protocol, ssl, task, error

def main(reactor, host, port=443):
    options = ssl.optionsForClientTLS(hostname=host.decode('utf-8'))
    port = int(port)

    class ShowCertificate(protocol.Protocol):
        def connectionMade(self):
            self.transport.write(b"GET / HTTP/1.0\r\n\r\n")
            self.done = defer.Deferred()
        def dataReceived(self, data):
            certificate = ssl.Certificate(self.transport.getPeerCertificate())
            print("OK:", certificate)
            self.transport.abortConnection()
        def connectionLost(self, reason):
            print("Lost.")
            if not reason.check(error.ConnectionClosed):
                print("BAD:", reason.value)
            self.done.callback(None)

    return endpoints.connectProtocol(
        endpoints.SSL4ClientEndpoint(reactor, host, port, options),
        ShowCertificate()
    ).addCallback(lambda protocol: protocol.done)

task.react(main, sys.argv[1:])
