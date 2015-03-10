# -*- test-case-name: twisted.test.test_stringtransport -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Assorted functionality which is commonly useful when writing unit tests.
"""

from __future__ import division, absolute_import

from socket import AF_INET, AF_INET6
from io import BytesIO

from zope.interface import implementer, implementedBy
from zope.interface.verify import verifyClass

from twisted.python import failure
from twisted.python.compat import unicode
from twisted.internet.interfaces import (
    ITransport, IConsumer, IPushProducer, IConnector, IReactorTCP, IReactorSSL,
    IReactorUNIX, IReactorSocket, IListeningPort, IReactorFDSet
)
from twisted.internet.abstract import isIPv6Address
from twisted.internet.error import UnsupportedAddressFamily
from twisted.protocols import basic
from twisted.internet import protocol, error, address

from twisted.internet.task import Clock
from twisted.internet.address import IPv4Address, UNIXAddress, IPv6Address


class AccumulatingProtocol(protocol.Protocol):
    """
    L{AccumulatingProtocol} is an L{IProtocol} implementation which collects
    the data delivered to it and can fire a Deferred when it is connected or
    disconnected.

    @ivar made: A flag indicating whether C{connectionMade} has been called.
    @ivar data: Bytes giving all the data passed to C{dataReceived}.
    @ivar closed: A flag indicated whether C{connectionLost} has been called.
    @ivar closedReason: The value of the I{reason} parameter passed to
        C{connectionLost}.
    @ivar closedDeferred: If set to a L{Deferred}, this will be fired when
        C{connectionLost} is called.
    """
    made = closed = 0
    closedReason = None

    closedDeferred = None

    data = b""

    factory = None

    def connectionMade(self):
        self.made = 1
        if (self.factory is not None and
            self.factory.protocolConnectionMade is not None):
            d = self.factory.protocolConnectionMade
            self.factory.protocolConnectionMade = None
            d.callback(self)

    def dataReceived(self, data):
        self.data += data

    def connectionLost(self, reason):
        self.closed = 1
        self.closedReason = reason
        if self.closedDeferred is not None:
            d, self.closedDeferred = self.closedDeferred, None
            d.callback(None)


class LineSendingProtocol(basic.LineReceiver):
    lostConn = False

    def __init__(self, lines, start = True):
        self.lines = lines[:]
        self.response = []
        self.start = start

    def connectionMade(self):
        if self.start:
            for line in self.lines:
                self.sendLine(line)

    def lineReceived(self, line):
        if not self.start:
            for line in self.lines:
                self.sendLine(line)
            self.lines = []
        self.response.append(line)

    def connectionLost(self, reason):
        self.lostConn = True


class FakeDatagramTransport:
    noAddr = object()

    def __init__(self):
        self.written = []

    def write(self, packet, addr=noAddr):
        self.written.append((packet, addr))



@implementer(ITransport, IConsumer, IPushProducer)
class StringTransport:
    """
    A transport implementation which buffers data in memory and keeps track of
    its other state without providing any behavior.

    L{StringTransport} has a number of attributes which are not part of any of
    the interfaces it claims to implement.  These attributes are provided for
    testing purposes.  Implementation code should not use any of these
    attributes; they are not provided by other transports.

    @ivar disconnecting: A C{bool} which is C{False} until L{loseConnection} is
        called, then C{True}.

    @ivar producer: If a producer is currently registered, C{producer} is a
        reference to it.  Otherwise, C{None}.

    @ivar streaming: If a producer is currently registered, C{streaming} refers
        to the value of the second parameter passed to C{registerProducer}.

    @ivar hostAddr: C{None} or an object which will be returned as the host
        address of this transport.  If C{None}, a nasty tuple will be returned
        instead.

    @ivar peerAddr: C{None} or an object which will be returned as the peer
        address of this transport.  If C{None}, a nasty tuple will be returned
        instead.

    @ivar producerState: The state of this L{StringTransport} in its capacity
        as an L{IPushProducer}.  One of C{'producing'}, C{'paused'}, or
        C{'stopped'}.

    @ivar io: A L{BytesIO} which holds the data which has been written to this
        transport since the last call to L{clear}.  Use L{value} instead of
        accessing this directly.
    """

    disconnecting = False

    producer = None
    streaming = None

    hostAddr = None
    peerAddr = None

    producerState = 'producing'

    def __init__(self, hostAddress=None, peerAddress=None):
        self.clear()
        if hostAddress is not None:
            self.hostAddr = hostAddress
        if peerAddress is not None:
            self.peerAddr = peerAddress
        self.connected = True

    def clear(self):
        """
        Discard all data written to this transport so far.

        This is not a transport method.  It is intended for tests.  Do not use
        it in implementation code.
        """
        self.io = BytesIO()


    def value(self):
        """
        Retrieve all data which has been buffered by this transport.

        This is not a transport method.  It is intended for tests.  Do not use
        it in implementation code.

        @return: A C{bytes} giving all data written to this transport since the
            last call to L{clear}.
        @rtype: C{bytes}
        """
        return self.io.getvalue()


    # ITransport
    def write(self, data):
        if isinstance(data, unicode): # no, really, I mean it
            raise TypeError("Data must not be unicode")
        self.io.write(data)


    def writeSequence(self, data):
        self.io.write(b''.join(data))


    def loseConnection(self):
        """
        Close the connection. Does nothing besides toggle the C{disconnecting}
        instance variable to C{True}.
        """
        self.disconnecting = True


    def getPeer(self):
        if self.peerAddr is None:
            return address.IPv4Address('TCP', '192.168.1.1', 54321)
        return self.peerAddr


    def getHost(self):
        if self.hostAddr is None:
            return address.IPv4Address('TCP', '10.0.0.1', 12345)
        return self.hostAddr


    # IConsumer
    def registerProducer(self, producer, streaming):
        if self.producer is not None:
            raise RuntimeError("Cannot register two producers")
        self.producer = producer
        self.streaming = streaming


    def unregisterProducer(self):
        if self.producer is None:
            raise RuntimeError(
                "Cannot unregister a producer unless one is registered")
        self.producer = None
        self.streaming = None


    # IPushProducer
    def _checkState(self):
        if self.disconnecting:
            raise RuntimeError(
                "Cannot resume producing after loseConnection")
        if self.producerState == 'stopped':
            raise RuntimeError("Cannot resume a stopped producer")


    def pauseProducing(self):
        self._checkState()
        self.producerState = 'paused'


    def stopProducing(self):
        self.producerState = 'stopped'


    def resumeProducing(self):
        self._checkState()
        self.producerState = 'producing'



class StringTransportWithDisconnection(StringTransport):
    """
    A L{StringTransport} which can be disconnected.
    """

    def loseConnection(self):
        if self.connected:
            self.connected = False
            self.protocol.connectionLost(
                failure.Failure(error.ConnectionDone("Bye.")))



class StringIOWithoutClosing(BytesIO):
    """
    A BytesIO that can't be closed.
    """
    def close(self):
        """
        Do nothing.
        """



@implementer(IListeningPort)
class _FakePort(object):
    """
    A fake L{IListeningPort} to be used in tests.

    @ivar _hostAddress: The L{IAddress} this L{IListeningPort} is pretending
        to be listening on.
    """

    def __init__(self, hostAddress):
        """
        @param hostAddress: An L{IAddress} this L{IListeningPort} should
            pretend to be listening on.
        """
        self._hostAddress = hostAddress


    def startListening(self):
        """
        Fake L{IListeningPort.startListening} that doesn't do anything.
        """


    def stopListening(self):
        """
        Fake L{IListeningPort.stopListening} that doesn't do anything.
        """


    def getHost(self):
        """
        Fake L{IListeningPort.getHost} that returns our L{IAddress}.
        """
        return self._hostAddress



@implementer(IConnector)
class _FakeConnector(object):
    """
    A fake L{IConnector} that allows us to inspect if it has been told to stop
    connecting.

    @ivar stoppedConnecting: has this connector's
        L{FakeConnector.stopConnecting} method been invoked yet?

    @ivar _address: An L{IAddress} provider that represents our destination.
    """
    _disconnected = False
    stoppedConnecting = False

    def __init__(self, address):
        """
        @param address: An L{IAddress} provider that represents this
            connector's destination.
        """
        self._address = address


    def stopConnecting(self):
        """
        Implement L{IConnector.stopConnecting} and set
        L{FakeConnector.stoppedConnecting} to C{True}
        """
        self.stoppedConnecting = True


    def disconnect(self):
        """
        Implement L{IConnector.disconnect} as a no-op.
        """
        self._disconnected = True


    def connect(self):
        """
        Implement L{IConnector.connect} as a no-op.
        """


    def getDestination(self):
        """
        Implement L{IConnector.getDestination} to return the C{address} passed
        to C{__init__}.
        """
        return self._address



@implementer(
    IReactorTCP, IReactorSSL, IReactorUNIX, IReactorSocket, IReactorFDSet
)
class MemoryReactor(object):
    """
    A fake reactor to be used in tests.  This reactor doesn't actually do
    much that's useful yet.  It accepts TCP connection setup attempts, but
    they will never succeed.

    @ivar tcpClients: a list that keeps track of connection attempts (ie, calls
        to C{connectTCP}).
    @type tcpClients: C{list}

    @ivar tcpServers: a list that keeps track of server listen attempts (ie, calls
        to C{listenTCP}).
    @type tcpServers: C{list}

    @ivar sslClients: a list that keeps track of connection attempts (ie,
        calls to C{connectSSL}).
    @type sslClients: C{list}

    @ivar sslServers: a list that keeps track of server listen attempts (ie,
        calls to C{listenSSL}).
    @type sslServers: C{list}

    @ivar unixClients: a list that keeps track of connection attempts (ie,
        calls to C{connectUNIX}).
    @type unixClients: C{list}

    @ivar unixServers: a list that keeps track of server listen attempts (ie,
        calls to C{listenUNIX}).
    @type unixServers: C{list}

    @ivar adoptedPorts: a list that keeps track of server listen attempts (ie,
        calls to C{adoptStreamPort}).

    @ivar adoptedStreamConnections: a list that keeps track of stream-oriented
        connections added using C{adoptStreamConnection}.
    """

    def __init__(self):
        """
        Initialize the tracking lists.
        """
        self.tcpClients = []
        self.tcpServers = []
        self.sslClients = []
        self.sslServers = []
        self.unixClients = []
        self.unixServers = []
        self.adoptedPorts = []
        self.adoptedStreamConnections = []
        self.connectors = []

        self.readers = set()
        self.writers = set()


    def adoptStreamPort(self, fileno, addressFamily, factory):
        """
        Fake L{IReactorSocket.adoptStreamPort}, that logs the call and returns
        an L{IListeningPort}.
        """
        if addressFamily == AF_INET:
            addr = IPv4Address('TCP', '0.0.0.0', 1234)
        elif addressFamily == AF_INET6:
            addr = IPv6Address('TCP', '::', 1234)
        else:
            raise UnsupportedAddressFamily()

        self.adoptedPorts.append((fileno, addressFamily, factory))
        return _FakePort(addr)


    def adoptStreamConnection(self, fileDescriptor, addressFamily, factory):
        """
        Record the given stream connection in C{adoptedStreamConnections}.

        @see: L{twisted.internet.interfaces.IReactorSocket.adoptStreamConnection}
        """
        self.adoptedStreamConnections.append((
                fileDescriptor, addressFamily, factory))


    def adoptDatagramPort(self, fileno, addressFamily, protocol,
                          maxPacketSize=8192):
        """
        Fake L{IReactorSocket.adoptDatagramPort}, that logs the call and returns
        a fake L{IListeningPort}.

        @see: L{twisted.internet.interfaces.IReactorSocket.adoptDatagramPort}
        """
        if addressFamily == AF_INET:
            addr = IPv4Address('UDP', '0.0.0.0', 1234)
        elif addressFamily == AF_INET6:
            addr = IPv6Address('UDP', '::', 1234)
        else:
            raise UnsupportedAddressFamily()

        self.adoptedPorts.append(
            (fileno, addressFamily, protocol, maxPacketSize))
        return _FakePort(addr)


    def listenTCP(self, port, factory, backlog=50, interface=''):
        """
        Fake L{reactor.listenTCP}, that logs the call and returns an
        L{IListeningPort}.
        """
        self.tcpServers.append((port, factory, backlog, interface))
        if isIPv6Address(interface):
            address = IPv6Address('TCP', interface, port)
        else:
            address = IPv4Address('TCP', '0.0.0.0', port)
        return _FakePort(address)


    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """
        Fake L{reactor.connectTCP}, that logs the call and returns an
        L{IConnector}.
        """
        self.tcpClients.append((host, port, factory, timeout, bindAddress))
        if isIPv6Address(host):
            conn = _FakeConnector(IPv6Address('TCP', host, port))
        else:
            conn = _FakeConnector(IPv4Address('TCP', host, port))
        factory.startedConnecting(conn)
        self.connectors.append(conn)
        return conn


    def listenSSL(self, port, factory, contextFactory,
                  backlog=50, interface=''):
        """
        Fake L{reactor.listenSSL}, that logs the call and returns an
        L{IListeningPort}.
        """
        self.sslServers.append((port, factory, contextFactory,
                                backlog, interface))
        return _FakePort(IPv4Address('TCP', '0.0.0.0', port))


    def connectSSL(self, host, port, factory, contextFactory,
                   timeout=30, bindAddress=None):
        """
        Fake L{reactor.connectSSL}, that logs the call and returns an
        L{IConnector}.
        """
        self.sslClients.append((host, port, factory, contextFactory,
                                timeout, bindAddress))
        conn = _FakeConnector(IPv4Address('TCP', host, port))
        factory.startedConnecting(conn)
        self.connectors.append(conn)
        return conn


    def listenUNIX(self, address, factory,
                   backlog=50, mode=0o666, wantPID=0):
        """
        Fake L{reactor.listenUNIX}, that logs the call and returns an
        L{IListeningPort}.
        """
        self.unixServers.append((address, factory, backlog, mode, wantPID))
        return _FakePort(UNIXAddress(address))


    def connectUNIX(self, address, factory, timeout=30, checkPID=0):
        """
        Fake L{reactor.connectUNIX}, that logs the call and returns an
        L{IConnector}.
        """
        self.unixClients.append((address, factory, timeout, checkPID))
        conn = _FakeConnector(UNIXAddress(address))
        factory.startedConnecting(conn)
        self.connectors.append(conn)
        return conn


    def addReader(self, reader):
        """
        Fake L{IReactorFDSet.addReader} which adds the reader to a local set.
        """
        self.readers.add(reader)


    def removeReader(self, reader):
        """
        Fake L{IReactorFDSet.removeReader} which removes the reader from a
        local set.
        """
        self.readers.discard(reader)


    def addWriter(self, writer):
        """
        Fake L{IReactorFDSet.addWriter} which adds the writer to a local set.
        """
        self.writers.add(writer)


    def removeWriter(self, writer):
        """
        Fake L{IReactorFDSet.removeWriter} which removes the writer from a
        local set.
        """
        self.writers.discard(writer)


    def getReaders(self):
        """
        Fake L{IReactorFDSet.getReaders} which returns a list of readers from
        the local set.
        """
        return list(self.readers)


    def getWriters(self):
        """
        Fake L{IReactorFDSet.getWriters} which returns a list of writers from
        the local set.
        """
        return list(self.writers)


    def removeAll(self):
        """
        Fake L{IReactorFDSet.removeAll} which removed all readers and writers
        from the local sets.
        """
        self.readers.clear()
        self.writers.clear()


for iface in implementedBy(MemoryReactor):
    verifyClass(iface, MemoryReactor)



class MemoryReactorClock(MemoryReactor, Clock):
    def __init__(self):
        MemoryReactor.__init__(self)
        Clock.__init__(self)



@implementer(IReactorTCP, IReactorSSL, IReactorUNIX, IReactorSocket)
class RaisingMemoryReactor(object):
    """
    A fake reactor to be used in tests.  It accepts TCP connection setup
    attempts, but they will fail.

    @ivar _listenException: An instance of an L{Exception}
    @ivar _connectException: An instance of an L{Exception}
    """

    def __init__(self, listenException=None, connectException=None):
        """
        @param listenException: An instance of an L{Exception} to raise when any
            C{listen} method is called.

        @param connectException: An instance of an L{Exception} to raise when
            any C{connect} method is called.
        """
        self._listenException = listenException
        self._connectException = connectException


    def adoptStreamPort(self, fileno, addressFamily, factory):
        """
        Fake L{IReactorSocket.adoptStreamPort}, that raises
        L{self._listenException}.
        """
        raise self._listenException


    def listenTCP(self, port, factory, backlog=50, interface=''):
        """
        Fake L{reactor.listenTCP}, that raises L{self._listenException}.
        """
        raise self._listenException


    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """
        Fake L{reactor.connectTCP}, that raises L{self._connectException}.
        """
        raise self._connectException


    def listenSSL(self, port, factory, contextFactory,
                  backlog=50, interface=''):
        """
        Fake L{reactor.listenSSL}, that raises L{self._listenException}.
        """
        raise self._listenException


    def connectSSL(self, host, port, factory, contextFactory,
                   timeout=30, bindAddress=None):
        """
        Fake L{reactor.connectSSL}, that raises L{self._connectException}.
        """
        raise self._connectException


    def listenUNIX(self, address, factory,
                   backlog=50, mode=0o666, wantPID=0):
        """
        Fake L{reactor.listenUNIX}, that raises L{self._listenException}.
        """
        raise self._listenException


    def connectUNIX(self, address, factory, timeout=30, checkPID=0):
        """
        Fake L{reactor.connectUNIX}, that raises L{self._connectException}.
        """
        raise self._connectException
