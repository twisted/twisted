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

"""Implementation of the ssh-userauth service.  Currently implemented authentication types are public-key and password.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import os.path, base64, struct
from twisted import cred
from twisted.conch import error
from twisted.internet import app, defer, reactor
from twisted.python import failure, log
from common import NS, getNS, MP
import keys, transport, service

class SSHUserAuthServer(service.SSHService):
    name = 'ssh-userauth'
    loginTimeout = 10 * 60 * 60 # 10 minutes before we disconnect them
    attemptsBeforeDisconnect = 20 # number of attempts to allow before a disconnect
    protocolMessages = None # set later
    supportedMethods = ['publickey', 'password']

    def serviceStarted(self):
        self.supportedAuthentications = self.supportedMethods[:] 
        self.authenticatedWith = []
        self.loginAttempts = 0
        self.user = None
        self.nextService = None
        self.identity = None

        if not self.transport.isEncrypted('out'):
            self.supportedAuthentications.remove('password')
            if 'keyboard-interactive' in self.supportedAuthentications:
                self.supportedAuthentications.remove('keyboard-interactive')
            # don't let us transport password in plaintext
        self.cancelLoginTimeout = reactor.callLater(self.loginTimeout,
                                                    self.transport.sendDisconnect,
                                                    transport.DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE,
                                                    'you took too long')

    def tryAuth(self, kind, user, data):
        log.msg('%s trying auth %s' % (user, kind))
        if kind not in self.supportedAuthentications:
            return defer.fail(error.ConchError('unsupported authentication, failing'))
        d = self.transport.factory.authorizer.getIdentityRequest(user)
        d.pause()
        d.addCallback(self._cbTryAuth, kind, data)
        return d

    def _cbTryAuth(self, identity, kind, data):
        self.identity = identity
        kind = kind.replace('-', '_')
        f = getattr(self,'auth_%s'%kind, None)
        if f:
            return f(identity, data)
        raise error.ConchError('bad auth type: %s' % kind) # this should make it err back

    def ssh_USERAUTH_REQUEST(self, packet):
        user, nextService, method, rest = getNS(packet, 3)
        if user != self.user or nextService != self.nextService:
            self.authenticatedWith = [] # clear auth state
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
            self.cancelLoginTimeout.cancel()
            self.transport.sendPacket(MSG_USERAUTH_SUCCESS, '')
            self.transport.authenticatedUser = self.identity
            self.transport.setService(self.transport.factory.services[self.nextService]())
        else:
            self.transport.sendPacket(MSG_USERAUTH_FAILURE, NS(','.join(self.supportedAuthentications))+'\xff')

    def _ebBadAuth(self, reason):
        if self.method != 'none': # ignore 'none' as a method
            log.msg('%s failed auth %s' % (self.user, self.method))
            log.msg('potential reason: %s' % reason)
            self.loginAttempts += 1
            if self.loginAttempts > self.attemptsBeforeDisconnect:
                self.transport.sendDisconnect(transport.DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE,
                                              'too many bad auths')
                return -1
        self.transport.sendPacket(MSG_USERAUTH_FAILURE, NS(','.join(self.supportedAuthentications))+'\x00')
        return -1

    def auth_publickey(self, ident, packet):
        if not getattr(ident, 'validatePublicKey'):
            return defer.fail(error.ConchError('identity does not have validatePublicKey'))
        hasSig = ord(packet[0])
        self.hasSigType = hasSig # protocol impl.s differ in this
        algName, blob, rest = getNS(packet[1:], 2)
        if hasSig:
            d = ident.validatePublicKey(blob)
            d.addCallback(self._cbToVerifySig, ident, blob, getNS(rest)[0])
            return d
        else:
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

    def auth_keyboard_interactive(self, ident, packet):
        if hasattr(self, '_pamDeferred'):
            return defer.fail(error.ConchError('cannot run kbd-int twice at once'))
        d = pamauth.pamAuthenticate('ssh', ident.name, self._pamConv)
        return d

    def _pamConv(self, items):
        resp = []
        for message, kind in items:
            if kind == 1: # password
                resp.append((message, 0))
            elif kind == 2: # text
                resp.append((message, 1))
            elif kind in (3, 4):
                return defer.fail(error.ConchError('cannot handle PAM 3 or 4 messages'))
            else:
                return defer.fail(error.ConchError('bad PAM auth kind %i' % kind))
        packet = NS('')+NS('')+NS('')
        packet += struct.pack('>L', len(resp))
        for prompt, echo in resp:
            packet += NS(prompt)
            packet += chr(echo)
        self.transport.sendPacket(MSG_USERAUTH_INFO_REQUEST, packet)
        self._pamDeferred = defer.Deferred()
        return self._pamDeferred

    def ssh_USERAUTH_INFO_RESPONSE(self, packet):
        if not self.identity:
            return defer.fail(error.ConchError('bad username'))
        d = self._pamDeferred
        del self._pamDeferred
        try:
            resp = []
            numResps = struct.unpack('>L', packet[:4])[0]
            packet = packet[4:]
            while packet:
                response, packet = getNS(packet)
                resp.append((response, 0))
            assert len(resp) == numResps
        except:
            d.errback(failure.Failure())
        else:
            d.callback(resp)
            

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
        self.ssh_USERAUTH_SUCCESS = lambda *a: None # ignore these

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
            if not privateKey:
                self.askForAuth('publickey', '\xff'+NS('')+NS('')+NS(''))
                # this should fail, we'll move on
                return
            publicKey = self.lastPublicKey
            keyType =  keys.objectType(privateKey)
            b = NS(self.transport.sessionID) + chr(MSG_USERAUTH_REQUEST) + \
                NS(self.user) + NS(self.instance.name) + NS('publickey') + '\xff' + \
                NS(keyType) + NS(publicKey)
            self.askForAuth('publickey', '\xff' + NS(keyType) + NS(publicKey) + \
                            NS(keys.signData(privateKey, b)))
        elif self.lastAuth == 'password':
            prompt, language, rest = getNS(packet, 2)
            self._oldPass = self._newPass = None
            op = self.getPassword('Old Password: ').addCallback(self._setOldPass)
            np = self.getPassword(prompt).addCallback(self._setNewPass)
        elif self.lastAuth == 'keyboard-interactive':
            return self.ssh_USERAUTH_INFO_RESPONSE(packet)

    def _setOldPass(self, op):
        if self._newPass:
            np = self._newPass
            self._newPass = None
            self.askForAuth('password', '\xff'+NS(op)+NS(np))
        else:
            self._oldPass = op

    def _setNewPass(self, np):
        if self._oldPass:
            op = self._oldPass
            self._oldPass = None
            self.askForAuth('password', '\xff'+NS(op)+NS(np))
        else:
            self._newPass = np

    def auth_publickey(self):
        publicKey = self.getPublicKey()
        if publicKey:
            self.lastPublicKey = publicKey
            self.triedPublicKeys.append(publicKey)
            keyType = getNS(publicKey)[0]
            log.msg('using key of type %s' % keyType)
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
MSG_USERAUTH_INFO_REQUEST     = 60
MSG_USERAUTH_INFO_RESPONSE    = 61
MSG_USERAUTH_PK_OK            = 60

messages = {}
import userauth
for v in dir(userauth):
    if v[:4]=='MSG_':
        messages[getattr(userauth,v)] = v # doesn't handle doubles

SSHUserAuthServer.protocolMessages = messages
SSHUserAuthClient.protocolMessages = messages

try:
    import pamauth
except:
    pass
else:
    SSHUserAuthServer.supportedMethods.append('keyboard-interactive')
