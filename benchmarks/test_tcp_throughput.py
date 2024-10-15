from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Factory, Protocol, ServerFactory
from twisted.protocols.wire import Echo
from twisted.internet.testing import _benchmarkWithReactor as benchmarkWithReactor
from twisted.internet import reactor


class Server(Echo):

    def connectionMade(self):
        self.transport.setTcpNoDelay(True)


class Counter(Protocol):
    count = 0
    sendAmount = 0
    finished : None | Deferred = None

    def connectionMade(self):
        self.transport.setTcpNoDelay(True)

    def dataReceived(self, b):
        self.count += len(b)
        if self.count == self.sendAmount:
            self.transport.loseConnection()

    def connectionLost(self, reason):
        assert self.finished is not None
        self.finished.callback(self.count)


class Client(object):

    def __init__(self, reactor, server):
        self._reactor = reactor
        self._server = server
        self._sent = 0

    def run(self, sendAmount, chunkSize):
        self._sendAmount = sendAmount
        self._bytes = b'x' * chunkSize
        # Set up a connection
        factory = Factory()
        factory.protocol = Counter
        d = self._server.connect(factory)
        d.addCallback(self._connected)
        return d

    def _connected(self, client):
        self._client = client
        self._client.finished = Deferred()
        self._client.sendAmount = self._sendAmount
        client.transport.registerProducer(self, False)
        return self._client.finished

    def resumeProducing(self):
        self._client.transport.write(self._bytes)
        self._sent += len(self._bytes)
        if self._sent == self._sendAmount:
            self._client.transport.unregisterProducer()

    def stopProducing(self):
        self._client.transport.loseConnection()


@benchmarkWithReactor
async def test_tcp_throughput():
    chunkSize = 16384
    sendAmount = 1024 * 1024

    server = ServerFactory()
    server.protocol = Server
    port = reactor.listenTCP(0, server)
    client = Client(
        reactor, TCP4ClientEndpoint(reactor, '127.0.0.1', port.getHost().port)
    )
    result = await client.run(sendAmount, chunkSize)
    await port.stopListening()
    assert result == sendAmount
