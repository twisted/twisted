"just twistd -y me"
from twisted.internet import main, udp
import pwd

class PacketPrinter:

    def packetReceived(self, data, addr, port):
        print "received", `data`, "from", `addr`
        port.socket.sendto(data, addr)
        
application = main.Application('udp-echo')
application.addPort(udp.Port(8080, PacketPrinter()))
