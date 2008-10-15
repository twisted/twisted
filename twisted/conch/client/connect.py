# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
import os

from twisted.internet import defer, protocol, reactor
from twisted.conch import error
from twisted.conch.ssh import transport
from twisted.python import log

from twisted.conch.client import unix, direct

connectTypes = {"direct" : direct.connect,
                "unix" : unix.connect}

def connect(host, port, options, verifyHostKey, userAuthObject):
    useConnects = options.conns or ['unix', 'direct']
    return _ebConnect(None, useConnects, host, port, options, verifyHostKey,
                      userAuthObject)

def _ebConnect(f, useConnects, host, port, options, vhk, uao):
    if not useConnects:
        return f
    connectType = useConnects.pop(0)
    f = connectTypes[connectType]
    d = f(host, port, options, vhk, uao)
    d.addErrback(_ebConnect, useConnects, host, port, options, vhk, uao)
    return d


class SSHClientFactory(protocol.ClientFactory):
    """
    An SSHClientFactory based on the one in
    twisted.conch.client.direct, but with better support for handling
    disconnects after the connection has been established.
    """

    didConnect = 0

    def __init__(self, willConnect, didDisconnect, options, verifyHostKey, userAuthObject):
        self.willConnect = willConnect.addCallback(self._cbWillConnect)
        self.didDisconnect = didDisconnect
        self.options = options
        self.verifyHostKey = verifyHostKey
        self.userAuthObject = userAuthObject

    def _cbWillConnect(self, ignored):
        #log.msg("_cbWillConnect")
        self.didConnect = 1
        self.willConnect = None
        return ignored

    def clientConnectionLost(self, connector, reason):
        log.msg("clientConnectionLost", reason)
        if self.options['reconnect']:
            connector.connect()


    def clientConnectionFailed(self, connector, reason):
        #log.msg("clientConnectionFailed", reason)
        if self.didConnect:
            return
        self.willConnect.errback(reason)


    def buildProtocol(self, addr):
        trans = SSHClientTransport(self)
        if self.options['ciphers']:
            trans.supportedCiphers = self.options['ciphers']
        if self.options['macs']:
            trans.supportedMACs = self.options['macs']
        if self.options['compress']:
            trans.supportedCompressions[0:1] = ['zlib']
        if self.options['host-key-algorithms']:
            trans.supportedPublicKeys = self.options['host-key-algorithms']
        return trans



class SSHClientTransport(transport.SSHClientTransport):
    """
    An ssh client transport based on the one in
    twisted.conch.client.direct but with better handling for
    disconnect behavior after the connection is established.
    """

    def __init__(self, factory):
        self.factory = factory
        self.unixServer = None


    def connectionLost(self, reason):
        """
        Shuts down the cached unix server if one was created.
        """
        if self.unixServer:
            d = self.unixServer.stopListening()
            self.unixServer = None
        else:
            d = defer.succeed(None)
        d.addCallback(lambda x:
            transport.SSHClientTransport.connectionLost(self, reason))


    def receiveError(self, code, desc):
        """
        This is issued when the other side sends us a disconnect.  It does not
        happen when we chose to disconnect ourselves.

        We errback in all cases.  Where the errback goes is a function
        of the state of the connection.  If we're still setting up, we
        errback to willConnect.  If we're after that point, to
        didDisconnect.
        """

        if self.factory.didConnect:
            self.factory.didDisconnect.errback(error.ConchError(desc, code))
        else:
            self.factory.willConnect.errback(error.ConchError(desc, code))

    def sendDisconnect(self, code, reason):
        """
        this message is issued when either the server or the client
        shuts down the connection.

        If the connection was already up and running, we errback to
        didDisconnect; if the problem occured while still establishing
        the connection, then we errback to willConnect.

        In the case where the disconnect request comes from the server
        end, receiveError will have already sent an errback and we must
        not try to invoke the errback a second time.

        Note that these messages are always errbacks.  Clients of this
        class can use an errback to switch over to callback chain
        processing if the error code is an expected value (such as
        DISCONNECT_CONNECTION_LOST, during a loseConnection call).
        
        """

        transport.SSHClientTransport.sendDisconnect(self, code, reason)
        if self.factory.didConnect:
            # we're connected, so we'll talk to didDisconnect, but
            # only if receiveError didn't get there first (due to an
            # error received from the other side).
            if not self.factory.didDisconnect.called:
                self.factory.didDisconnect.errback(error.ConchError(reason, code))
            else:
                pass # already called in receiveError
        elif not self.factory.willConnect.called:
            # we're trying to connect and weren't able to do so, let
            # willConnect know, unless receiveError beat us to it.
            self.factory.willConnect.errback(error.ConchError(reason, code))
        else:
            pass # already called in receive error


    def receiveDebug(self, alwaysDisplay, message, lang):
        #log.msg('Received Debug Message: %s' % message)
        if alwaysDisplay: # XXX what should happen here?
            log.msg(message)


    def verifyHostKey(self, pubKey, fingerprint):
        """
        Ask our factory to verify the other side's host key.
        """

        return self.factory.verifyHostKey(self, self.transport.getPeer().host, pubKey,
                                          fingerprint)


    def setService(self, service):
        """
        if we're establishing an SSH connection and we were asked to
        cache it through a unix domain socket, set that up now.  If
        we're not in the ssh-userauth phase, then we're up and running
        and it's time to let willConnet know with a callback.
        """

        #log.msg('setting client server to %s' % service)
        transport.SSHClientTransport.setService(self, service)
        if service.name == 'ssh-connection':
            # listen for UNIX
            if not self.factory.options['nocache']:
                user = self.factory.userAuthObject.user
                peer = self.transport.getPeer()
                filename = os.path.expanduser("~/.conch-%s-%s-%i" % (user, peer.host, peer.port))

                # this is one possible solution to the deprecation of the mode argument to listenUNIX
                # but it is not enabled here because t.c.c.unix expects to find the socket file
                # in the "bad" location

                #path = os.path.expanduser("~/.conch")
                #if not os.path.exists(path):
                #    os.makedirs(path)
                #     os.chmod(path, 0700)
                #filename = os.path.join(path, "%s-%s-%i" % (user, peer.host, peer.port))

                u = unix.SSHUnixServerFactory(service)
                try:
                    self.unixServer = reactor.listenUNIX(filename, u, mode=0600, wantPID=1)
                except:
                    if self.factory.d is not None:
                        d, self.factory.d = self.factory.d, None
                        d.errback(None)
        if service.name != 'ssh-userauth' and not self.factory.didConnect:
            self.factory.willConnect.callback(None)


    def connectionSecure(self):
        """
        Delegated to the userAuthObject
        """

        self.requestService(self.factory.userAuthObject)

def connectTCP(host, port, options, verifyHostKey, userAuthObject):
    """
    connect to host:port using options.  Host key verification will be
    the responsibility of the verifyHostKey function.  The
    userAuthObject will be responsible for user authentication.

    Installs two deferred objects on the factory created here.  The
    first calls/errs back based on the outcome of the connection
    process.  Subsequent problems, including clean disconnects, are
    reported on the second Deferred.

    The first of these two Deferreds is returned by this function.
    The other is available as the didDisconnect attribute of the
    connection's factory attribute.
    """

    willConnect = defer.Deferred()
    didDisconnect = defer.Deferred()
    factory = SSHClientFactory(willConnect, didDisconnect, options, verifyHostKey, userAuthObject)
    reactor.connectTCP(host, port, factory)
    return willConnect
