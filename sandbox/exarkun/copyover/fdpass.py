# -*- coding: Latin-1 -*-

"""
Protocol for passing files between processes.
"""

import os
import sys
import struct
import socket

sys.path.insert(0, "../../pahan/sendmsg")
from sendmsg import sendmsg
from eunuchs.recvmsg import recvmsg

from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet import unix
from twisted.python import log

SCM_RIGHTS = 0x01

class Server(unix.Server):
    def sendFileDescriptors(self, fileno, data="Filler"):
        """
        @param fileno: An iterable of the file descriptors to pass.
        """
        payload = struct.pack("%di" % len(fileno), *fileno)
        r = sendmsg(self.fileno(), data, 0, (socket.SOL_SOCKET, SCM_RIGHTS, payload))
        print 'Sent', fileno, '(', r, ')'
        return r


class Port(unix.Port):
    transport = Server


class Client(unix.Client):
    def doRead(self):
        try:
            msg, addr, _, ancillary = recvmsg(self.fileno())
        except:
            log.err()
        else:
            buf = ancillary[0][2]
            fds = []
            while buf:
                fd, buf = buf[:4], buf[4:]
                fds.append(struct.unpack("i", fd)[0])
            try:
                self.protocol.fileDescriptorsReceived(fds)
            except:
                log.err()
        return unix.Client.doRead(self)

class Connector(unix.Connector):
    def _makeTransport(self):
        return Client(self.address, self, self.reactor)

class FileDescriptorSendingProtocol(protocol.Protocol):
    """
    Must be used with L{Port} as the transport.
    """

    def connectionMade(self):
        files = [file(x) for x in os.listdir('.') if os.path.isfile(x)]
        self.transport.sendFileDescriptors([f.fileno() for f in files])

class FileDescriptorReceivingProtocol(protocol.Protocol):
    """
    Must be used with L{Port} as the transport.
    """

    def dataReceived(self, data):
        print 'Got some random data', repr(data)

    def fileDescriptorsReceived(self, fds):
        print 'Now I own', fds
        print 'I am going to read them:'
        for f in fds:
            f = os.fdopen(f, 'r')
            print repr(f.read(80))
        self.factory.rDeferred.callback(self)

def main():
    log.startLogging(sys.stdout)

    from twisted.internet import reactor
    f = protocol.ServerFactory()
    f.protocol = FileDescriptorSendingProtocol
    s = reactor.listenWith(Port, 'fd_control', f)
    
    f = protocol.ClientFactory()
    f.protocol = FileDescriptorReceivingProtocol
    f.rDeferred = defer.Deferred().addCallback(lambda _: reactor.stop())
    c = reactor.connectWith(Connector, 'fd_control', f, 60, reactor=reactor)

    reactor.run()

if __name__ == '__main__':
    main()
