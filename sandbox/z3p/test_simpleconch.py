# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

from __future__ import nested_scopes
import os, struct, sys
from twisted.conch import identity, error, checkers
from twisted.conch.ssh import keys, transport, factory, userauth, connection, common, session, channel
from twisted.cred import portal
from twisted.cred.credentials import IUsernamePassword
from twisted.internet import reactor, defer, protocol
from twisted.python import log
from twisted.trial import unittest
from Crypto.PublicKey import RSA, DSA

import simpleconch

publicRSA_openssh = "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAGEArzJx8OYOnJmzf4tfBEvLi8DVPrJ3/c9k2I/Az64fxjHf9imyRJbixtQhlH9lfNjUIx+4LmrJH5QNRsFporcHDKOTwTTYLh5KmRpslkYHRivcJSkbh/C+BR3utDS555mV comment"

privateRSA_openssh = """-----BEGIN RSA PRIVATE KEY-----
MIIByAIBAAJhAK8ycfDmDpyZs3+LXwRLy4vA1T6yd/3PZNiPwM+uH8Yx3/YpskSW
4sbUIZR/ZXzY1CMfuC5qyR+UDUbBaaK3Bwyjk8E02C4eSpkabJZGB0Yr3CUpG4fw
vgUd7rQ0ueeZlQIBIwJgbh+1VZfr7WftK5lu7MHtqE1S1vPWZQYE3+VUn8yJADyb
Z4fsZaCrzW9lkIqXkE3GIY+ojdhZhkO1gbG0118sIgphwSWKRxK0mvh6ERxKqIt1
xJEJO74EykXZV4oNJ8sjAjEA3J9r2ZghVhGN6V8DnQrTk24Td0E8hU8AcP0FVP+8
PQm/g/aXf2QQkQT+omdHVEJrAjEAy0pL0EBH6EVS98evDCBtQw22OZT52qXlAwZ2
gyTriKFVoqjeEjt3SZKKqXHSApP/AjBLpF99zcJJZRq2abgYlf9lv1chkrWqDHUu
DZttmYJeEfiFBBavVYIF1dOlZT0G8jMCMBc7sOSZodFnAiryP+Qg9otSBjJ3bQML
pSTqy7c3a2AScC/YyOwkDaICHnnD3XyjMwIxALRzl0tQEKMXs6hH8ToUdlLROCrP
EhQ0wahUTCk1gKA4uPD6TMTChavbh4K63OvbKg==
-----END RSA PRIVATE KEY-----"""

publicDSA_openssh = "ssh-dss AAAAB3NzaC1kc3MAAABBAIbwTOSsZ7Bl7U1KyMNqV13Tu7yRAtTr70PVI3QnfrPumf2UzCgpL1ljbKxSfAi05XvrE/1vfCFAsFYXRZLhQy0AAAAVAM965Akmo6eAi7K+k9qDR4TotFAXAAAAQADZlpTW964haQWS4vC063NGdldT6xpUGDcDRqbm90CoPEa2RmNOuOqi8lnbhYraEzypYH3K4Gzv/bxCBnKtHRUAAABAK+1osyWBS0+P90u/rAuko6chZ98thUSY2kLSHp6hLKyy2bjnT29h7haELE+XHfq2bM9fckDx2FLOSIJzy83VmQ== comment"

privateDSA_openssh = """-----BEGIN DSA PRIVATE KEY-----
MIH4AgEAAkEAhvBM5KxnsGXtTUrIw2pXXdO7vJEC1OvvQ9UjdCd+s+6Z/ZTMKCkv
WWNsrFJ8CLTle+sT/W98IUCwVhdFkuFDLQIVAM965Akmo6eAi7K+k9qDR4TotFAX
AkAA2ZaU1veuIWkFkuLwtOtzRnZXU+saVBg3A0am5vdAqDxGtkZjTrjqovJZ24WK
2hM8qWB9yuBs7/28QgZyrR0VAkAr7WizJYFLT4/3S7+sC6SjpyFn3y2FRJjaQtIe
nqEsrLLZuOdPb2HuFoQsT5cd+rZsz19yQPHYUs5IgnPLzdWZAhUAl1TqdmlAG/b4
nnVchGiO9sML8MM=
-----END DSA PRIVATE KEY-----"""

# note that theTest.fail() will not cause the reactor to stop. If it is
# called inside a DelayedCall, a Deferred callback, or a reactor doRead, then
# it will be turned into a logged error and trial will report it as an ERROR
# instead of a FAILURE.
theTest = None

