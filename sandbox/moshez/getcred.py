from twisted.internet import protocol, reactor
import socket, struct

class CredChecker(protocol.Protocol):

    def connectionMade(self):
        buf = self.transport.socket.getsockopt(socket.SOL_SOCKET, 17, 4*3)
        pid, uid, gid = struct.unpack('3i', buf)
        print pid, uid, gid
        self.transport.loseConnection()

f = protocol.Factory()
f.protocol = CredChecker
reactor.listenUNIX("lala", f)
reactor.run()
