# -*- test-case-name: twisted.protocols.test.test_tls,twisted.internet.test.test_tls,twisted.test.test_sslverify -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of a TLS transport (L{ISSLTransport}) as an
L{IProtocol<twisted.internet.interfaces.IProtocol>} layered on top of any
L{ITransport<twisted.internet.interfaces.ITransport>} implementation, based on
U{OpenSSL<http://www.openssl.org>}'s memory BIO features.

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

This API offers somewhat more flexibility than
L{twisted.internet.interfaces.IReactorSSL}; for example, a
L{TLSMemoryBIOProtocol} instance can use another instance of
L{TLSMemoryBIOProtocol} as its transport, yielding TLS over TLS - useful to
implement onion routing.  It can also be used to run TLS over unusual
transports, such as UNIX sockets and stdio.
"""

from __future__ import division, absolute_import

from OpenSSL.SSL import Error, ZeroReturnError, WantReadError, WantWriteError
from OpenSSL.SSL import TLSv1_METHOD, Context, Connection

try:
    Connection(Context(TLSv1_METHOD), None)
except TypeError as e:
    if str(e) != "argument must be an int, or have a fileno() method.":
        raise
    raise ImportError("twisted.protocols.tls requires pyOpenSSL 0.10 or newer.")

from zope.interface import implementer, providedBy, directlyProvides

from twisted.python.compat import unicode
from twisted.python.failure import Failure
from twisted.python import log
from twisted.python.reflect import safe_str
from twisted.internet.interfaces import ISystemHandle, ISSLTransport
from twisted.internet.interfaces import IPushProducer, ILoggingContext
from twisted.internet import defer
from twisted.internet.main import CONNECTION_LOST
from twisted.internet.protocol import Protocol
from twisted.internet.task import cooperate
from twisted.protocols.policies import ProtocolWrapper, WrappingFactory


@implementer(IPushProducer)
class _PullToPush(object):
    """
    An adapter that converts a non-streaming to a streaming producer.

    Because of limitations of the producer API, this adapter requires the
    cooperation of the consumer. When the consumer's C{registerProducer} is
    called with a non-streaming producer, it must wrap it with L{_PullToPush}
    and then call C{startStreaming} on the resulting object. When the
    consumer's C{unregisterProducer} is called, it must call
    C{stopStreaming} on the L{_PullToPush} instance.

    If the underlying producer throws an exception from C{resumeProducing},
    the producer will be unregistered from the consumer.

    @ivar _producer: the underling non-streaming producer.

    @ivar _consumer: the consumer with which the underlying producer was
                     registered.

    @ivar _finished: C{bool} indicating whether the producer has finished.

    @ivar _coopTask: the result of calling L{cooperate}, the task driving the
                     streaming producer.
    """

    _finished = False


    def __init__(self, pullProducer, consumer):
        self._producer = pullProducer
        self._consumer = consumer


    def _pull(self):
        """
        A generator that calls C{resumeProducing} on the underlying producer
        forever.

        If C{resumeProducing} throws an exception, the producer is
        unregistered, which should result in streaming stopping.
        """
        while True:
            try:
                self._producer.resumeProducing()
            except:
                log.err(None, "%s failed, producing will be stopped:" %
                        (safe_str(self._producer),))
                try:
                    self._consumer.unregisterProducer()
                    # The consumer should now call stopStreaming() on us,
                    # thus stopping the streaming.
                except:
                    # Since the consumer blew up, we may not have had
                    # stopStreaming() called, so we just stop on our own:
                    log.err(None, "%s failed to unregister producer:" %
                            (safe_str(self._consumer),))
                    self._finished = True
                    return
            yield None


    def startStreaming(self):
        """
        This should be called by the consumer when the producer is registered.

        Start streaming data to the consumer.
        """
        self._coopTask = cooperate(self._pull())


    def stopStreaming(self):
        """
        This should be called by the consumer when the producer is unregistered.

        Stop streaming data to the consumer.
        """
        if self._finished:
            return
        self._finished = True
        self._coopTask.stop()


    # IPushProducer implementation:
    def pauseProducing(self):
        self._coopTask.pause()


    def resumeProducing(self):
        self._coopTask.resume()


    def stopProducing(self):
        self.stopStreaming()
        self._producer.stopProducing()



@implementer(IPushProducer)
class _ProducerMembrane(object):
    """
    Stand-in for producer registered with a L{TLSMemoryBIOProtocol} transport.

    Ensures that producer pause/resume events from the undelying transport are
    coordinated with pause/resume events from the TLS layer.

    @ivar _producer: The application-layer producer.
    """

    _producerPaused = False

    def __init__(self, producer):
        self._producer = producer


    def pauseProducing(self):
        """
        C{pauseProducing} the underlying producer, if it's not paused.
        """
        if self._producerPaused:
            return
        self._producerPaused = True
        self._producer.pauseProducing()


    def resumeProducing(self):
        """
        C{resumeProducing} the underlying producer, if it's paused.
        """
        if not self._producerPaused:
            return
        self._producerPaused = False
        self._producer.resumeProducing()


    def stopProducing(self):
        """
        C{stopProducing} the underlying producer.

        There is only a single source for this event, so it's simply passed
        on.
        """
        self._producer.stopProducing()



@implementer(ISystemHandle, ISSLTransport)
class TLSMemoryBIOProtocol(ProtocolWrapper):
    """
    L{TLSMemoryBIOProtocol} is a protocol wrapper which uses OpenSSL via a
    memory BIO to encrypt bytes written to it before sending them on to the
    underlying transport and decrypts bytes received from the underlying
    transport before delivering them to the wrapped protocol.

    In addition to producer events from the underlying transport, the need to
    wait for reads before a write can proceed means the L{TLSMemoryBIOProtocol}
    may also want to pause a producer.  Pause/resume events are therefore
    merged using the L{_ProducerMembrane} wrapper.  Non-streaming (pull)
    producers are supported by wrapping them with L{_PullToPush}.

    @ivar _tlsConnection: The L{OpenSSL.SSL.Connection} instance which is
        encrypted and decrypting this connection.

    @ivar _lostTLSConnection: A flag indicating whether connection loss has
        already been dealt with (C{True}) or not (C{False}).  TLS disconnection
        is distinct from the underlying connection being lost.

    @ivar _writeBlockedOnRead: A flag indicating whether further writing must
        wait for data to be received (C{True}) or not (C{False}).

    @ivar _appSendBuffer: A C{list} of C{str} of application-level (cleartext)
        data which is waiting for C{_writeBlockedOnRead} to be reset to
        C{False} so it can be passed to and perhaps accepted by
        C{_tlsConnection.send}.

    @ivar _connectWrapped: A flag indicating whether or not to call
        C{makeConnection} on the wrapped protocol.  This is for the reactor's
        L{twisted.internet.interfaces.ITLSTransport.startTLS} implementation,
        since it has a protocol which it has already called C{makeConnection}
        on, and which has no interest in a new transport.  See #3821.

    @ivar _handshaking: C{True} if the handshake has yet to be completed,
        C{False} if it has completed.
    @type _handshaking: L{bool}

    @ivar _handshakeError: If the handshake failed, then this will store the
        reason.  Otherwise it is C{None}.
    @type _handshakeError: L{Failure} or L{NoneType}

    @ivar _reason: If an unexpected L{OpenSSL.SSL.Error} occurs which causes
        the connection to be lost, it is saved here.  If appropriate, this may
        be used as the reason passed to the application protocol's
        C{connectionLost} method.

    @ivar _producer: The current producer registered via C{registerProducer},
        or C{None} if no producer has been registered or a previous one was
        unregistered.
    """

    _reason = None
    _handshaking = True
    _handshakeError = None
    _lostTLSConnection = False
    _writeBlockedOnRead = False
    _producer = None

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

        # Add interfaces provided by the transport we are wrapping:
        for interface in providedBy(transport):
            directlyProvides(self, interface)

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
        self._tryHandshake()


    def _tryHandshake(self):
        """
        Attempt to make progress on the handshake.

        This tells OpenSSL to try to do some handshake work and then flushes
        the send buffer if necessary.
        """
        while True:
            try:
                self._tlsConnection.do_handshake()
            except WantReadError:
                # do_handshake may have written to the send buffer and now be
                # waiting for a reply.
                self._flushSendBIO()
            except WantWriteError:
                # do_handshake tried to write to the send buffer but found
                # there was no room to do so.  Make some room and then repeat
                # the loop so it has a chance to write what it wanted to write.
                self._flushSendBIO()
                # And give it that chance now.
                continue
            except Error:
                self._tlsShutdownFinished(Failure())
            else:
                self._handshakeFinished(None)

            # Either the handshake is done or we encountered an obstacle that
            # requires some bytes to arrive over the network.  Stop trying to
            # handshake.
            break


    def _handshakeFinished(self, error):
        """
        Mark the handshake done and notify everyone.  It's safe to call this
        more than once (all calls except the first will be ignored).

        @param error: The reason the handshake failed or C{None} if it
            succeeded.
        @type error: L{Failure} or L{NoneType}
        """


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
        # SSL_read can transparently complete a handshake, but we can't
        # rely on it: if the handshake is done but there's no application
        # data, then SSL_read won't tell us.
        if self._handshaking:
            self._tryHandshake()

        # Check again, the handshake may have completed.
        if self._handshaking:
            # If not, save some effort.  Reading application bytes (SSL_read)
            # can't possibly return anything useful.
            return

        # Keep trying this until an error indicates we should stop or we
        # close the connection.  Looping is necessary to make sure we
        # process all of the data which was put into the receive BIO, as
        # there is no guarantee that a single recv call will do it all.
        while not self._lostTLSConnection:
            try:
                bytes = self._tlsConnection.recv(2 ** 15)
            except WantReadError:
                # The newly received bytes might not have been enough to produce
                # any application data.
                break
            except ZeroReturnError:
                # TLS has shut down and no more TLS data will be received over
                # this connection.
                self._shutdownTLS()
                # Passing in None means the user protocol's connnectionLost
                # will get called with reason from underlying transport:
                self._tlsShutdownFinished(None)
            except Error as e:
                # Something went pretty wrong.  For example, this might be a
                # handshake failure (because there were no shared ciphers, because
                # a certificate failed to verify, etc).  TLS can no longer proceed.

                # Squash EOF in violation of protocol into ConnectionLost; we
                # create Failure before calling _flushSendBio so that no new
                # exception will get thrown in the interim.
                if e.args[0] == -1 and e.args[1] == 'Unexpected EOF':
                    failure = Failure(CONNECTION_LOST)
                else:
                    failure = Failure()

                self._flushSendBIO()
                self._tlsShutdownFinished(failure)
            else:
                ProtocolWrapper.dataReceived(self, bytes)

        # The received bytes might have generated a response which needs to be
        # sent now.  This is most likely to occur during renegotiation.
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
                self._write(bytes)
            if (not self._writeBlockedOnRead and self.disconnecting and
                self.producer is None):
                self._shutdownTLS()
            if self._producer is not None:
                self._producer.resumeProducing()

        self._flushReceiveBIO()


    def _shutdownTLS(self):
        """
        Initiate, or reply to, the shutdown handshake of the TLS layer.
        """
        shutdownSuccess = self._tlsConnection.shutdown()
        self._flushSendBIO()
        if shutdownSuccess:
            # Both sides have shutdown, so we can start closing lower-level
            # transport. This will also happen if we haven't started
            # negotiation at all yet, in which case shutdown succeeds
            # immediately.
            self.transport.loseConnection()


    def _tlsShutdownFinished(self, reason):
        """
        Called when TLS connection has gone away; tell underlying transport to
        disconnect.
        """
        self._handshakeFinished(reason)
        self._reason = reason
        self._lostTLSConnection = True
        # Using loseConnection causes the application protocol's
        # connectionLost method to be invoked non-reentrantly, which is always
        # a nice feature. However, for error cases (reason != None) we might
        # want to use abortConnection when it becomes available. The
        # loseConnection call is basically tested by test_handshakeFailure.
        # At least one side will need to do it or the test never finishes.
        self.transport.loseConnection()


    def connectionLost(self, reason):
        """
        Handle the possible repetition of calls to this method (due to either
        the underlying transport going away or due to an error at the TLS
        layer) and make sure the base implementation only gets invoked once.
        """
        if not self._lostTLSConnection:
            # Tell the TLS connection that it's not going to get any more data
            # and give it a chance to finish handshaking and/or reading.
            self._tlsConnection.bio_shutdown()
            self._flushReceiveBIO()
            self._lostTLSConnection = True
        reason = self._reason or reason
        self._reason = None
        ProtocolWrapper.connectionLost(self, reason)


    def loseConnection(self):
        """
        Send a TLS close alert and close the underlying connection.
        """
        if self.disconnecting:
            return
        self.disconnecting = True
        if not self._writeBlockedOnRead and self._producer is None:
            self._shutdownTLS()


    def write(self, bytes):
        """
        Process the given application bytes and send any resulting TLS traffic
        which arrives in the send BIO.

        If C{loseConnection} was called, subsequent calls to C{write} will
        drop the bytes on the floor.
        """
        if isinstance(bytes, unicode):
            raise TypeError("Must write bytes to a TLS transport, not unicode.")
        # Writes after loseConnection are not supported, unless a producer has
        # been registered, in which case writes can happen until the producer
        # is unregistered:
        if self.disconnecting and self._producer is None:
            return
        self._write(bytes)


    def _write(self, bytes):
        """
        Process the given application bytes and send any resulting TLS traffic
        which arrives in the send BIO.

        This may be called by C{dataReceived} with bytes that were buffered
        before C{loseConnection} was called, which is why this function
        doesn't check for disconnection but accepts the bytes regardless.
        """
        if self._lostTLSConnection:
            return

        # A TLS payload is 16kB max
        bufferSize = 2 ** 16

        # How far into the input we've gotten so far
        alreadySent = 0

        while alreadySent < len(bytes):
            toSend = bytes[alreadySent:alreadySent + bufferSize]
            try:
                sent = self._tlsConnection.send(toSend)
            except WantReadError:
                self._writeBlockedOnRead = True
                self._appSendBuffer.append(bytes[alreadySent:])
                if self._producer is not None:
                    self._producer.pauseProducing()
                break
            except Error:
                # Pretend TLS connection disconnected, which will trigger
                # disconnect of underlying transport. The error will be passed
                # to the application protocol's connectionLost method.  The
                # other SSL implementation doesn't, but losing helpful
                # debugging information is a bad idea.
                self._tlsShutdownFinished(Failure())
                break
            else:
                # SSL_write can transparently complete a handshake.  If we get
                # here, then we're done handshaking.
                self._handshakeFinished(None)
                self._flushSendBIO()
                alreadySent += sent


    def writeSequence(self, iovec):
        """
        Write a sequence of application bytes by joining them into one string
        and passing them to L{write}.
        """
        self.write(b"".join(iovec))


    def getPeerCertificate(self):
        return self._tlsConnection.get_peer_certificate()


    def registerProducer(self, producer, streaming):
        # If we've already disconnected, nothing to do here:
        if self._lostTLSConnection:
            producer.stopProducing()
            return

        # If we received a non-streaming producer, wrap it so it becomes a
        # streaming producer:
        if not streaming:
            producer = streamingProducer = _PullToPush(producer, self)
        producer = _ProducerMembrane(producer)
        # This will raise an exception if a producer is already registered:
        self.transport.registerProducer(producer, True)
        self._producer = producer
        # If we received a non-streaming producer, we need to start the
        # streaming wrapper:
        if not streaming:
            streamingProducer.startStreaming()


    def unregisterProducer(self):
        # If we received a non-streaming producer, we need to stop the
        # streaming wrapper:
        if isinstance(self._producer._producer, _PullToPush):
            self._producer._producer.stopStreaming()
        self._producer = None
        self._producerPaused = False
        self.transport.unregisterProducer()
        if self.disconnecting and not self._writeBlockedOnRead:
            self._shutdownTLS()



class TLSMemoryBIOFactory(WrappingFactory):
    """
    L{TLSMemoryBIOFactory} adds TLS to connections.

    @ivar _contextFactory: The TLS context factory which will be used to define
        certain TLS connection parameters.

    @ivar _isClient: A flag which is C{True} if this is a client TLS
        connection, C{False} if it is a server TLS connection.
    """
    protocol = TLSMemoryBIOProtocol

    noisy = False  # disable unnecessary logging.

    def __init__(self, contextFactory, isClient, wrappedFactory):
        WrappingFactory.__init__(self, wrappedFactory)
        self._contextFactory = contextFactory
        self._isClient = isClient

        # Force some parameter checking in pyOpenSSL.  It's better to fail now
        # than after we've set up the transport.
        contextFactory.getContext()


    def logPrefix(self):
        """
        Annotate the wrapped factory's log prefix with some text indicating TLS
        is in use.

        @rtype: C{str}
        """
        if ILoggingContext.providedBy(self.wrappedFactory):
            logPrefix = self.wrappedFactory.logPrefix()
        else:
            logPrefix = self.wrappedFactory.__class__.__name__
        return "%s (TLS)" % (logPrefix,)

