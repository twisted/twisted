# -*- test-case-name: twisted.test.test_unix,twisted.internet.test.test_unix,twisted.internet.test.test_posixbase -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Various asynchronous TCP/IP classes.

End users shouldn't use this module directly - use the reactor APIs instead.

Maintainer: Itamar Shtull-Trauring
"""

# System imports
import os, sys, stat, socket
from errno import EINTR, EMSGSIZE, EAGAIN, EWOULDBLOCK, ECONNREFUSED

from zope.interface import implements, implementsOnly, implementedBy

if not hasattr(socket, 'AF_UNIX'):
    raise ImportError("UNIX sockets not supported on this platform")

# Twisted imports
from twisted.internet import base, tcp, udp, error, interfaces, protocol, address
from twisted.internet.error import CannotListenError
from twisted.python import lockfile, log, reflect, failure


class Server(tcp.Server):
    def __init__(self, sock, protocol, client, server, sessionno, reactor):
        tcp.Server.__init__(self, sock, protocol, (client, None), server, sessionno, reactor)

    def getHost(self):
        return address.UNIXAddress(self.socket.getsockname())

    def getPeer(self):
        return address.UNIXAddress(self.hostname)



def _inFilesystemNamespace(path):
    """
    Determine whether the given unix socket path is in a filesystem namespace.

    While most PF_UNIX sockets are entries in the filesystem, Linux 2.2 and
    above support PF_UNIX sockets in an "abstract namespace" that does not
    correspond to any path. This function returns C{True} if the given socket
    path is stored in the filesystem and C{False} if the path is in this
    abstract namespace.
    """
    return path[:1] != "\0"


class _UNIXPort(object):
    def getHost(self):
        """Returns a UNIXAddress.

        This indicates the server's address.
        """
        if sys.version_info > (2, 5) or _inFilesystemNamespace(self.port):
            path = self.socket.getsockname()
        else:
            # Abstract namespace sockets aren't well supported on Python 2.4.
            # getsockname() always returns ''.
            path = self.port
        return address.UNIXAddress(path)



class Port(_UNIXPort, tcp.Port):
    addressFamily = socket.AF_UNIX
    socketType = socket.SOCK_STREAM

    transport = Server
    lockFile = None

    def __init__(self, fileName, factory, backlog=50, mode=0666, reactor=None, wantPID = 0):
        tcp.Port.__init__(self, fileName, factory, backlog, reactor=reactor)
        self.mode = mode
        self.wantPID = wantPID

    def __repr__(self):
        factoryName = reflect.qual(self.factory.__class__)
        if hasattr(self, 'socket'):
            return '<%s on %r>' % (factoryName, self.port)
        else:
            return '<%s (not listening)>' % (factoryName,)

    def _buildAddr(self, name):
        return address.UNIXAddress(name)

    def startListening(self):
        """
        Create and bind my socket, and begin listening on it.

        This is called on unserialization, and must be called after creating a
        server to begin listening on the specified port.
        """
        log.msg("%s starting on %r" % (
                self._getLogPrefix(self.factory), self.port))
        if self.wantPID:
            self.lockFile = lockfile.FilesystemLock(self.port + ".lock")
            if not self.lockFile.lock():
                raise CannotListenError, (None, self.port, "Cannot acquire lock")
            else:
                if not self.lockFile.clean:
                    try:
                        # This is a best-attempt at cleaning up
                        # left-over unix sockets on the filesystem.
                        # If it fails, there's not much else we can
                        # do.  The bind() below will fail with an
                        # exception that actually propagates.
                        if stat.S_ISSOCK(os.stat(self.port).st_mode):
                            os.remove(self.port)
                    except:
                        pass

        self.factory.doStart()
        try:
            skt = self.createInternetSocket()
            skt.bind(self.port)
        except socket.error, le:
            raise CannotListenError, (None, self.port, le)
        else:
            if _inFilesystemNamespace(self.port):
                # Make the socket readable and writable to the world.
                os.chmod(self.port, self.mode)
            skt.listen(self.backlog)
            self.connected = True
            self.socket = skt
            self.fileno = self.socket.fileno
            self.numberAccepts = 100
            self.startReading()


    def _logConnectionLostMsg(self):
        """
        Log message for closing socket
        """
        log.msg('(UNIX Port %s Closed)' % (repr(self.port),))


    def connectionLost(self, reason):
        if _inFilesystemNamespace(self.port):
            os.unlink(self.port)
        if self.lockFile is not None:
            self.lockFile.unlock()
        tcp.Port.connectionLost(self, reason)



class Client(tcp.BaseClient):
    """A client for Unix sockets."""
    addressFamily = socket.AF_UNIX
    socketType = socket.SOCK_STREAM

    def __init__(self, filename, connector, reactor=None, checkPID = 0):
        self.connector = connector
        self.realAddress = self.addr = filename
        if checkPID and not lockfile.isLocked(filename + ".lock"):
            self._finishInit(None, None, error.BadFileError(filename), reactor)
        self._finishInit(self.doConnect, self.createInternetSocket(),
                         None, reactor)

    def getPeer(self):
        return address.UNIXAddress(self.addr)

    def getHost(self):
        return address.UNIXAddress(None)


class Connector(base.BaseConnector):
    def __init__(self, address, factory, timeout, reactor, checkPID):
        base.BaseConnector.__init__(self, factory, timeout, reactor)
        self.address = address
        self.checkPID = checkPID

    def _makeTransport(self):
        return Client(self.address, self, self.reactor, self.checkPID)

    def getDestination(self):
        return address.UNIXAddress(self.address)


class DatagramPort(_UNIXPort, udp.Port):
    """Datagram UNIX port, listening for packets."""

    implements(interfaces.IUNIXDatagramTransport)

    addressFamily = socket.AF_UNIX

    def __init__(self, addr, proto, maxPacketSize=8192, mode=0666, reactor=None):
        """Initialize with address to listen on.
        """
        udp.Port.__init__(self, addr, proto, maxPacketSize=maxPacketSize, reactor=reactor)
        self.mode = mode


    def __repr__(self):
        protocolName = reflect.qual(self.protocol.__class__,)
        if hasattr(self, 'socket'):
            return '<%s on %r>' % (protocolName, self.port)
        else:
            return '<%s (not listening)>' % (protocolName,)


    def _bindSocket(self):
        log.msg("%s starting on %s"%(self.protocol.__class__, repr(self.port)))
        try:
            skt = self.createInternetSocket() # XXX: haha misnamed method
            if self.port:
                skt.bind(self.port)
        except socket.error, le:
            raise error.CannotListenError, (None, self.port, le)
        if self.port and _inFilesystemNamespace(self.port):
            # Make the socket readable and writable to the world.
            os.chmod(self.port, self.mode)
        self.connected = 1
        self.socket = skt
        self.fileno = self.socket.fileno

    def write(self, datagram, address):
        """Write a datagram."""
        try:
            return self.socket.sendto(datagram, address)
        except socket.error, se:
            no = se.args[0]
            if no == EINTR:
                return self.write(datagram, address)
            elif no == EMSGSIZE:
                raise error.MessageLengthError, "message too long"
            elif no == EAGAIN:
                # oh, well, drop the data. The only difference from UDP
                # is that UDP won't ever notice.
                # TODO: add TCP-like buffering
                pass
            else:
                raise

    def connectionLost(self, reason=None):
        """Cleans up my socket.
        """
        log.msg('(Port %s Closed)' % repr(self.port))
        base.BasePort.connectionLost(self, reason)
        if hasattr(self, "protocol"):
            # we won't have attribute in ConnectedPort, in cases
            # where there was an error in connection process
            self.protocol.doStop()
        self.connected = 0
        self.socket.close()
        del self.socket
        del self.fileno
        if hasattr(self, "d"):
            self.d.callback(None)
            del self.d

    def setLogStr(self):
        self.logstr = reflect.qual(self.protocol.__class__) + " (UDP)"



class ConnectedDatagramPort(DatagramPort):
    """
    A connected datagram UNIX socket.
    """

    implementsOnly(interfaces.IUNIXDatagramConnectedTransport,
                   *(implementedBy(base.BasePort)))

    def __init__(self, addr, proto, maxPacketSize=8192, mode=0666,
                 bindAddress=None, reactor=None):
        assert isinstance(proto, protocol.ConnectedDatagramProtocol)
        DatagramPort.__init__(self, bindAddress, proto, maxPacketSize, mode,
                              reactor)
        self.remoteaddr = addr


    def startListening(self):
        try:
            self._bindSocket()
            self.socket.connect(self.remoteaddr)
            self._connectToProtocol()
        except:
            self.connectionFailed(failure.Failure())


    def connectionFailed(self, reason):
        """
        Called when a connection fails. Stop listening on the socket.

        @type reason: L{Failure}
        @param reason: Why the connection failed.
        """
        self.stopListening()
        self.protocol.connectionFailed(reason)
        del self.protocol


    def doRead(self):
        """
        Called when my socket is ready for reading.
        """
        read = 0
        while read < self.maxThroughput:
            try:
                data, addr = self.socket.recvfrom(self.maxPacketSize)
                read += len(data)
                self.protocol.datagramReceived(data)
            except socket.error, se:
                no = se.args[0]
                if no in (EAGAIN, EINTR, EWOULDBLOCK):
                    return
                if no == ECONNREFUSED:
                    self.protocol.connectionRefused()
                else:
                    raise
            except:
                log.deferr()


    def write(self, data):
        """
        Write a datagram.
        """
        try:
            return self.socket.send(data)
        except socket.error, se:
            no = se.args[0]
            if no == EINTR:
                return self.write(data)
            elif no == EMSGSIZE:
                raise error.MessageLengthError, "message too long"
            elif no == ECONNREFUSED:
                self.protocol.connectionRefused()
            elif no == EAGAIN:
                # oh, well, drop the data. The only difference from UDP
                # is that UDP won't ever notice.
                # TODO: add TCP-like buffering
                pass
            else:
                raise


    def getPeer(self):
        return address.UNIXAddress(self.remoteaddr)