class ConchTestRealm:
    
    def requestAvatar(self, avatarID, mind, *interfaces):
        theTest.assertEquals(avatarID, 'testuser')
        a = ConchTestAvatar()
        return interfaces[0], a, a.logout

class ConchTestAvatar:
    loggedOut = False
    
    def logout(self):
        loggedOut = True

class ConchTestPublicKeyChecker(checkers.SSHPublicKeyDatabase):
    def checkKey(self, credentials):
        global theTest
        theTest.assertEquals(credentials.username, 'testuser', 'bad username')
        theTest.assertEquals(credentials.blob, keys.getPublicKeyString(data=publicDSA_openssh), 'bad public key')
        return 1

class ConchTestPasswordChecker:
    credentialInterfaces = IUsernamePassword,

    def requestAvatarId(self, credentials):
        global theTest
        theTest.assertEquals(credentials.username, 'testuser', 'bad username')
        theTest.assertEquals(credentials.password, 'testpass', 'bad password')
        return defer.succeed(credentials.username)

class ConchTestSSHChecker(checkers.SSHProtocolChecker):

    def areDone(self, avatarId):
        global theTest
        theTest.assertEquals(avatarId, 'testuser')
        if len(self.successfulCredentials[avatarId]) < 2:
            return 0
        else:
            return 1

class SSHTestBase:

    done = 0
    allowedToError = 0

    def connectionLost(self, reason):
        if self.done:
            return
        global theTest
        if not hasattr(self,'expectedLoseConnection'):
            theTest.fail('unexpectedly lost connection %s\n%s' % (self, reason))
        reactor.crash()

    def receiveError(self, reasonCode, desc):
        global theTest
        reactor.crash()
        self.expectedLoseConnection = 1
        if not self.allowedToError:
            theTest.fail('got disconnect for %s: reason %s, desc: %s' %
                           (self, reasonCode, desc))

    def receiveUnimplemented(self, seqID):
        global theTest
        reactor.crash()
        theTest.fail('got unimplemented: seqid %s'  % seqID)

class SSHTestServer(SSHTestBase, transport.SSHServerTransport): pass

class SSHTestServerConnection(connection.SSHConnection):

    def getChannel(self, ct, ws, mp, d):
        if ct != 'session':
            global theTest
            theTest.fail('should not get %s as a channel type' % ct)
            reactor.crash()
        return SSHTestServerSession(remoteWindow = ws,
                                    remoteMaxPacket = mp,
                                    conn = self)

class SSHTestServerSession(channel.SSHChannel):

    def request_exec(self, data):
        program = common.getNS(data)[0].split()
        log.msg('execing %s' % (program,))
        self.client = session.SSHSessionClient()
        reactor.spawnProcess(session.SSHSessionProtocol(self, self.client), \
                             program[0], program, {}, '/tmp')
        return 1

class SSHTestFactory(factory.SSHFactory):
    noisy = 0

    services = {
        'ssh-userauth':userauth.SSHUserAuthServer,
        'ssh-connection':SSHTestServerConnection
    }

    def buildProtocol(self, addr):
        if hasattr(self, 'proto'):
            global theTest
            reactor.crash()
            theTest.fail('connected twice to factory')
        self.proto = SSHTestServer()
        self.proto.supportedPublicKeys = self.privateKeys.keys()
        self.proto.factory = self
        return self.proto

    def getPublicKeys(self):
        return {
            'ssh-rsa':keys.getPublicKeyString(data=publicRSA_openssh),
            'ssh-dss':keys.getPublicKeyString(data=publicDSA_openssh)
        }

    def getPrivateKeys(self):
        return {
            'ssh-rsa':keys.getPrivateKeyObject(data=privateRSA_openssh),
            'ssh-dss':keys.getPrivateKeyObject(data=privateDSA_openssh)
        }

    def getPrimes(self):
        return {
            2048:[(transport.DH_GENERATOR, transport.DH_PRIME)]
        }

    def getService(self, trans, name):
        return factory.SSHFactory.getService(self, trans, name)

class TrueProtocol(protocol.ProcessProtocol):

    p = 'true'
    def outReceived(self, data):
        global theTest
        reactor.crash()
        theTest.fail("out received in %s protocol" % self.p)

    def errReceived(self, data):
        global theTest
        reactor.crash()
        theTest.fail("err received in %s protocol" % self.p)

    def processEnded(self, reason):
        global theTest
        theTest.sessions.append(self.p)
        theTest.assertEquals(reason.value.exitCode, 0, "true exitcode not 0")
        self.transport.loseConnection()

