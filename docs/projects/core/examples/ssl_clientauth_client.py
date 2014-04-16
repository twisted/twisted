from __future__ import print_function
from twisted.internet import ssl, reactor
from twisted.internet.protocol import ClientFactory, Protocol

class EchoClient(Protocol):
    def connectionMade(self):
        print("hello, world")
        self.transport.write("hello, world!")

    def dataReceived(self, data):
        print("Server said:", data)
        self.transport.loseConnection()

class EchoClientFactory(ClientFactory):
    protocol = EchoClient

    def clientConnectionFailed(self, connector, reason):
        print("Connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        print("Connection lost - goodbye!")
        reactor.stop()

if __name__ == '__main__':
    with open("server.pem") as keyAndCert:
        clientCert = ssl.PrivateCertificate.loadPEM(keyAndCert.read())
    with open("public.pem") as authCert:
        authority = ssl.Certificate.loadPEM(authCert.read())
    factory = EchoClientFactory()
    settings = ssl.settingsForClientTLS(
        u'example.com', clientCert,
        extraCertificateOptions={"certificate": clientCert.original,
                                 "privateKey": clientCert.privateKey.original}
    )
    reactor.connectSSL('localhost', 8000, factory, settings)
    reactor.run()
