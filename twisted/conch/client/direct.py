# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2004 Matthew W. Lefkowitz
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

#    def stopFactory(self):
#        stopConnection()

    def connectionFailed(self, reason):
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
        return trans

class SSHClientTransport(transport.SSHClientTransport):

    def __init__(self, factory):
        self.factory = factory

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
        transport.SSHClientTransport.setService(self, service)
        if service.name == 'ssh-connection':
            # listen for UNIX
            if not self.factory.options['nocache']:
                user = self.factory.userAuthObject.user
                peer = self.transport.getPeer()
                filename = os.path.expanduser("~/.conch-%s-%s-%i" % (user, peer.host, peer.port))
                try:
                    reactor.listenUNIX(filename, unix.SSHUnixServerFactory(service), mode=0600, wantPID=1)
                except Exception, e:
                    log.msg('error trying to listen on %s' % filename)
                    log.err(e)

    def connectionSecure(self):
        if not self.factory.d: return
        d = self.factory.d
        self.factory.d = None
        d.callback(None)
        self.requestService(self.factory.userAuthObject)


def connect(host, port, options, verifyHostKey, userAuthObject):
    d = defer.Deferred()
    factory = SSHClientFactory(d, options, verifyHostKey, userAuthObject)
    reactor.connectTCP(host, port, factory)
    return d
