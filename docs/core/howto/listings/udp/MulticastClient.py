from MulticastCommon import group, interface, port

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol


class MulticastPingClient(DatagramProtocol):
    def startProtocol(self):
        # Join the multicast address, so we can receive replies:
        self.transport.joinGroup(group)
        # Send to our group:port pair - all listeners on the multicast address
        # (including us) will receive this message.
        self.transport.write(b"Client: Ping", (group, port))

    def datagramReceived(self, datagram, address):
        print(f"Datagram {repr(datagram)} received from {repr(address)}")


reactor.listenMulticast(
    port, MulticastPingClient(), listenMultiple=True, interface=interface
)
reactor.run()
