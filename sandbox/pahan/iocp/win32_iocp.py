"""
XXX: I AM INCORRECT, BROKEN CODE
A IOCP-based event loop.

This requires win32all to be installed.

TODO:
1. Pass tests.
2. Switch everyone to a decent OS so we don't have to deal with insane APIs.
3. Process support, SSL, UDP.
"""

# Win32 imports
from win32file import WSAEventSelect, FD_READ, FD_WRITE, FD_CLOSE, \
                      FD_ACCEPT, FD_CONNECT
from win32event import CreateEvent, WaitForMultipleObjects, \
                       WAIT_OBJECT_0, WAIT_TIMEOUT, INFINITE
import win32api
import win32con
import win32event
import win32file
import win32pipe
import win32process
import win32security
import pywintypes
import msvcrt

# Twisted imports
from twisted.internet import default, abstract
from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorTCP
from twisted.python import log, threadable
from twisted.protocols import protocol
from twisted.persisted import styles

# System imports
import os
import threading
import Queue
import string
import time
import socket
import sys
import struct

# globals
files = {} # files handled by IOCP


class Win32Reactor(default.PosixReactorBase):
    """Reactor that uses Win32 event APIs.

    Actually, this uses Proactor pattern.
    """
    
    __implements__ = IReactorCore, IReactorTime, IReactorTCP

    def __init__(self, handleSignals=1):
        default.PosixReactorBase.__init__(self, handleSignals)
        self.iocp = win32file.CreateIoCompletionPort(win32file.INVALID_HANDLE_VALUE, None, 0, 1)

    def installWaker(self):
        self.wakeupOverlapped = pywintypes.OVERLAPPED()
    
    def wakeUp(self):
        """Wake up the event loop."""
        if not threadable.isInIOThread():
            win32file.PostQueuedCompletionStatus(self.iocp, 0, 0, self.wakeupOverlapped)

    def removeAll(self):
        return []
    
    def registerFile(self, file, wrapper):
        """Register an object that will be handled by the I/O completion port."""
        print "registering %d for %s" % (int(file), wrapper)
        files[int(file)] = wrapper
        self.iocp = win32file.CreateIoCompletionPort(file, self.iocp, int(file), 1)
    
    def doIteration(self, timeout):
        if timeout is None:
            timeout = 10000
        else:
            timeout = int(1000 * timeout)
        rc, numBytes, key, overlapped = win32file.GetQueuedCompletionStatus(self.iocp, timeout)
        print "GQCS", rc, numBytes, key, overlapped, repr(overlapped.object)
        if key == 0:
            return

        object = files[key]
        #print "about to run method %r on object %r" % (overlapped.object, object)
        action = getattr(object, overlapped.object)
        try:
            action()
        except:
            log.deferr()
            try:
                object.connectionLost()
            except:
                log.deferr()


    # IReactorTCP

    def listenTCP(self, port, factory, backlog=5, interface=''):
        """See twisted.internet.interfaces.IReactorTCP.listenTCP
        """
        p = Port(port, factory, backlog, interface)
        p.startListening()
        return p

    def clientTCP(self, host, port, protocol, timeout=30):
        return Client(host, port, protocol, timeout)


def install():
    threadable.init(1)
    r = Win32Reactor()
    import main
    main.installReactor(r)
    import threadtask
    threadtask.theDispatcher.start()


