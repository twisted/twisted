# Twisted, the Framework of Your Internet
# Copyright (C) 2004 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from sets import Set
import socket

from twisted.internet import interfaces, address
from twisted.persisted import styles
from twisted.python import log, reflect

from ops import AcceptExOp
from abstract import ConnectedSocket
from util import StateEventMachineType
import error
from zope.interface import implements

class ServerSocket(ConnectedSocket):
    def __init__(self, sock, protocol, sf, sessionno):
        ConnectedSocket.__init__(self, sock, protocol, sf)
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno, self.getPeerHost())
        self.repstr = "<%s #%s on %s>" % (self.protocol.__class__.__name__, sessionno, self.getPeerPort())
        self.startReading()

class ListeningPort(log.Logger, styles.Ephemeral, object):
    __metaclass__ = StateEventMachineType
    implements(interfaces.IListeningPort)
    events = ["startListening", "stopListening", "loseConnection", "acceptDone", "acceptErr"]
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
        return "<%s on %s>" % (self.factory.__class__, self.getOwnPort())

    def handle_disconnected_startListening(self):
        log.msg("%s starting on %s" % (self.factory.__class__, self.getOwnPort()))
        try:
            skt = socket.socket(*self.sockinfo)
            skt.bind(self.addr)
        except socket.error, le:
            raise error.CannotListenError, (None, None, le)
        self.factory.doStart()
        skt.listen(self.backlog)
        self.socket = skt
        self.state = "listening"
        self.startAccepting()

    def startAccepting(self):
        self.accept_op.initiateOp(self.socket.fileno())

    def handle_listening_acceptDone(self, sock, addr):
        protocol = self.factory.buildProtocol(self.buildAddress(addr))
        if protocol is None:
            sock.close()
        else:
            s = self.sessionno
            self.sessionno = s+1
            transport = self.transport(sock, protocol, self, s)
            protocol.makeConnection(transport)
        if self.state == "listening":
            self.startAccepting()

    def handle_disconnected_acceptDone(self, sock, addr):
        sock.close()

    def handle_listening_acceptErr(self, ret, bytes):
#        print "ono acceptErr", ret, bytes
        self.stopListening()

    def handle_disconnected_acceptErr(self, ret, bytes):
#        print "ono acceptErr", ret, bytes
        pass

    def handle_listening_stopListening(self):
        self.state = "disconnected"
        self.socket.close()
        log.msg('(Port %s Closed)' % (self.getOwnPort(),))
        self.factory.doStop()

    handle_listening_loseConnection = handle_listening_stopListening

    def handle_disconnected_stopListening(self):
        raise error.NotListeningError

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return reflect.qual(self.factory.__class__)
 
    def connectionLost(self, reason):
        pass

    # stupid workaround for test_tcp.LoopbackTestCase.testClosePortInProtocolFactory
    disconnected = property(lambda self: self.state == "disconnected")

