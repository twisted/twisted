from twisted.internet import defer, endpoints, protocol, ssl, task
from twisted.protocols.basic import LineReceiver
from twisted.python.modules import getModule


class StartTLSClient(LineReceiver):
    def connectionMade(self):
        self.sendLine(b"plain text")
        self.sendLine(b"STARTTLS")

    def lineReceived(self, line):
        print("received: ", line)
        if line == b"READY":
            self.transport.startTLS(self.factory.options)
            self.sendLine(b"secure text")
            self.transport.loseConnection()


@defer.inlineCallbacks
def main(reactor):
    factory = protocol.Factory.forProtocol(StartTLSClient)
    certData = getModule(__name__).filePath.sibling("server.pem").getContent()
    factory.options = ssl.optionsForClientTLS(
        "example.com", ssl.PrivateCertificate.loadPEM(certData)
    )
    endpoint = endpoints.HostnameEndpoint(reactor, "localhost", 8000)
    startTLSClient = yield endpoint.connect(factory)

    done = defer.Deferred()
    startTLSClient.connectionLost = lambda reason: done.callback(None)
    yield done


if __name__ == "__main__":
    import starttls_client

    task.react(starttls_client.main)