class Connection(protocol.Transport, styles.Ephemeral):
    """A TCP connection for the Proactor pattern."""

    connected = 0
    producerPaused = 0
    streamingProducer = 0
    unsent = ""
    producer = None
    disconnected = 0
    disconnecting = 0
    bufferSize = 2**2**2**2
    writing = 0
    
    def __init__(self, skt, protocol):
        self.socket = skt
        self.socket.setblocking(0)
        self.protocol = protocol

        # setup win32 objects
        self.winSocket = skt.fileno()
        self.outOverlapped = pywintypes.OVERLAPPED()
        self.outOverlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
        self.inOverlapped = pywintypes.OVERLAPPED()
        self.inOverlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
        self.readData = win32file.AllocateReadBuffer(self.bufferSize)
        from twisted.internet import reactor
        reactor.registerFile(self.winSocket, self)
        self.outOverlapped.object = "finishedWriting"
        self.inOverlapped.object = "doRead"
    
    def registerProducer(self, producer, streaming):
        """Register to receive data from a producer.

        This sets this selectable to be a consumer for a producer.  When this
        selectable runs out of data on a write() call, it will ask the producer
        to resumeProducing(). A producer should implement the IProducer
        interface.

        FileDescriptor provides some infrastructure for producer methods.
        """

        self.producer = producer
        self.streamingProducer = streaming
        if not streaming:
            producer.resumeProducing()

    def unregisterProducer(self):
        """Stop consuming data from a producer, without disconnecting.
        """
        self.producer = None

    def stopConsuming(self):
        """Stop consuming data.

        This is called when a producer has lost its connection, to tell the
        consumer to go lose its connection (and break potential circular
        references).
        """
        self.unregisterProducer()
        self.loseConnection()

    def connectionLost(self):
        """The connection was lost.

        This is called when the connection on a selectable object has been
        lost.  It will be called whether the connection was closed explicitly,
        an exception occurred in an event handler, or the other end of the
        connection closed it first.

        Clean up state here, but make sure to call back up to FileDescriptor.
        """
        #print "closing connection", self
        self.disconnected = 1
        self.connected = 0
        if self.producer is not None:
            self.producer.stopProducing()
            self.producer = None
        try:
            self.socket.shutdown(2)
        except socket.error:
            pass
        protocol = self.protocol
        del self.protocol
        del self.socket
        protocol.connectionLost()

    def write(self, data):
        #print self, "is writing", repr(data)
        self.unsent = self.unsent + data
        if not self.writing:
            self.startWriting()

        if self.producer is not None:
            if len(self.unsent) > self.bufferSize:
                self.producerPaused = 1
                self.producer.pauseProducing()

    def loseConnection(self):
        if self.connected:
            if self.writing:
                self.disconnecting = 1
            else:
                self.connectionLost()

    def startWriting(self):
        #print self, "startWriting"
        self.writing = 1
        size = min(len(self.unsent), self.bufferSize)
        data, self.unsent = self.unsent[:size], self.unsent[size:]
        try:
            win32file.WriteFile(self.winSocket, data, self.outOverlapped)
        except win32api.error:
            self.connectionLost()
            return
    
    def finishedWriting(self):
        #print self, "finishedWriting"
        if self.disconnected:
            return
        if self.unsent:
            self.startWriting()
            return
        else:
            if self.producer is not None and ((not self.streamingProducer)
                                              or self.producerPaused):
                # tell them to supply some more.
                self.writing = 0
                self.producer.resumeProducing()
                self.producerPaused = 0
                return
            elif self.disconnecting:
                # But if I was previously asked to let the connection die, do
                # so.
                self.connectionLost()
                return
            self.writing = 0
    
    def startReading(self):
        #print self, "startReading"
        try:
            result, readData = win32file.ReadFile(self.winSocket, self.readData, self.inOverlapped)
            assert self.readData is readData
        except win32api.error, e:
            #print "win32api error", e
            try:
                length = win32file.GetOverlappedResult(self.winSocket, self.inOverlapped, 0)
                self.protocol.dataReceived(self.readData[:length])
            except win32api.error:
                pass
            return
    
    def doRead(self):
        #print self, "doRead"
        if self.disconnected:
            #print "disconnected, byebye:", self.disconnected
            return
        #print "not disconnected"
        length = win32file.GetOverlappedResult(self.winSocket, self.inOverlapped, 0)
        #print self, "received data of length", length
        if length:
            #print self, "received data", repr(self.readData[:length])
            self.protocol.dataReceived(self.readData[:length])
            self.startReading()
        else:
            self.connectionLost()


# this code is identical to tcp.Connection:

