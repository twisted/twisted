from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

class MulticastClientUDP(DatagramProtocol):

    def datagramReceived(self, datagram, address):
            print "Received:" + repr(datagram)

# Send multicast on 224.0.0.1:8005, on our dynamically allocated port
port = reactor.listenUDP(0, MulticastClientUDP())
port.write('UniqueID', ('224.0.0.1', 8005))
reactor.run()
