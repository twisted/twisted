# -*- test-case-name: twisted.test.test_stringtransport -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Assorted functionality which is commonly useful when writing unit tests.
"""

from StringIO import StringIO

from zope.interface import implements

from twisted.internet.interfaces import ITransport, IConsumer, IPushProducer,\
    IConnector
from twisted.internet.interfaces import IReactorTCP, IReactorSSL, IReactorUNIX
from twisted.internet.interfaces import IListeningPort
from twisted.protocols import basic
from twisted.internet import protocol, error, address

from twisted.internet.address import IPv4Address, UNIXAddress


class AccumulatingProtocol(protocol.Protocol):
    """
    L{AccumulatingProtocol} is an L{IProtocol} implementation which collects
    the data delivered to it and can fire a Deferred when it is connected or
    disconnected.

    @ivar made: A flag indicating whether C{connectionMade} has been called.
    @ivar data: A string giving all the data passed to C{dataReceived}.
    @ivar closed: A flag indicated whether C{connectionLost} has been called.
    @ivar closedReason: The value of the I{reason} parameter passed to
        C{connectionLost}.
    @ivar closedDeferred: If set to a L{Deferred}, this will be fired when
        C{connectionLost} is called.
    """
    made = closed = 0
    closedReason = None

    closedDeferred = None

    data = ""

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
            map(self.sendLine, self.lines)

    def lineReceived(self, line):
        if not self.start:
            map(self.sendLine, self.lines)
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

    @ivar io: A L{StringIO} which holds the data which has been written to this
        transport since the last call to L{clear}.  Use L{value} instead of
        accessing this directly.
    """
    implements(ITransport, IConsumer, IPushProducer)

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
        self.io = StringIO()


    def value(self):
        """
        Retrieve all data which has been buffered by this transport.

        This is not a transport method.  It is intended for tests.  Do not use
        it in implementation code.

        @return: A C{str} giving all data written to this transport since the
            last call to L{clear}.
        @rtype: C{str}
        """
        return self.io.getvalue()


    # ITransport
    def write(self, data):
        if isinstance(data, unicode): # no, really, I mean it
            raise TypeError("Data must not be unicode")
        self.io.write(data)


    def writeSequence(self, data):
        self.io.write(''.join(data))


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
    def loseConnection(self):
        if self.connected:
            self.connected = False
            self.protocol.connectionLost(error.ConnectionDone("Bye."))



class StringIOWithoutClosing(StringIO):
    """
    A StringIO that can't be closed.
    """
    def close(self):
        """
        Do nothing.
        """



class _FakePort(object):
    """
    A fake L{IListeningPort} to be used in tests.

    @ivar _hostAddress: The L{IAddress} this L{IListeningPort} is pretending
        to be listening on.
    """
    implements(IListeningPort)

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



class _FakeConnector(object):
    """
    A fake L{IConnector} that allows us to inspect if it has been told to stop
    connecting.
    
    @ivar stoppedConnecting: has this connector's
        L{FakeConnector.stopConnecting} method been invoked yet?

    @ivar _address: An L{IAddress} provider that represents our destination.
    """
    implements(IConnector)

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
    """
    implements(IReactorTCP, IReactorSSL, IReactorUNIX)

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


    def listenTCP(self, port, factory, backlog=50, interface=''):
        """
        Fake L{reactor.listenTCP}, that logs the call and returns an
        L{IListeningPort}.
        """
        self.tcpServers.append((port, factory, backlog, interface))
        return _FakePort(IPv4Address('TCP', '0.0.0.0', port))


    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """
        Fake L{reactor.connectTCP}, that logs the call and returns an
        L{IConnector}.
        """
        self.tcpClients.append((host, port, factory, timeout, bindAddress))
        return _FakeConnector(IPv4Address('TCP', host, port))


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
        return _FakeConnector(IPv4Address('TCP', host, port))


    def listenUNIX(self, address, factory,
                   backlog=50, mode=0666, wantPID=0):
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
        return _FakeConnector(UNIXAddress(address))



class RaisingMemoryReactor(object):
    """
    A fake reactor to be used in tests.  It accepts TCP connection setup
    attempts, but they will fail.

    @ivar _listenException: An instance of an L{Exception}
    @ivar _connectException: An instance of an L{Exception}
    """
    implements(IReactorTCP, IReactorSSL, IReactorUNIX)

    def __init__(self, listenException=None, connectException=None):
        """
        @param listenException: An instance of an L{Exception} to raise when any
            C{listen} method is called.

        @param connectException: An instance of an L{Exception} to raise when
            any C{connect} method is called.
        """
        self._listenException = listenException
        self._connectException = connectException


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
                   backlog=50, mode=0666, wantPID=0):
        """
        Fake L{reactor.listenUNIX}, that raises L{self._listenException}.
        """
        raise self._listenException


    def connectUNIX(self, address, factory, timeout=30, checkPID=0):
        """
        Fake L{reactor.connectUNIX}, that raises L{self._connectException}.
        """
        raise self._connectException
