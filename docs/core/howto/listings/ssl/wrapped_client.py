from sys import argv

from twisted.internet.defer import Deferred
from twisted.internet.endpoints import HostnameEndpoint, wrapClientTLS
from twisted.internet.interfaces import IReactorTCP, ITCPTransport
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.ssl import optionsForClientTLS
from twisted.internet.task import react
from twisted.python.failure import Failure


async def main(reactor: IReactorTCP, hostname: str = "example.com") -> None:
    class ExampleHTTP(Protocol):
        def makeConnection(self, transport: ITCPTransport) -> None:
            transport.write(f"GET / HTTP/1.1\r\nHost: {hostname}\r\n\r\n".encode())

        def dataReceived(self, data: bytes) -> None:
            print(f"data: {data!r}")

    tcpEndpoint = HostnameEndpoint(reactor, hostname, 443)
    tlsEndpoint = wrapClientTLS(optionsForClientTLS(hostname), tcpEndpoint)
    await tlsEndpoint.connect(Factory.forProtocol(ExampleHTTP))
    await Deferred()


if __name__ == "__main__":
    react(main, argv[1:])
