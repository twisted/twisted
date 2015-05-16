from twisted.internet import ssl, protocol, defer, task, endpoints
from twisted.protocols.basic import LineReceiver
from twisted.python.modules import getModule

class TLSServer(LineReceiver):
    def lineReceived(self, line):
        print("received: " + line)
        if line == "STARTTLS":
            print("-- Switching to TLS")
            self.sendLine('READY')
            self.transport.startTLS(self.factory.options)

def main(reactor):
    certData = getModule(__name__).filePath.sibling('server.pem').getContent()
    cert = ssl.PrivateCertificate.loadPEM(certData)
    factory = protocol.Factory.forProtocol(TLSServer)
    factory.options = cert.options()
    endpoint = endpoints.TCP4ServerEndpoint(reactor, 8000)
    endpoint.listen(factory)
    return defer.Deferred()

if __name__ == '__main__':
    import starttls_server
    task.react(starttls_server.main)
