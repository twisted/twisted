from twisted.internet import ssl, reactor
from twisted.internet.protocol import Factory, Protocol

class Echo(Protocol):
    def dataReceived(self, data):
        self.transport.write(data)
    def connectionLost(self, reason):
        print(reason)

if __name__ == '__main__':
    factory = Factory()
    factory.protocol = Echo

    with open("public.pem") as certAuthCertFile:
        certAuthCert = ssl.Certificate.loadPEM(certAuthCertFile.read())

    with open("server.pem") as privateFile:
        serverCert = ssl.PrivateCertificate.loadPEM(privateFile.read())

    contextFactory = serverCert.options(certAuthCert)
    reactor.listenSSL(8000, factory, contextFactory)
    reactor.run()
