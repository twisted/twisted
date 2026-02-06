from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol


class Echo(DatagramProtocol):
    def datagramReceived(self, data, addr):
        print(f"received {data!r} from {addr}")
        self.transport.write(data, addr)


reactor.listenUDP(9999, Echo())
reactor.run()
