# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
import os.path, base64
from twisted.conch import error
from twisted.internet import app, defer
from twisted.python import failure, log
from common import NS, getNS, MP
import keys, transport, service

class SSHUserAuthServer(service.SSHService):
    name = 'ssh-userauth'
    protocolMessages = None # set later
    supportedAuthentications = ('publickey','password')
    authenticatedWith = []

    def tryAuth(self, kind, user, data):
        log.msg('%s trying auth %s' % (user, kind))
        d = self.transport.factory.authorizer.getIdentityRequest(user)
        d.pause()
        d.addCallback(self._cbTryAuth, kind, data)
        return d

    def _cbTryAuth(self, identity, kind, data):
        log.msg('%s trying auth %s with identity' % (identity.name, kind))
        f = getattr(self,'auth_%s'%kind, None)
        if f:
            return f(identity, data)
        raise error.ConchError('bad auth for %s' % kind) # this should make it err back

    def ssh_USERAUTH_REQUEST(self, packet):
        user, nextService, method, rest = getNS(packet, 3)
        self.user = user
        self.nextService = nextService
        self.method = method
        d = self.tryAuth(method, user, rest)
        d.addCallbacks(self._cbGoodAuth, self._ebBadAuth)
        d.unpause() # we need this because it turns out Deferreds /really/ want to report errors

    def _cbGoodAuth(self, foo):
        if foo == -1: # got a callback saying we sent another packet type
            return
        log.msg('%s authenticated with %s' % (self.user, self.method))
        self.authenticatedWith.append(self.method)
        if self.areDone():
            self.transport.sendPacket(MSG_USERAUTH_SUCCESS, '')
            self.transport.setService(self.transport.factory.services[self.nextService]())
        else:
            self.transport.sendPacket(MSG_USERAUTH_FAILURE, NS(','.join(self.supportedAuthentications))+'\xff')

    def _ebBadAuth(self, foo):
        if isinstance(foo, failure.Failure):
            foo.trap(error.ConchError)
        elif foo == "unauthorized":
            pass
        else:
            raise foo
        if self.method != 'none': # ignore 'none' as a method
            log.msg('%s failed auth %s' % (self.user, self.method))
            log.msg('potential reason: %s' % foo)
            #print foo
        self.transport.sendPacket(MSG_USERAUTH_FAILURE, NS(','.join(self.supportedAuthentications))+'\x00')

    def auth_publickey(self, ident, packet):
        hasSig = ord(packet[0])
        self.hasSigType = hasSig # protocol impl.s differ in this
        algName, blob, rest = getNS(packet[1:], 2)
        if hasSig:
            #print 'has sig'
            d = ident.validatePublicKey(blob)
            d.addCallback(self._cbToVerifySig, ident, blob, getNS(rest)[0])
            return d
        else:
            #print 'does not have sig'
            d = ident.validatePublicKey(blob)
            d.addCallback(self._cbValidateKey, packet[1:])
            return d

    def _cbToVerifySig(self, foo, ident, blob, signature):
        if not self.verifySignatureFor(ident, blob, signature):
            raise error.ConchError('bad sig') # this kicks it into errback mode

    def _cbValidateKey(self, foo, packet):
        self.transport.sendPacket(MSG_USERAUTH_PK_OK, packet)
        return -1
        
    def verifySignatureFor(self, ident, blob, signature):
        pubKey = keys.getPublicKeyObject(data = blob)
        b = NS(self.transport.sessionID) + chr(MSG_USERAUTH_REQUEST) + \
            NS(ident.name) + NS(self.nextService) + NS('publickey') + chr(self.hasSigType) + \
            NS(keys.objectType(pubKey)) + NS(blob)
        return keys.verifySignature(pubKey, signature, b)

    def auth_password(self, ident, packet):
        password = getNS(packet[1:])[0]
        return ident.verifyPlainPassword(password)

    # overwrite on the client side            
    def areDone(self):
        return len(self.authenticatedWith)>0
        

class SSHUserAuthClient(service.SSHService):
    name = 'ssh-userauth'
    protocolMessages = None # set later
    def __init__(self, user, instance):
        self.user = user
        self.instance = instance
        self.authenticatedWith = []
        self.triedPublicKeys = []

    def serviceStarted(self):
        self.askForAuth('none', '')

    def askForAuth(self, kind, extraData):
        self.lastAuth = kind
        self.transport.sendPacket(MSG_USERAUTH_REQUEST, NS(self.user) + \
                                  NS(self.instance.name) + NS(kind) + extraData)
    def tryAuth(self, kind):
        f= getattr(self,'auth_%s'%kind, None)
        if f:
            return f()
        
    def ssh_USERAUTH_SUCCESS(self, packet):
        self.transport.setService(self.instance)

    def ssh_USERAUTH_FAILURE(self, packet):
        canContinue, partial = getNS(packet)
        canContinue = canContinue.split(',')
        partial = ord(partial)
        if partial:
            self.authenticatedWith.append(self.lastAuth)
        for method in canContinue:
            if method not in self.authenticatedWith and self.tryAuth(method):
                break

    def ssh_USERAUTH_PK_OK(self, packet):
        if self.lastAuth == 'publickey':
            # this is ok
            privateKey = self.getPrivateKey()
            publicKey = self.lastPublicKey
            keyType =  keys.objectType(privateKey)
            b = NS(self.transport.sessionID) + chr(MSG_USERAUTH_REQUEST) + \
                NS(self.user) + NS(self.instance.name) + NS('publickey') + '\xff' + \
                NS(keyType) + NS(publicKey)
            self.askForAuth('publickey', '\xff' + NS(keyType) + NS(publicKey) + \
                            NS(keys.signData(privateKey, b)))
        elif self.lastAuth == 'password':
            prompt, language, rest = getNS(packet, 2)
            op = getpass('Old Password: ')
            np = getpass(prompt)
            self.askForAuth('password', '\xff'+NS(op)+NS(np))

    def auth_publickey(self):
        publicKey = self.getPublicKey()
        if publicKey:
            self.lastPublicKey = publicKey
            self.triedPublicKeys.append(publicKey)
            keyType = getNS('publicKey')[0]
            self.askForAuth('publickey', '\x00' + NS(keyType) + \
                            NS(publicKey))
            return 1

    def auth_password(self):
        d = self.getPassword()
        d.addCallback(self._cbPassword)
        return 1

    def _cbPassword(self, password):
        self.askForAuth('password', '\x00'+NS(password))

    def getPublicKey(self):
        # XXX try to get public key
        raise NotImplementedError

    def getPrivateKey(self):
        # XXX try to get the private key
        raise NotImplementedError

    def getPassword(self, prompt = None):
        if not prompt:
            prompt = 'Password for %s: ' % self.user
        return defer.succeed(getpass(prompt))

def getpass(prompt = "Password: "):
    import termios, sys
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] = new[3] & ~termios.ECHO          # lflags
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        passwd = raw_input(prompt)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return passwd

MSG_USERAUTH_REQUEST          = 50
MSG_USERAUTH_FAILURE          = 51
MSG_USERAUTH_SUCCESS          = 52
MSG_USERAUTH_BANNER           = 53
MSG_USERAUTH_PASSWD_CHANGEREQ = 60
MSG_USERAUTH_PK_OK            = 60

messages = {}
import userauth
for v in dir(userauth):
    if v[:4]=='MSG_':
        messages[getattr(userauth,v)] = v # doesn't handle doubles

SSHUserAuthServer.protocolMessages = messages
SSHUserAuthClient.protocolMessages = messages
