
from twisted.internet import protocol

import unix
import pbold
import jelliers

class FileDescriptorReceiver(protocol.Protocol):
    def __init__(self):
        self.fds = []

    def fileDescriptorsReceived(self, fds):
        self.fds.extend(fds)

    def __str__(self):
        return '<FileDescriptorReceiver (received %r)>' % (self.fds,)

class ClientFactory(protocol.ClientFactory):
    protocol = FileDescriptorReceiver

    def __init__(self, d):
        self.onConnect = d

    def buildProtocol(self, addr):
        p = protocol.ClientFactory.buildProtocol(self, addr)
        self.onConnect.callback(p)
        return p
