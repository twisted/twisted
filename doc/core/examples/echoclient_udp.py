#!/usr/bin/python
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet.protocol import ConnectedDatagramProtocol
from twisted.internet import reactor

class ConnectedEchoClientDatagramProtocol(ConnectedDatagramProtocol):
    strings = [
        "Hello, world!",
        "What a fine day it is.",
        "Bye-bye!"
    ]
    
    def startProtocol(self):
        self.sendDatagram()
    
    def sendDatagram(self):
        if len(self.strings):
            datagram = self.strings.pop(0)
            self.transport.write(datagram)
        else:
            reactor.stop()

    def datagramReceived(self, datagram):
        print 'Datagram received: ', repr(datagram)
        self.sendDatagram()

def main():
    protocol = ConnectedEchoClientDatagramProtocol()
    reactor.connectUDP('localhost', 8000, protocol)
    reactor.run()

if __name__ == '__main__':
    main()
