# -*- test-case-name: twisted.protocols.test.test_tls,twisted.internet.test.test_tls,twisted.test.test_sslverify -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of a TLS transport (L{ISSLTransport}) as an L{IProtocol}
layered on top of any L{ITransport} implementation, based on OpenSSL's
memory BIO features.

L{TLSMemoryBIOFactory} is a L{WrappingFactory} which wraps protocols created by
the factory it wraps with L{TLSMemoryBIOProtocol}.  L{TLSMemoryBIOProtocol}
intercedes between the underlying transport and the wrapped protocol to
implement SSL and TLS.  Typical usage of this module looks like this::

    from twisted.protocols.tls import TLSMemoryBIOFactory
    from twisted.internet.protocol import ServerFactory
    from twisted.internet.ssl import PrivateCertificate
    from twisted.internet import reactor

    from someapplication import ApplicationProtocol

    serverFactory = ServerFactory()
    serverFactory.protocol = ApplicationProtocol
    certificate = PrivateCertificate.loadPEM(certPEMData)
    contextFactory = certificate.options()
    tlsFactory = TLSMemoryBIOFactory(contextFactory, False, serverFactory)
    reactor.listenTCP(12345, tlsFactory)
    reactor.run()

Because the reactor's SSL and TLS APIs are likely implemented in a more
efficient way, it is more common to use them (see L{IReactorSSL} and
L{ITLSTransport}).  However, this API offers somewhat more flexibility; for
example, a L{TLSMemoryBIOProtocol} instance can use another instance of
L{TLSMemoryBIOProtocol} as its transport, yielding TLS over TLS - useful to
implement onion routing.  Or it can be used to run TLS over a UNIX socket,
or over stdio to a child process.
"""


from OpenSSL.SSL import Error, ZeroReturnError, WantReadError
from OpenSSL.SSL import TLSv1_METHOD, Context, Connection

try:
    Connection(Context(TLSv1_METHOD), None)
except TypeError, e:
    if str(e) != "argument must be an int, or have a fileno() method.":
        raise
    raise ImportError("twisted.protocols.tls requires pyOpenSSL 0.10 or newer.")

from zope.interface import implements

from twisted.python.failure import Failure
from twisted.internet.interfaces import ISystemHandle, ISSLTransport
from twisted.internet.main import CONNECTION_DONE, CONNECTION_LOST
from twisted.internet.protocol import Protocol
from twisted.protocols.policies import ProtocolWrapper, WrappingFactory


class TLSMemoryBIOProtocol(ProtocolWrapper):
    """
    L{TLSMemoryBIOProtocol} is a protocol wrapper which uses OpenSSL via a
    memory BIO to encrypt bytes written to it before sending them on to the
    underlying transport and decrypts bytes received from the underlying
    transport before delivering them to the wrapped protocol.

    @ivar _tlsConnection: The L{OpenSSL.SSL.Connection} instance which is
        encrypted and decrypting this connection.

    @ivar _lostConnection: A flag indicating whether connection loss has
        already been dealt with (C{True}) or not (C{False}).

    @ivar _writeBlockedOnRead: A flag indicating whether further writing must
        wait for data to be received (C{True}) or not (C{False}).

    @ivar _appSendBuffer: A C{list} of C{str} of application-level (cleartext)
        data which is waiting for C{_writeBlockedOnRead} to be reset to
        C{False} so it can be passed to and perhaps accepted by
        C{_tlsConnection.send}.

    @ivar _connectWrapped: A flag indicating whether or not to call
        C{makeConnection} on the wrapped protocol.  This is for the reactor's
        L{ITLSTransport.startTLS} implementation, since it has a protocol which
        it has already called C{makeConnection} on, and which has no interest
        in a new transport.  See #3821.

    @ivar _handshakeDone: A flag indicating whether or not the handshake is
        known to have completed successfully (C{True}) or not (C{False}).  This
        is used to control error reporting behavior.  If the handshake has not
        completed, the underlying L{OpenSSL.SSL.Error} will be passed to the
        application's C{connectionLost} method.  If it has completed, any
        unexpected L{OpenSSL.SSL.Error} will be turned into a
        L{ConnectionLost}.  This is weird; however, it is simply an attempt at
        a faithful re-implementation of the behavior provided by
        L{twisted.internet.ssl}.

    @ivar _reason: If an unexpected L{OpenSSL.SSL.Error} occurs which causes
        the connection to be lost, it is saved here.  If appropriate, this may
        be used as the reason passed to the application protocol's
        C{connectionLost} method.
    """
    implements(ISystemHandle, ISSLTransport)

    _reason = None
    _handshakeDone = False
    _lostConnection = False
    _writeBlockedOnRead = False

    def __init__(self, factory, wrappedProtocol, _connectWrapped=True):
        ProtocolWrapper.__init__(self, factory, wrappedProtocol)
        self._connectWrapped = _connectWrapped


    def getHandle(self):
        """
        Return the L{OpenSSL.SSL.Connection} object being used to encrypt and
        decrypt this connection.

        This is done for the benefit of L{twisted.internet.ssl.Certificate}'s
        C{peerFromTransport} and C{hostFromTransport} methods only.  A
        different system handle may be returned by future versions of this
        method.
        """
        return self._tlsConnection


    def makeConnection(self, transport):
        """
        Connect this wrapper to the given transport and initialize the
        necessary L{OpenSSL.SSL.Connection} with a memory BIO.
        """
        tlsContext = self.factory._contextFactory.getContext()
        self._tlsConnection = Connection(tlsContext, None)
        if self.factory._isClient:
            self._tlsConnection.set_connect_state()
        else:
            self._tlsConnection.set_accept_state()
        self._appSendBuffer = []

        # Intentionally skip ProtocolWrapper.makeConnection - it might call
        # wrappedProtocol.makeConnection, which we want to make conditional.
        Protocol.makeConnection(self, transport)
        self.factory.registerProtocol(self)
        if self._connectWrapped:
            # Now that the TLS layer is initialized, notify the application of
            # the connection.
            ProtocolWrapper.makeConnection(self, transport)

        # Now that we ourselves have a transport (initialized by the
        # ProtocolWrapper.makeConnection call above), kick off the TLS
        # handshake.
        try:
            self._tlsConnection.do_handshake()
        except WantReadError:
            # This is the expected case - there's no data in the connection's
            # input buffer yet, so it won't be able to complete the whole
            # handshake now.  If this is the speak-first side of the
            # connection, then some bytes will be in the send buffer now; flush
            # them.
            self._flushSendBIO()


    def _flushSendBIO(self):
        """
        Read any bytes out of the send BIO and write them to the underlying
        transport.
        """
        try:
            bytes = self._tlsConnection.bio_read(2 ** 15)
        except WantReadError:
            # There may be nothing in the send BIO right now.
            pass
        else:
            self.transport.write(bytes)


    def _flushReceiveBIO(self):
        """
        Try to receive any application-level bytes which are now available
        because of a previous write into the receive BIO.  This will take
        care of delivering any application-level bytes which are received to
        the protocol, as well as handling of the various exceptions which
        can come from trying to get such bytes.
        """
        # Keep trying this until an error indicates we should stop or we
        # close the connection.  Looping is necessary to make sure we
        # process all of the data which was put into the receive BIO, as
        # there is no guarantee that a single recv call will do it all.
        while not self._lostConnection:
            try:
                bytes = self._tlsConnection.recv(2 ** 15)
            except WantReadError:
                # The newly received bytes might not have been enough to produce
                # any application data.
                break
            except ZeroReturnError:
                # TLS has shut down and no more TLS data will be received over
                # this connection.
                self._lostConnection = True
                self.transport.loseConnection()
                if not self._handshakeDone and self._reason is not None:
                    failure = self._reason
                else:
                    failure = Failure(CONNECTION_DONE)
                # Failure's are fat.  Drop the reference.
                self._reason = None
                ProtocolWrapper.connectionLost(self, failure)
            except Error, e:
                # Something went pretty wrong.  For example, this might be a
                # handshake failure (because there were no shared ciphers, because
                # a certificate failed to verify, etc).  TLS can no longer proceed.
                self._flushSendBIO()
                self._lostConnection = True

                # Squash EOF in violation of protocol into ConnectionLost
                if e.args[0] == -1 and e.args[1] == 'Unexpected EOF':
                    failure = Failure(CONNECTION_LOST)
                else:
                    failure = Failure()
                ProtocolWrapper.connectionLost(self, failure)
                # This loseConnection call is basically tested by
                # test_handshakeFailure.  At least one side will need to do it
                # or the test never finishes.
                self.transport.loseConnection()
            else:
                # If we got application bytes, the handshake must be done by
                # now.  Keep track of this to control error reporting later.
                self._handshakeDone = True
                ProtocolWrapper.dataReceived(self, bytes)

        # The received bytes might have generated a response which needs to be
        # sent now.  For example, the handshake involves several round-trip
        # exchanges without ever producing application-bytes.
        self._flushSendBIO()


    def dataReceived(self, bytes):
        """
        Deliver any received bytes to the receive BIO and then read and deliver
        to the application any application-level data which becomes available
        as a result of this.
        """
        self._tlsConnection.bio_write(bytes)

        if self._writeBlockedOnRead:
            # A read just happened, so we might not be blocked anymore.  Try to
            # flush all the pending application bytes.
            self._writeBlockedOnRead = False
            appSendBuffer = self._appSendBuffer
            self._appSendBuffer = []
            for bytes in appSendBuffer:
                self.write(bytes)
            if not self._writeBlockedOnRead and self.disconnecting:
                self.loseConnection()

        self._flushReceiveBIO()


    def connectionLost(self, reason):
        """
        Handle the possible repetition of calls to this method (due to either
        the underlying transport going away or due to an error at the TLS
        layer) and make sure the base implementation only gets invoked once.
        """
        if not self._lostConnection:
            # Tell the TLS connection that it's not going to get any more data
            # and give it a chance to finish reading.
            self._tlsConnection.bio_shutdown()
            self._flushReceiveBIO()


    def loseConnection(self):
        """
        Send a TLS close alert and close the underlying connection.
        """
        self.disconnecting = True
        if not self._writeBlockedOnRead:
            self._tlsConnection.shutdown()
            self._flushSendBIO()
            self.transport.loseConnection()


    def write(self, bytes):
        """
        Process the given application bytes and send any resulting TLS traffic
        which arrives in the send BIO.
        """
        if self._lostConnection:
            return

        leftToSend = bytes
        while leftToSend:
            try:
                sent = self._tlsConnection.send(leftToSend)
            except WantReadError:
                self._writeBlockedOnRead = True
                self._appSendBuffer.append(leftToSend)
                break
            except Error, e:
                # Just drop the connection.  This has two useful consequences.
                # First, for the application protocol's connectionLost method,
                # it will squash any error into connection lost.  We *could*
                # let the real exception propagate to application code, but the
                # other SSL implementation doesn't.  Second, it causes the
                # protocol's connectionLost method to be invoked
                # non-reentrantly, which is always a nice feature.
                self._reason = Failure()
                self.transport.loseConnection()
                break
            else:
                # If we sent some bytes, the handshake must be done.  Keep
                # track of this to control error reporting behavior.
                self._handshakeDone = True
                self._flushSendBIO()
                leftToSend = leftToSend[sent:]


    def writeSequence(self, iovec):
        """
        Write a sequence of application bytes by joining them into one string
        and passing them to L{write}.
        """
        self.write("".join(iovec))


    def getPeerCertificate(self):
        return self._tlsConnection.get_peer_certificate()



class TLSMemoryBIOFactory(WrappingFactory):
    """
    L{TLSMemoryBIOFactory} adds TLS to connections.

    @ivar _contextFactory: The TLS context factory which will be used to define
        certain TLS connection parameters.

    @ivar _isClient: A flag which is C{True} if this is a client TLS
        connection, C{False} if it is a server TLS connection.
    """
    protocol = TLSMemoryBIOProtocol

    def __init__(self, contextFactory, isClient, wrappedFactory):
        WrappingFactory.__init__(self, wrappedFactory)
        self._contextFactory = contextFactory
        self._isClient = isClient
