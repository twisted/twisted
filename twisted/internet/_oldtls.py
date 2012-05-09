# -*- test-case-name: twisted.test.test_ssl -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module implements OpenSSL socket BIO based TLS support.  It is only used if
memory BIO APIs are not available, which is when the version of pyOpenSSL
installed is older than 0.10 (when L{twisted.protocols.tls} is not importable).
This implementation is undesirable because of the complexity of working with
OpenSSL's non-blocking socket-based APIs (which this module probably does about
99% correctly, but see #4455 for an example of a problem with it).

Eventually, use of this module should emit a warning.  See #4974 and 5014.

@see: L{twisted.internet._newtls}
@since: 11.1
"""

import os

from twisted.python.runtime import platformType
if platformType == 'win32':
    from errno import WSAEINTR as EINTR
    from errno import WSAEWOULDBLOCK as EWOULDBLOCK
    from errno import WSAENOBUFS as ENOBUFS
else:
    from errno import EINTR
    from errno import EWOULDBLOCK
    from errno import ENOBUFS

from OpenSSL import SSL

from zope.interface import implements

from twisted.python import log
from twisted.internet.interfaces import ITLSTransport, ISSLTransport
from twisted.internet.abstract import FileDescriptor
from twisted.internet.main import CONNECTION_DONE, CONNECTION_LOST
from twisted.internet._ssl import _TLSDelayed


class _TLSMixin:
    _socketShutdownMethod = 'sock_shutdown'

    writeBlockedOnRead = 0
    readBlockedOnWrite = 0
    _userWantRead = _userWantWrite = True

    def getPeerCertificate(self):
        return self.socket.get_peer_certificate()

    def doRead(self):
        if self.disconnected:
            # See the comment in the similar check in doWrite below.
            # Additionally, in order for anything other than returning
            # CONNECTION_DONE here to make sense, it will probably be necessary
            # to implement a way to switch back to TCP from TLS (actually, if
            # we did something other than return CONNECTION_DONE, that would be
            # a big part of implementing that feature).  In other words, the
            # expectation is that doRead will be called when self.disconnected
            # is True only when the connection has been lost.  It's possible
            # that the other end could stop speaking TLS and then send us some
            # non-TLS data.  We'll end up ignoring that data and dropping the
            # connection.  There's no unit tests for this check in the cases
            # where it makes a difference.  The test suite only hits this
            # codepath when it would have otherwise hit the SSL.ZeroReturnError
            # exception handler below, which has exactly the same behavior as
            # this conditional.  Maybe that's the only case that can ever be
            # triggered, I'm not sure.  -exarkun
            return CONNECTION_DONE
        if self.writeBlockedOnRead:
            self.writeBlockedOnRead = 0
            self._resetReadWrite()
        try:
            return self._base.doRead(self)
        except SSL.ZeroReturnError:
            return CONNECTION_DONE
        except SSL.WantReadError:
            return
        except SSL.WantWriteError:
            self.readBlockedOnWrite = 1
            self._base.startWriting(self)
            self._base.stopReading(self)
            return
        except SSL.SysCallError, (retval, desc):
            if ((retval == -1 and desc == 'Unexpected EOF')
                or retval > 0):
                return CONNECTION_LOST
            log.err()
            return CONNECTION_LOST
        except SSL.Error, e:
            return e

    def doWrite(self):
        # Retry disconnecting
        if self.disconnected:
            # This case is triggered when "disconnected" is set to True by a
            # call to _postLoseConnection from FileDescriptor.doWrite (to which
            # we upcall at the end of this overridden version of that API).  It
            # means that while, as far as any protocol connected to this
            # transport is concerned, the connection no longer exists, the
            # connection *does* actually still exist.  Instead of closing the
            # connection in the overridden _postLoseConnection, we probably
            # tried (and failed) to send a TLS close alert.  The TCP connection
            # is still up and we're waiting for the socket to become writeable
            # enough for the TLS close alert to actually be sendable.  Only
            # then will the connection actually be torn down. -exarkun
            return self._postLoseConnection()
        if self._writeDisconnected:
            return self._closeWriteConnection()

        if self.readBlockedOnWrite:
            self.readBlockedOnWrite = 0
            self._resetReadWrite()
        return self._base.doWrite(self)

    def writeSomeData(self, data):
        try:
            return self._base.writeSomeData(self, data)
        except SSL.WantWriteError:
            return 0
        except SSL.WantReadError:
            self.writeBlockedOnRead = 1
            self._base.stopWriting(self)
            self._base.startReading(self)
            return 0
        except SSL.ZeroReturnError:
            return CONNECTION_LOST
        except SSL.SysCallError, e:
            if e[0] == -1 and data == "":
                # errors when writing empty strings are expected
                # and can be ignored
                return 0
            else:
                return CONNECTION_LOST
        except SSL.Error, e:
            return e


    def _postLoseConnection(self):
        """
        Gets called after loseConnection(), after buffered data is sent.

        We try to send an SSL shutdown alert, but if it doesn't work, retry
        when the socket is writable.
        """
        # Here, set "disconnected" to True to trick higher levels into thinking
        # the connection is really gone.  It's not, and we're not going to
        # close it yet.  Instead, we'll try to send a TLS close alert to shut
        # down the TLS connection cleanly.  Only after we actually get the
        # close alert into the socket will we disconnect the underlying TCP
        # connection.
        self.disconnected = True
        if hasattr(self.socket, 'set_shutdown'):
            # If possible, mark the state of the TLS connection as having
            # already received a TLS close alert from the peer.  Why do
            # this???
            self.socket.set_shutdown(SSL.RECEIVED_SHUTDOWN)
        return self._sendCloseAlert()


    def _sendCloseAlert(self):
        # Okay, *THIS* is a bit complicated.

        # Basically, the issue is, OpenSSL seems to not actually return
        # errors from SSL_shutdown. Therefore, the only way to
        # determine if the close notification has been sent is by
        # SSL_shutdown returning "done". However, it will not claim it's
        # done until it's both sent *and* received a shutdown notification.

        # I don't actually want to wait for a received shutdown
        # notification, though, so, I have to set RECEIVED_SHUTDOWN
        # before calling shutdown. Then, it'll return True once it's
        # *SENT* the shutdown.

        # However, RECEIVED_SHUTDOWN can't be left set, because then
        # reads will fail, breaking half close.

        # Also, since shutdown doesn't report errors, an empty write call is
        # done first, to try to detect if the connection has gone away.
        # (*NOT* an SSL_write call, because that fails once you've called
        # shutdown)
        try:
            os.write(self.socket.fileno(), '')
        except OSError, se:
            if se.args[0] in (EINTR, EWOULDBLOCK, ENOBUFS):
                return 0
            # Write error, socket gone
            return CONNECTION_LOST

        try:
            if hasattr(self.socket, 'set_shutdown'):
                laststate = self.socket.get_shutdown()
                self.socket.set_shutdown(laststate | SSL.RECEIVED_SHUTDOWN)
                done = self.socket.shutdown()
                if not (laststate & SSL.RECEIVED_SHUTDOWN):
                    self.socket.set_shutdown(SSL.SENT_SHUTDOWN)
            else:
                #warnings.warn("SSL connection shutdown possibly unreliable, "
                #              "please upgrade to ver 0.XX", category=UserWarning)
                self.socket.shutdown()
                done = True
        except SSL.Error, e:
            return e

        if done:
            self.stopWriting()
            # Note that this is tested for by identity below.
            return CONNECTION_DONE
        else:
            # For some reason, the close alert wasn't sent.  Start writing
            # again so that we'll get another chance to send it.
            self.startWriting()
            # On Linux, select will sometimes not report a closed file
            # descriptor in the write set (in particular, it seems that if a
            # send() fails with EPIPE, the socket will not appear in the write
            # set).  The shutdown call above (which calls down to SSL_shutdown)
            # may have swallowed a write error.  Therefore, also start reading
            # so that if the socket is closed we will notice.  This doesn't
            # seem to be a problem for poll (because poll reports errors
            # separately) or with select on BSD (presumably because, unlike
            # Linux, it doesn't implement select in terms of poll and then map
            # POLLHUP to select's in fd_set).
            self.startReading()
            return None

    def _closeWriteConnection(self):
        result = self._sendCloseAlert()

        if result is CONNECTION_DONE:
            return self._base._closeWriteConnection(self)

        return result

    def startReading(self):
        self._userWantRead = True
        if not self.readBlockedOnWrite:
            return self._base.startReading(self)


    def stopReading(self):
        self._userWantRead = False
        # If we've disconnected, preventing stopReading() from happening
        # because we are blocked on a read is silly; the read will never
        # happen.
        if self.disconnected or not self.writeBlockedOnRead:
            return self._base.stopReading(self)


    def startWriting(self):
        self._userWantWrite = True
        if not self.writeBlockedOnRead:
            return self._base.startWriting(self)


    def stopWriting(self):
        self._userWantWrite = False
        # If we've disconnected, preventing stopWriting() from happening
        # because we are blocked on a write is silly; the write will never
        # happen.
        if self.disconnected or not self.readBlockedOnWrite:
            return self._base.stopWriting(self)


    def _resetReadWrite(self):
        # After changing readBlockedOnWrite or writeBlockedOnRead,
        # call this to reset the state to what the user requested.
        if self._userWantWrite:
            self.startWriting()
        else:
            self.stopWriting()

        if self._userWantRead:
            self.startReading()
        else:
            self.stopReading()



def _getTLSClass(klass, _existing={}):
    if klass not in _existing:
        class TLSConnection(_TLSMixin, klass):
            implements(ISSLTransport)
            _base = klass
        _existing[klass] = TLSConnection
    return _existing[klass]


class ConnectionMixin(object):
    """
    Mixin for L{twisted.internet.tcp.Connection} to help implement
    L{ITLSTransport} using pyOpenSSL to do crypto and I/O.
    """
    TLS = 0

    _tlsWaiting = None
    def startTLS(self, ctx, extra=True):
        assert not self.TLS
        if self.dataBuffer or self._tempDataBuffer:
            # pre-TLS bytes are still being written.  Starting TLS now
            # will do the wrong thing.  Instead, mark that we're trying
            # to go into the TLS state.
            self._tlsWaiting = _TLSDelayed([], ctx, extra)
            return False

        self.stopReading()
        self.stopWriting()
        self._startTLS()
        self.socket = SSL.Connection(ctx.getContext(), self.socket)
        self.fileno = self.socket.fileno
        self.startReading()
        return True


    def _startTLS(self):
        self.TLS = 1
        self.__class__ = _getTLSClass(self.__class__)


    def write(self, bytes):
        if self._tlsWaiting is not None:
            self._tlsWaiting.bufferedData.append(bytes)
        else:
            FileDescriptor.write(self, bytes)


    def writeSequence(self, iovec):
        if self._tlsWaiting is not None:
            self._tlsWaiting.bufferedData.extend(iovec)
        else:
            FileDescriptor.writeSequence(self, iovec)


    def doWrite(self):
        result = FileDescriptor.doWrite(self)
        if self._tlsWaiting is not None:
            if not self.dataBuffer and not self._tempDataBuffer:
                waiting = self._tlsWaiting
                self._tlsWaiting = None
                self.startTLS(waiting.context, waiting.extra)
                self.writeSequence(waiting.bufferedData)
        return result



class ClientMixin(object):
    """
    Mixin for L{twisted.internet.tcp.Client} to implement the client part of
    L{ITLSTransport}.
    """
    implements(ITLSTransport)

    def startTLS(self, ctx, client=1):
        if self._base.startTLS(self, ctx, client):
            if client:
                self.socket.set_connect_state()
            else:
                self.socket.set_accept_state()



class ServerMixin(object):
    """
    Mixin for L{twisted.internet.tcp.Client} to implement the server part of
    L{ITLSTransport}.
    """
    implements(ITLSTransport)

    def startTLS(self, ctx, server=1):
        if self._base.startTLS(self, ctx, server):
            if server:
                self.socket.set_accept_state()
            else:
                self.socket.set_connect_state()

