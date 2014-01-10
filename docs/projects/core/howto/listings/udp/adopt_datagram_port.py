import socket

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor



class Echo(DatagramProtocol):
    def datagramReceived(self, data, (host, port)):
        print "received %r from %s:%d" % (data, host, port)
        self.transport.write(data, (host, port))



portSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# Make the port non-blocking and start it listening.
portSocket.setblocking(False)
portSocket.bind(('127.0.0.1', 9999))

# Now pass the port file descriptor to the reactor
port = reactor.adoptDatagramPort(
    portSocket.fileno(), socket.AF_INET, Echo())

# The portSocket should be cleaned up by the process that creates it.
portSocket.close()

reactor.run()
