
import sys
import errno
import struct
import socket

from twisted.python import log
from twisted.python import failure
from twisted.internet import unix
from twisted.application import internet

from sendmsg import sendmsg, recvmsg
from sendmsg import SCM_RIGHTS

class Server(unix.Server):
    def sendFileDescriptors(self, fileno, data="Filler"):
        """
        @param fileno: An iterable of the file descriptors to pass.
        """
        fileno = list(fileno)
        payload = struct.pack("%di" % len(fileno), *fileno)
        r = sendmsg(self.fileno(), data, 0, (socket.SOL_SOCKET, SCM_RIGHTS, payload))
        return r

class Port(unix.Port):
    transport = Server

class UNIXServer(internet._AbstractServer):
    def getHost(self):
        return self._port.getHost()

    def _getPort(self):
        from twisted.internet import reactor
        return reactor.listenWith(Port, *self.args, **self.kwargs)

class Client(unix.Client):
    def doRead(self):
        if not self.connected:
            return
        while True:
            try:
                msg, flags, ancillary = recvmsg(self.fileno())
            except socket.error, e:
                if e[0] == errno.EAGAIN:
                    break
                else:
                    log.msg('recvmsg():')
                    log.err()
            except:
                log.msg('recvmsg():')
                log.err()
            else:
                if ancillary:
                    buf = ancillary[0][2]
                    fds = struct.unpack('%di' % (len(buf) / 4), buf)
                    try:
                        self.protocol.fileDescriptorsReceived(fds)
                    except:
                        log.msg('protocol.fileDescriptorsReceived')
                        log.err()
                else:
                    break
        return unix.Client.doRead(self)

class Connector(unix.Connector):
    def _makeTransport(self):
        return Client(self.address, self, self.reactor)

class UNIXClient(internet._AbstractClient):
    def _getConnection(self):
        from twisted.internet import reactor
        return reactor.connectWith(Connector, *self.args, **self.kwargs)
