# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
from twisted.internet import defer, protocol, reactor
from twisted.conch import error
from twisted.conch.ssh import transport
from twisted.python import log

import unix

import os

class SSHClientFactory(protocol.ClientFactory):
#    noisy = 1

    def __init__(self, d, options, verifyHostKey, userAuthObject):
        self.d = d
        self.options = options
        self.verifyHostKey = verifyHostKey
        self.userAuthObject = userAuthObject

    def clientConnectionLost(self, connector, reason):
        if self.options['reconnect']:
            connector.connect()

    def clientConnectionFailed(self, connector, reason):
        if not self.d: return
        d = self.d
        self.d = None
        d.errback(reason)

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

    def __init__(self, factory):
        self.factory = factory
        self.unixServer = None

    def connectionLost(self, reason):
        transport.SSHClientTransport.connectionLost(self, reason)
        if self.unixServer:
            self.unixServer.stopListening()
            self.unixServer = None

    def receiveError(self, code, desc):
        if not self.factory.d: return
        d = self.factory.d
        self.factory.d = None
        d.errback(error.ConchError(desc, code))

    def sendDisconnect(self, code, reason):
        if not self.factory.d: return
        d = self.factory.d
        self.factory.d = None
        transport.SSHClientTransport.sendDisconnect(self, code, reason)
        d.errback(error.ConchError(reason, code))

    def receiveDebug(self, alwaysDisplay, message, lang):
        log.msg('Received Debug Message: %s' % message)
        if alwaysDisplay: # XXX what should happen here?
            print message

    def verifyHostKey(self, pubKey, fingerprint):
        return self.factory.verifyHostKey(self, self.transport.getPeer().host, pubKey,
                                          fingerprint)

    def setService(self, service):
        log.msg('setting client server to %s' % service)
        transport.SSHClientTransport.setService(self, service)
        if service.name != 'ssh-userauth' and self.factory.d:
            d = self.factory.d
            self.factory.d = None
            d.callback(None)
        if service.name == 'ssh-connection':
            # listen for UNIX
            if not self.factory.options['nocache']:
                user = self.factory.userAuthObject.user
                peer = self.transport.getPeer()
                filename = os.path.expanduser("~/.conch-%s-%s-%i" % (user, peer.host, peer.port))
                try:
                    u = unix.SSHUnixServerFactory(service)
                    try:
                        os.unlink(filename)
                    except OSError:
                        pass
                    self.unixServer = reactor.listenUNIX(filename, u, mode=0600, wantPID=1)
                except Exception, e:
                    log.msg('error trying to listen on %s' % filename)
                    log.err(e)

    def connectionSecure(self):
        self.requestService(self.factory.userAuthObject)


def connect(host, port, options, verifyHostKey, userAuthObject):
    d = defer.Deferred()
    factory = SSHClientFactory(d, options, verifyHostKey, userAuthObject)
    reactor.connectTCP(host, port, factory)
    return d
