from sets import Set
import socket

from twisted.internet import interfaces, error
from twisted.persisted import styles
from twisted.python import log, reflect

from ops import AcceptExOp
from abstract import ConnectedSocket
import address

class ServerSocket(ConnectedSocket):
    def __init__(self, sock, protocol, sf, sessionno):
        ConnectedSocket.__init__(self, sock, protocol, sf)
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno,
                address.getHost(self.sf.addr, self.sf.sockinfo))
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__, sessionno, 
                address.getPort(self.sf.addr, self.sf.sockinfo))
        self.startReading()

class ListeningPort(log.Logger, styles.Ephemeral):
    __implements__ = interfaces.IListeningPort,
    events = ["startListening", "stopListening", "acceptDone", "acceptErr"]
    sockinfo = None
    transport = ServerSocket
    sessionno = 0

    def __init__(self, addr, factory, backlog):
        self.state = "disconnected"
        self.addr = addr
        self.factory = factory
        self.backlog = backlog
        self.accept_op = AcceptExOp(self)

    def __repr__(self):
        return "<%s on %s>" % (self.factory.__class__, address.getPort(self.addr, self.sockinfo))

    def handle_disconnected_startListening(self):
        log.msg("%s starting on %s" % (self.factory.__class__, address.getPort(self.addr, self.sockinfo)))
        try:
            skt = socket.socket(*self.sockinfo)
            skt.bind(self.addr)
        except socket.error, le:
            raise error.CannotListenError, (address.getHost(self.addr, self.sockinfo), address.getPort(self.addr, self.sockinfo), le)
        self.factory.doStart()
        skt.listen(self.backlog)
        self.socket = skt
        self.state = "listening"
        self.startAccepting()

    def startAccepting(self):
        self.accept_op.initiateOp(self.socket.fileno())

    def handle_listening_acceptDone(self, sock, addr):
        protocol = self.factory.buildProtocol(addr)
        if protocol is None:
            sock.close()
        else:
            s = self.sessionno
            self.sessionno = s+1
            transport = self.transport(sock, protocol, self, s)
            protocol.makeConnection(transport)
        self.startAccepting()

    def handle_disconnected_acceptDone(self, sock, addr):
        sock.close()

    def handle_listening_acceptErr(self, ret, bytes):
        self.stopListening()

    def handle_disconnected_acceptErr(self, ret, bytes):
        pass

    def handle_listening_stopListening(self):
        self.state = "disconnected"
        self.socket.close()
        log.msg('(Port %r Closed)' % address.getPort(self.addr, self.sockinfo))
        self.factory.doStop()

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)

    def getHost(self):
        return address.getFull(self.socket.getsockname(), self.sockinfo)

    def getPeer(self):
        return address.getFull(self.socket.getpeername(), self.sockinfo)

def makeHandleGetter(name):
    def helpful(self):
        return getattr(self, "handle_%s_%s" % (self.state, name))
    return helpful

# urf this should be done with a metaclass! Or something!
for i in ListeningPort.events:
    setattr(ListeningPort, i, property(makeHandleGetter(i)))

