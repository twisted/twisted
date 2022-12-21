from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol


class MulticastPingClient(DatagramProtocol):
    def startProtocol(self):
        # Join the multicast address, so we can receive replies:
        self.transport.joinGroup("228.0.0.5")
        # Send to 228.0.0.5:9999 - all listeners on the multicast address
        # (including us) will receive this message.
        self.transport.write(b"Client: Ping", ("228.0.0.5", 9999))

    def datagramReceived(self, datagram, address):
        print(f"Datagram {repr(datagram)} received from {repr(address)}")


reactor.listenMulticast(9999, MulticastPingClient(), listenMultiple=True)
reactor.run()
