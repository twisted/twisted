"""
Protocol for passing files between processes.
"""

import os
import sys
import struct
import socket

sys.path.insert(0, "../../pahan/sendmsg")
from sendmsg import sendmsg
from sendmsg import recvmsg
from sendmsg import SCM_RIGHTS

from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet import unix
from twisted.python import log

from twisted.application import internet

class Server(unix.Server):
    def sendFileDescriptors(self, fileno, data="Filler"):
        """
        @param fileno: An iterable of the file descriptors to pass.
        """
        payload = struct.pack("%di" % len(fileno), *fileno)
        r = sendmsg(self.fileno(), data, 0, (socket.SOL_SOCKET, SCM_RIGHTS, payload))
        return r


class Port(unix.Port):
    transport = Server


class Client(unix.Client):
    def doRead(self):
        try:
            msg, flags, ancillary = recvmsg(self.fileno())
        except:
            log.msg('recvmsg():')
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
                log.msg('protocol.fileDescriptorsReceived')
                log.err()
        return unix.Client.doRead(self)
    
class Connector(unix.Connector):
    def _makeTransport(self):
        return Client(self.address, self, self.reactor)

class UNIXServer(internet.UNIXServer):
    def _getPort(self):
        from twisted.internet import reactor
        return reactor.listenWith(Port, *self.args, **self.kwargs)

class UNIXClient(internet.UNIXClient):
    def _getConnection(self):
        from twisted.internet import reactor
        return reactor.connectWith(Connector, *self.args, **self.kwargs)
    
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

def makeServer(service):
    if os.path.exists('fd_control'):
        raise Exception("Server already listening")
    f = protocol.ServerFactory()
    f.protocol = FileDescriptorSendingProtocol
    s = UNIXServer('fd_control', f)
    s.setServiceParent(service)
    return s

def makeClient(service):
    from twisted.internet import reactor
    f = protocol.ClientFactory()
    f.protocol = FileDescriptorReceivingProtocol
    f.rDeferred = defer.Deferred().addCallback(lambda _: reactor.stop())
    c = UNIXClient('fd_control', f, 60, reactor=reactor)
    c.setServiceParent(service)
    return c

def main():
    import sys
    from twisted.application import service
    
    a = service.Application("File Descriptor Passing Application")
    try:
        makeServer(a)
    except:
        makeClient(a)
    return a

application = main()