class FalseProtocol(TrueProtocol):
    p = 'false'

    def processEnded(self, reason):
        global theTest
        theTest.sessions.append(self.p)
        theTest.assertNotEquals(reason.value.exitCode, 0, "false exit code 0")
        self.transport.loseConnection()

class EchoProtocol(TrueProtocol):
    p = 'echo'
    buf = ''
    def outReceived(self, data):
        self.buf += data

    def processEnded(self, reason):
        global theTest
        theTest.sessions.append(self.p)
        theTest.assertEquals(reason.value.exitCode, 0, "echo exit code not 0")
        theTest.assertEquals(self.buf, 'hello\n')
        theTest.assertEquals(theTest.sessions, ['true', 'false', 'echo'])
        self.transport.loseConnection()
        reactor.crash()

class SSHTransportTestCase(unittest.TestCase):

    def tearDown(self):
        self.server.stopListening()

    def testOurServerOurClient(self):
        """test the SSH server against the simpler SSH client
        """
        if os.name != 'posix':
            raise unittest.SkipTest("cannot run on non-posix") # why?
        global theTest
        theTest = self
        realm = ConchTestRealm()
        p = portal.Portal(realm)
        sshpc = ConchTestSSHChecker()
        sshpc.registerChecker(ConchTestPasswordChecker())
        sshpc.registerChecker(ConchTestPublicKeyChecker())
        p.registerChecker(sshpc)
        self.fac = fac = SSHTestFactory()
        fac.portal = p
        theTest.fac = fac
        self.server = reactor.listenTCP(0, fac, interface="127.0.0.1")
        port = self.server.getHost()[2]
        d = defer.Deferred()
        cc = protocol.ClientCreator(reactor, simpleconch.SimpleTransport, d)
        d.addCallback(self._cbSimpleConnected)
        d.addErrback(self._ebFailTest, "failed before connection")
        def _failTest():
            reactor.crash()
            self.fail('test took too long') # logged but caught by reactor
        self.sessions = []
        timeout = reactor.callLater(10, _failTest)
        d = cc.connectTCP('localhost', port)
        d.addErrback(self._ebFailTest)
        reactor.run()
        # test finished.. might have passed, might have failed. Must cleanup.
        fac.proto.done = 1
        fac.proto.transport.loseConnection()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

        try:
            timeout.cancel()
        except: # really just (error.AlreadyCancelled, error.AlreadyCalled)
            pass


    def _ebFailTest(self, reason, where = ''):
        reactor.crash() 
        self.fail(reason)

    def _cbSimpleConnected(self, client):
        kind, key, fp = client.getHostKey()
        self.assertEquals(kind, 'ssh-rsa')
        self.assertEquals(key, keys.getPublicKeyString(data = publicRSA_openssh))
        self.assertEquals(fp, '3d:13:5f:cb:c9:79:8a:93:06:27:65:bc:3d:0b:8f:af')
        d = client.authPublicKey('testuser', privateDSA_openssh)
        d.addCallback(self._cbSimplePublicKey, client)
        d.addErrback(self._ebFailTest)

    def _cbSimplePublicKey(self, r, client):
        if client.isAuthenticated():
            raise FailTest, "client should not be authenticated"
        d = client.authPassword('testuser', 'testpass')
        d.addCallback(self._cbSimplePassword, client)
        d.addErrback(self._ebFailTest)

    def _cbSimplePassword(self, r, client):
        if not client.isAuthenticated():
            raise FailTest, "client should be authenticated"
        d = client.openSession()
        d.addCallback(self._cbSimpleSession, client)
        d.addErrback(self._ebFailTest)

    def _cbSimpleSession(self, sess, client):
        tp = TrueProtocol()
        sess.setClient(tp)
        sess.openExec('true')

        d = client.openSession()
        d.addCallback(self._cbSimpleSession2, client)
        d.addErrback(self._ebFailTest)

    def _cbSimpleSession2(self, sess, client):
        fp = FalseProtocol()
        sess.setClient(fp)
        sess.openExec('false')
        d = client.openSession()
        d.addCallback(self._cbSimpleSession3, client)
        d.addErrback(self._ebFailTest)

    def _cbSimpleSession3(self, sess, client):
        ep = EchoProtocol()
        sess.setClient(ep)
        sess.openExec('echo hello')
