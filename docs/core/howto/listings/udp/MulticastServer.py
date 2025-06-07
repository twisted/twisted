from MulticastCommon import group, interface, ipv6, port

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol


class MulticastPingPong(DatagramProtocol):
    def startProtocol(self):
        """
        Called after protocol has started listening.
        """
        if not ipv6:
            # Set the TTL>1 so multicast will cross router hops:
            self.transport.setTTL(5)
        # Join a specific multicast group:
        self.transport.joinGroup(group)

    def datagramReceived(self, datagram, address):
        print(f"Datagram {repr(datagram)} received from {repr(address)}")
        if datagram == b"Client: Ping" or datagram == "Client: Ping":
            # Rather than replying to the group multicast address, we send the
            # reply directly (unicast) to the originating port:
            self.transport.write(b"Server: Pong", address)


# We use listenMultiple=True so that we can run MulticastServer.py and
# MulticastClient.py on same machine:
reactor.listenMulticast(
    port, MulticastPingPong(), listenMultiple=True, interface=interface
)
reactor.run()