class Server(Connection):
    """Serverside socket-stream connection class.

    I am a serverside network connection transport; a socket which came from an
    accept() on a server.  Programmers for the twisted.net framework should not
    have to use me directly, since I am automatically instantiated in
    TCPServer's doRead method.  For documentation on what I do, refer to the
    documentation for twisted.protocols.protocol.Transport.
    """

    def __init__(self, sock, protocol, client, server, sessionno):
        """Server(sock, protocol, client, server, sessionno)

        Initialize me with a socket, a protocol, a descriptor for my peer (a
        tuple of host, port describing the other end of the connection), an
        instance of Port, and a session number.
        """
        self.repstr = "<%s #%s on %s>" % (protocol.__class__.__name__, sessionno, server.port)
        Connection.__init__(self, sock, protocol)
        self.server = server
        self.client = client
        self.sessionno = sessionno
        self.hostname = client[0]
        self.logstr = "%s,%s,%s" % (self.protocol.__class__.__name__, sessionno, self.hostname)
        self.startReading()
        self.connected = 1

    def __repr__(self):
        """A string representation of this connection.
        """
        return self.repstr

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the servers address.
        """
        return ('INET',)+self.socket.getsockname()

    def getPeer(self):
        """
        Returns a tuple of ('INET', hostname, port), indicating the connected
        client's address.
        """
        return ('INET',)+self.client


class Port:
    """I am a TCP server port, listening for connections.

    When a connection is accepted, I will call my factory's buildProtocol with
    the incoming connection as an argument, according to the specification
    described in twisted.protocols.protocol.Factory.

    If you wish to change the sort of transport that will be used, my
    `transport' attribute will be called with the signature expected for
    Server.__init__, so it can be replaced.
    """

    transport = Server
    sessionno = 0
    interface = ''
    backlog = 5

    def __init__(self, port, factory, backlog=5, interface='', reactor=None):
        """Initialize with a numeric port to listen on.
        """
        self.port = port
        self.factory = factory
        self.backlog = backlog
        self.interface = interface
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor
        self.overlapped = pywintypes.OVERLAPPED()
        self.overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
        self.buffer = win32file.AllocateReadBuffer(64)

    def __repr__(self):
        return "<%s on %s>" % (self.factory.__class__, self.port)

    def createInternetSocket(self):
        """(internal) create an AF_INET socket.
        """
        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        return s

    def __getstate__(self):
        """(internal) get my state for persistence
        """
        dct = copy.copy(self.__dict__)
        try: del dct['socket']
        except: pass
        try: del dct['fileno']
        except: pass
        return dct

    def startListening(self):
        """Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        log.msg("%s starting on %s"%(self.factory.__class__, self.port))
        skt = self.createInternetSocket()
        skt.setblocking(0)
        skt.bind((self.interface, self.port))
        skt.listen(self.backlog)
        self.connected = 1
        self.socket = skt
        winSocket = skt.fileno()
        self.overlapped.object = "doRead"
        self.reactor.registerFile(winSocket, self)
        self.startReading()

    def startReading(self):
        self.newSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.newSocket.setblocking(0)
        win32file.AcceptEx(self.socket, self.newSocket, self.buffer, self.overlapped)
    
    def doRead(self):
        """Called when my socket is ready for reading.

        This accepts a connection and callse self.protocol() to handle the
        wire-level protocol.
        """
        if not self.connected:
            return
        try:
            skt = self.newSocket
            del self.newSocket

            # make new socket inherit properties from the port's socket
            skt.setsockopt(socket.SOL_SOCKET, win32file.SO_UPDATE_ACCEPT_CONTEXT, struct.pack("I", self.socket.fileno()))

            # get new socket's address
            family, localaddr, addr = win32file.GetAcceptExSockaddrs(self.socket, self.buffer)

            # build the new protocol
            protocol = self.factory.buildProtocol(addr)
            if protocol is None:
                skt.close()
            else:
                s = self.sessionno
                self.sessionno = s+1
                transport = self.transport(skt, protocol, addr, self, s)
                protocol.makeConnection(transport, self)
        except:
            log.deferr()
        
        self.startReading()

    def loseConnection(self):
        """ Stop accepting connections on this port.

        This will shut down my socket and call self.connectionLost().
        """
        self.disconnecting = 1
        if self.connected:
            self.reactor.callLater(0, self.connectionLost)

    def connectionLost(self):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % self.port)
        self.disconnected = 1
        self.connected = 0
        self.socket.close()
        del self.socket
        self.factory.stopFactory()

    def logPrefix(self):
        """Returns the name of my class, to prefix log entries with.
        """
        return str(self.factory.__class__)

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the servers address.
        """
        return ('INET',)+self.socket.getsockname()


class Client(Connection):
    """A client for TCP (and similiar) sockets.
    """
    def __init__(self, host, port, protocol, timeout=None, connector=None, reactor=None):
        """Initialize the client, setting up its socket, and request to connect.
        """
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor
        self.socket = self.createInternetSocket()
        self.addr = (host, port)
        self.protocol = protocol
        self.host = host
        self.port = port
        self.connector = connector
        self.logstr = self.protocol.__class__.__name__+",client"
        if timeout is not None:
            self.reactor.callLater(timeout, self.failIfNotConnected)
        self.reactor.callLater(0, self.resolveAddress)

    def failIfNotConnected(self, *ignored):
        # print 'failing if not connected'
        if (not self.connected) and (not self.disconnected):
            if self.connector:
                self.connector.connectionFailed()
            self.protocol.connectionFailed()

    def createInternetSocket(self):
        """(internal) Create an AF_INET socket.
        """
        # factored out so as to minimise the code necessary for SecureClient
        return socket.socket(socket.AF_INET,socket.SOCK_STREAM)

    def resolveAddress(self):
        if abstract.isIPAddress(self.addr[0]):
            self._setRealAddress(self.addr[0])
        else:
            self.reactor.resolve(self.addr[0]
                            ).addCallbacks(
                self._setRealAddress, self.failIfNotConnected
                ).arm()

    def _setRealAddress(self, address):
        # print 'real address:',repr(address),repr(self.addr)
        self.realAddress = (address, self.addr[1])
        import threadtask
        threadtask.theDispatcher.dispatch(log.logOwner.owner(), self._connect)

    def _connect(self):
        """Runs in thread"""
        try:
            self.socket.connect(self.realAddress)
        except socket.error:
            self.reactor.callFromThread(self.failIfNotConnected)
        else:
            self.reactor.callFromThread(self._connected)
    
    def _connected(self):
        """Called when connection succeeded."""
        self.connected = 1
        Connection.__init__(self, self.socket, self.protocol)
        self.protocol.makeConnection(self)
        self.startReading()
    
    def connectionLost(self):
        if not self.connected:
            self.failIfNotConnected()
        else:
            Connection.connectionLost(self)
            if self.connector:
                self.connector.connectionLost()

    def getHost(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the address from which I am connecting.
        """
        return ('INET',)+self.socket.getsockname()

    def getPeer(self):
        """Returns a tuple of ('INET', hostname, port).

        This indicates the address that I am connected to.  I implement
        twisted.protocols.protocol.Transport.
        """
        return ('INET',)+self.addr

    def __repr__(self):
        s = '<%s to %s at %x>' % (self.__class__, self.addr, id(self))
        return s



__all__ = ["Win32Reactor", "install"]

