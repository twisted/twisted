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
from twisted.conch import checkers, avatar 
from twisted.conch.error import ConchError
from twisted.conch.ssh import keys, transport, factory, userauth, connection, common, session,channel
from twisted.cred import portal
from twisted.cred.credentials import IUsernamePassword
from twisted.internet import reactor, defer, protocol, error
from twisted.python import log, failure
from twisted.trial import unittest
from Crypto.PublicKey import RSA, DSA

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

publicRSA_lsh = """{KDEwOnB1YmxpYy1rZXkoMTQ6cnNhLXBrY3MxLXNoYTEoMTpuNjU6AJidzg8akh9enh1JrIQyL8mrqfnJT3sBxhDkIFXqjlyN2OK2al2s5mRVNMrhzL7rX8hptPX597nHmfAS65yA85cpKDE6ZTQ6PTiAYykpKQ==}"""

privateRSA_lsh = """(11:private-key(9:rsa-pkcs1(1:n65:\x00\x98\x9d\xce\x0f\x1a\x92\x1f^\x9e\x1dI\xac\x842/\xc9\xab\xa9\xf9\xc9O{\x01\xc6\x10\xe4 U\xea\x8e\\\x8d\xd8\xe2\xb6j]\xac\xe6dU4\xca\xe1\xcc\xbe\xeb_\xc8i\xb4\xf5\xf9\xf7\xb9\xc7\x99\xf0\x12\xeb\x9c\x80\xf3\x97)(1:e4:=8\x80c)(1:d64:h>)i\xb7\xc3z_\x94\xd30\xbd\xdf\xf5\x9d\x8d\xd7\xb4\xb2*\xcb\xef\xae~yq\xb8\x8a\xda\xae\xdf\xa3h\x9a=6{c\xb9\xf4\xa5\xe9\xe0\xf9a\xf5\xe7$*\x83\r\x1e\xcb[\xc8\xda\n\xa1\x94+\x00\x96d\xfb)(1:p33:\x00\xfd\x92\xdf\xdb\xd6\xebU\x82\xc6\x86eq9Dv\x98B\xd6\xfd\xa7\xa8,\x99\x1e\xa3\x88>\xa4A\xb7;i)(1:q33:\x00\x9a\x13\xa3\t\xd1@u\x86\xe9\xdeZym\xa8\x9c\xba\xcb\x18\x8c\xfcwJ*\x08\x0c\xac\xee\x0bU[\xd6\xff)(1:a33:\x00\xc4\xe3w\xe4\xbc\xf1q\x16\x84%D*]\xd0\x8d\xa2\xaf\x99\xff\x11\xf5\x8f\x06\xd5\x8c\xa6FH\xfe\x8e\xea\x8b)(1:b32:qx\xbd\xa6\x88\x13p\x94W\xfd\xbff\x941\xc3\xac\xa8\xaf\xe6\xaavO+\x95\xa7\x06|\x91~\xc5\xc7\xb1)(1:c32:9z\xf1\x80\xbdLE\x8c?\x8f\xd3\xe8\x05\x12\xc2@\xedZ\xec/\xb9\x8c\xdd\x07\xccM\x88g\x05jG2)))"""

publicDSA_lsh = """{KDEwOnB1YmxpYy1rZXkoMzpkc2EoMTpwNjU6AOiMNL79iqUfSqaIHIySHKt4Jlc272yYTzAXmEg77NCgtyfDjuAcHHgwTphBA1l53i/4AAiaUBcU8qPY/Ug/MPcpKDE6cTIxOgDYKP8uLv/m6aUDAA7l5hjMq6Iy7ykoMTpnNjU6ANLKfX/CG7L9o7TQzwLa/X/hb1ZZ+++bySGQep5Ka2lCLm+gff3erqKdxwn5kjqEWq/tXtnSx3rl3TgiwO5R1GEpKDE6eTY1OgDZKD/rhxonz8sugmAcf/wIIhq4M4A+XFOzkEHj0XWHGpjycC8moBWwsIXRuRYCjbl5dA6wVv+xDrf9c6a6GMhhKSkp}"""

privateDSA_lsh = """(11:private-key(3:dsa(1:p65:\x00\xe8\x8c4\xbe\xfd\x8a\xa5\x1fJ\xa6\x88\x1c\x8c\x92\x1c\xabx&W6\xefl\x98O0\x17\x98H;\xec\xd0\xa0\xb7\'\xc3\x8e\xe0\x1c\x1cx0N\x98A\x03Yy\xde/\xf8\x00\x08\x9aP\x17\x14\xf2\xa3\xd8\xfdH?0\xf7)(1:q21:\x00\xd8(\xff..\xff\xe6\xe9\xa5\x03\x00\x0e\xe5\xe6\x18\xcc\xab\xa22\xef)(1:g65:\x00\xd2\xca}\x7f\xc2\x1b\xb2\xfd\xa3\xb4\xd0\xcf\x02\xda\xfd\x7f\xe1oVY\xfb\xef\x9b\xc9!\x90z\x9eJkiB.o\xa0}\xfd\xde\xae\xa2\x9d\xc7\t\xf9\x92:\x84Z\xaf\xed^\xd9\xd2\xc7z\xe5\xdd8"\xc0\xeeQ\xd4a)(1:y65:\x00\xd9(?\xeb\x87\x1a\'\xcf\xcb.\x82`\x1c\x7f\xfc\x08"\x1a\xb83\x80>\\S\xb3\x90A\xe3\xd1u\x87\x1a\x98\xf2p/&\xa0\x15\xb0\xb0\x85\xd1\xb9\x16\x02\x8d\xb9yt\x0e\xb0V\xff\xb1\x0e\xb7\xfds\xa6\xba\x18\xc8a)(1:x20:>\xbb\xe4D\xb9\xb8\xb5\xf8\xf2-}\xf7\x0f\x90`\x968\xd3\x98Q)))"""

class SSHKeysHandlingTestCase(unittest.TestCase):
    """
    test the handling of reading/signing/verifying with RSA and DSA keys
    assumed test keys are in test/
    """

    def testDSA(self):
        """test DSA keys
        """
        self._testKey(publicDSA_openssh, privateDSA_openssh, 'openssh')
        self._testKey(publicDSA_lsh, privateDSA_lsh, 'lsh')

    def testRSA(self):
        """test RSA keys
        """
        self._testKey(publicRSA_openssh, privateRSA_openssh, 'openssh')
        self._testKey(publicRSA_lsh, privateRSA_lsh, 'lsh')

    def _testKey(self, pubData, privData, keyType):
        privKey = keys.getPrivateKeyObject(data = privData)
        pubStr = keys.getPublicKeyString(data = pubData)
        pubKey = keys.getPublicKeyObject(pubStr)
        self._testKeySignVerify(privKey, pubKey)
        self._testKeyFromString(privKey, pubKey, privData, pubData)
        self._testGenerateKey(privKey, pubKey, privData, pubData, keyType)

    def _testKeySignVerify(self, priv, pub):
        testData = 'this is the test data'
        sig = keys.signData(priv, testData)
        self.assert_(keys.verifySignature(priv, sig, testData),
                     'verifying with private %s failed' %
                         keys.objectType(priv))
        self.assert_(keys.verifySignature(pub, sig, testData),
                     'verifying with public %s failed' %
                         keys.objectType(pub))
        self.failIf(keys.verifySignature(priv, sig, 'other data'),
                    'verified bad data with %s' %
                        keys.objectType(priv))
        self.failIf(keys.verifySignature(priv, 'bad sig', testData),
                    'verified badsign with %s' %
                        keys.objectType(priv))

    def _testKeyFromString(self, privKey, pubKey, privData, pubData):
        keyType = keys.objectType(privKey)
        privFS = keys.getPrivateKeyObject(data = privData)
        pubFS = keys.getPublicKeyObject(keys.getPublicKeyString(data=pubData))
        for k in privFS.keydata:
            if getattr(privFS, k) != getattr(privKey, k):
                self.fail('getting %s private key from string failed' % keyType)
        for k in pubFS.keydata:
            if hasattr(pubFS, k):
                if getattr(pubFS, k) != getattr(pubKey, k):
                    self.fail('getting %s public key from string failed' % keyType)

    def _testGenerateKey(self, privKey, pubKey, privData, pubData, keyType):
        self.assertEquals(keys.makePublicKeyString(pubKey, 'comment', keyType), pubData)
        self.assertEquals(keys.makePublicKeyString(privKey, 'comment', keyType), pubData)
        self.assertEquals(keys.makePrivateKeyString(privKey, kind=keyType), privData)
        encData = keys.makePrivateKeyString(privKey, passphrase='test', kind=keyType)
        self.assertEquals(
            keys.getPrivateKeyObject(data = encData,
                                     passphrase = 'test').__getstate__(),
            privKey.__getstate__())

# note that theTest.fail() will not cause the reactor to stop. If it is
# called inside a DelayedCall, a Deferred callback, or a reactor doRead, then
# it will be turned into a logged error and trial will report it as an ERROR
# instead of a FAILURE.
theTest = None

class CrazySubsystem(protocol.Protocol):

    def __init__(self, *args, **kw):
        pass

    def connectionMade(self):
        """
        good ... good
        """

class FalseTransport:

    def __init__(self, p):
        p.makeConnection(self) 
        p.processEnded(failure.Failure(error.ProcessTerminated(255, None, None)))

    def loseConnection(self):
        pass

class EchoTransport:

    def __init__(self, p):
        self.proto = p
        p.makeConnection(self)
        self.closed = 0

    def write(self, data):
        self.proto.outReceived(data)
        self.proto.outReceived('\r\n')

    def loseConnection(self):
        if self.closed: return
        self.closed = 1
        self.proto.inConnectionLost()
        self.proto.outConnectionLost()
        self.proto.errConnectionLost()
        self.proto.processEnded(failure.Failure(error.ProcessTerminated(0, None, None)))

class ErrEchoTransport:

    def __init__(self, p):
        self.proto = p
        p.makeConnection(self)
        self.closed = 0

    def write(self, data):
        self.proto.errReceived(data)
        self.proto.errReceived('\r\n')

    def loseConnection(self):
        if self.closed: return
        self.closed = 1
        self.proto.inConnectionLost()
        self.proto.outConnectionLost()
        self.proto.errConnectionLost()
        self.proto.processEnded(failure.Failure(error.ProcessTerminated(0, None, None)))

class SuperEchoTransport:

    def __init__(self, p):
        self.proto = p
        p.makeConnection(self)
        self.closed = 0

    def write(self, data):
        self.proto.outReceived(data)
        self.proto.outReceived('\r\n')
        self.proto.errReceived(data)
        self.proto.errReceived('\r\n')

    def loseConnection(self):
        if self.closed: return
        self.closed = 1
        self.proto.inConnectionLost()
        self.proto.outConnectionLost()
        self.proto.errConnectionLost()
        self.proto.processEnded(failure.Failure(error.ProcessTerminated(0, None, None)))

class ConchTestRealm:
    
    def requestAvatar(self, avatarID, mind, *interfaces):
        theTest.assertEquals(avatarID, 'testuser')
        a = ConchTestAvatar()
        return interfaces[0], a, a.logout

class ConchTestAvatar(avatar.ConchUser):
    loggedOut = False
    
    def __init__(self):
        avatar.ConchUser.__init__(self)
        self.channelLookup.update({'session': session.SSHSession})
        self.subsystemLookup.update({'crazy': CrazySubsystem})

    def global_foo(self, data):
        global theTest
        theTest.assertEquals(data, 'bar')
        return 1

    def global_foo_2(self, data):
        global theTest
        theTest.assertEquals(data, 'bar2')
        return 1, 'data'

    def logout(self):
        loggedOut = True

class ConchSessionForTestAvatar:

    def __init__(self, avatar):
        theTest.assert_(isinstance(avatar, ConchTestAvatar))
        self.cmd = None
        self.ptyReq = False

    def getPty(self, term, windowSize, attrs):
        log.msg('pty req')
        theTest.assertEquals(term, 'conch-test-term')
        theTest.assertEquals(windowSize, (24, 80, 0, 0))
        self.ptyReq = True

    def openShell(self, proto):
        log.msg('openning shell')
        theTest.assertEquals(self.ptyReq, True)
        self.proto = proto
        EchoTransport(proto)
        self.cmd = 'shell'

    def execCommand(self, proto, cmd):
        theTest.assert_(cmd.split()[0] in ['false', 'echo', 'secho', 'eecho','jumboliah'])
        if cmd == 'jumboliah':
            raise ConchError('bad exec')
        self.cmd = cmd
        self.proto = proto
        f = cmd.split()[0]
        if f == 'false':
            FalseTransport(proto)
        elif f == 'echo':
            t = EchoTransport(proto)
            t.write(cmd[5:])
            t.loseConnection()
        elif f == 'secho':
            t = SuperEchoTransport(proto)
            t.write(cmd[6:])
            t.loseConnection()
        elif f == 'eecho':
            t = ErrEchoTransport(proto)
            t.write(cmd[6:])
            t.loseConnection()
        

    def closed(self):
        global theTest
        log.msg('closing cmd %s' % self.cmd)
        if self.cmd == 'echo hello':
            rwl = self.proto.session.remoteWindowLeft
            theTest.assertEquals(rwl, 4)
        elif self.cmd == 'eecho hello':
            rwl = self.proto.session.remoteWindowLeft
            theTest.assertEquals(rwl, 4)
        self.proto.transport.loseConnection()

from twisted.python import components
components.registerAdapter(ConchSessionForTestAvatar, ConchTestAvatar, session.ISession)

class ConchTestPublicKeyChecker(checkers.SSHPublicKeyDatabase):
    def checkKey(self, credentials):
        global theTest
        theTest.assertEquals(credentials.username, 'testuser', 'bad username')
        theTest.assertEquals(credentials.blob, keys.getPublicKeyString('dsa_test.pub'), 'bad public key')
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

class SSHTestClientAuth(userauth.SSHUserAuthClient):

    hasTriedNone = 0 # have we tried the 'none' auth yet?
    canSucceedPublicKey = 0 # can we succed with this yet?
    canSucceedPassword = 0

    def ssh_USERAUTH_SUCCESS(self, packet):
        if not self.canSucceedPassword and self.canSucceedPublicKey:
            global theTest
            reactor.crash()
            theTest.fail('got USERAUTH_SUCESS before password and publickey')
        userauth.SSHUserAuthClient.ssh_USERAUTH_SUCCESS(self, packet)

    def getPassword(self):
        self.canSucceedPassword = 1
        return defer.succeed('testpass')

    def getPrivateKey(self):
        self.canSucceedPublicKey = 1
        return defer.succeed(keys.getPrivateKeyObject('dsa_test'))

    def getPublicKey(self):
        return keys.getPublicKeyString('dsa_test.pub')

class SSHTestClient(SSHTestBase, transport.SSHClientTransport):

    def verifyHostKey(self, key, fp):
        global theTest
        theTest.assertEquals(key, keys.getPublicKeyString(data = publicRSA_openssh))
        theTest.assertEquals(fp,'3d:13:5f:cb:c9:79:8a:93:06:27:65:bc:3d:0b:8f:af')
        return defer.succeed(1)

    def connectionSecure(self):
        self.requestService(SSHTestClientAuth('testuser',SSHTestClientConnection()))

class SSHTestClientFactory(protocol.ClientFactory):
    noisy = 0

    def buildProtocol(self, addr):
        self.client = SSHTestClient()
        return self.client

    def clientConnectionFailed(self, connector, reason):
        global theTest
        theTest.fail('connection between client and server failed!')
        reactor.crash()

class SSHTestClientConnection(connection.SSHConnection):

    name = 'ssh-connection'
    results = 0
    totalResults = 8 

    def serviceStarted(self):
        self.openChannel(SSHUnknownChannel(conn = self))
        self.openChannel(SSHTestFailExecChannel(conn = self))
        self.openChannel(SSHTestFalseChannel(conn = self))
        self.openChannel(SSHTestEchoChannel(localWindow=4, localMaxPacket=5, conn = self))
        self.openChannel(SSHTestErrChannel(localWindow=4, localMaxPacket=5, conn = self))
        self.openChannel(SSHTestMaxPacketChannel(localWindow=12, localMaxPacket=1, conn = self))
        self.openChannel(SSHTestShellChannel(conn = self))
        self.openChannel(SSHTestSubsystemChannel(conn = self))

    def addResult(self):
        self.results += 1
        log.msg('got %s of %s results' % (self.results, self.totalResults))
        if self.results == self.totalResults:
            self.transport.expectedLoseConnection = 1
            theTest.fac.proto.expectedLoseConnection = 1
            #self.loseConnection()
            self.serviceStopped()
            reactor.crash()

class SSHUnknownChannel(channel.SSHChannel):

    name = 'crazy-unknown-channel'

    def openFailed(self, reason):
        """
        good .... good
        """
        log.msg('unknown open failed')
        log.flushErrors()
        self.conn.addResult()

    def channelOpen(self, ignored):
        global theTest
        theTest.fail("opened unknown channel")
        reactor.crash()

class SSHTestFailExecChannel(channel.SSHChannel):

    name = 'session'

    def openFailed(self, reason):
        global theTest
        theTest.fail('fail exec open failed: %s' % reason)
        reactor.crash()

    def channelOpen(self, ignore):
        d = self.conn.sendRequest(self, 'exec', common.NS('jumboliah'), 1)
        d.addCallback(self._cbRequestWorked)
        d.addErrback(lambda x,s=self:log.flushErrors() and s.conn.addResult())
        log.msg('opened fail exec')

    def _cbRequestWorked(self, ignored):
        global theTest
        theTest.fail('fail exec succeeded')
        reactor.crash()

class SSHTestFalseChannel(channel.SSHChannel):

    name = 'session'

    def openFailed(self, reason):
        global theTest
        theTest.fail('false open failed: %s' % reason)
        reactor.crash()

    def channelOpen(self, ignored):
        d = self.conn.sendRequest(self, 'exec', common.NS('false'), 1)
        d.addCallback(self._cbRequestWorked)
        d.addErrback(self._ebRequestFailed)
        log.msg('opened false')

    def _cbRequestWorked(self, ignored):
        pass

    def _ebRequestFailed(self, reason):
        global theTest
        theTest.fail('false exec failed: %s' % reason)
        reactor.crash()

    def dataReceived(self, data):
        global theTest
        theTest.fail('got data when using false')
        reactor.crash()

    def request_exit_status(self, status):
        status = struct.unpack('>L', status)[0]
        if status == 0:
            global theTest
            theTest.fail('false exit status was 0')
            reactor.crash()
        log.msg('finished false')
        self.conn.addResult()
        self.loseConnection()
        return 1

class SSHTestEchoChannel(channel.SSHChannel):

    name = 'session'
    testBuf = ''
    eofCalled = 0

    def openFailed(self, reason):
        global theTest
        theTest.fail('echo open failed: %s' % reason)
        reactor.crash()

    def channelOpen(self, ignore):
        d = self.conn.sendRequest(self, 'exec', common.NS('echo hello'), 1)
        d.addErrback(self._ebRequestFailed)
        log.msg('opened echo')

    def _ebRequestFailed(self, reason):
        global theTest
        theTest.fail('echo exec failed: %s' % reason)
        reactor.crash()

    def dataReceived(self, data):
        self.testBuf += data

    def errReceived(self, dataType, data):
        theTest.fail('echo channel got extended data')
        reactor.crash()

    def request_exit_status(self, status):
        self.status = struct.unpack('>L', status)[0]
        
    def eofReceived(self):
        log.msg('eof received')
        self.eofCalled = 1

    def closed(self):
        global theTest
        if self.status != 0:
            theTest.fail('echo exit status was not 0: %i' % self.status)
            reactor.crash()
        if self.testBuf != "hello\r\n":
            theTest.fail('echo did not return hello: %s' % repr(self.testBuf))
            reactor.crash()
        theTest.assertEquals(self.localWindowLeft, 4)
        theTest.assert_(self.eofCalled)
        log.msg('finished echo')
        self.conn.addResult()
        self.loseConnection()
        return 1

class SSHTestErrChannel(channel.SSHChannel):

    name = 'session'
    testBuf = ''
    eofCalled = 0

    def openFailed(self, reason):
        global theTest
        theTest.fail('err open failed: %s' % reason)
        reactor.crash()

    def channelOpen(self, ignore):
        d = self.conn.sendRequest(self, 'exec', common.NS('eecho hello'), 1)
        d.addErrback(self._ebRequestFailed)
        log.msg('opened err')

    def _ebRequestFailed(self, reason):
        global theTest
        theTest.fail('err exec failed: %s' % reason)
        reactor.crash()

    def dataReceived(self, data):
        theTest.fail('err channel got regular data: %s' % repr(data))
        reactor.crash()

    def extReceived(self, dataType, data):
        theTest.assertEquals(dataType, connection.EXTENDED_DATA_STDERR)
        self.testBuf += data

    def request_exit_status(self, status):
        self.status = struct.unpack('>L', status)[0]
        
    def eofReceived(self):
        log.msg('eof received')
        self.eofCalled = 1

    def closed(self):
        global theTest
        if self.status != 0:
            theTest.fail('echo exit status was not 0: %i' % self.status)
            reactor.crash()
        if self.testBuf != "hello\r\n":
            theTest.fail('err did not return hello: %s' % repr(self.testBuf))
            reactor.crash()
        theTest.assertEquals(self.localWindowLeft, 4)
        theTest.assert_(self.eofCalled)
        log.msg('finished err')
        self.conn.addResult()
        self.loseConnection()
        return 1

class SSHTestMaxPacketChannel(channel.SSHChannel):

    name = 'session'
    testBuf = ''
    testExtBuf = ''
    eofCalled = 0

    def openFailed(self, reason):
        global theTest
        theTest.fail('max packet open failed: %s' % reason)
        reactor.crash()

    def channelOpen(self, ignore):
        d = self.conn.sendRequest(self, 'exec', common.NS('secho hello'), 1)
        d.addErrback(self._ebRequestFailed)
        log.msg('opened max packet')

    def _ebRequestFailed(self, reason):
        global theTest
        theTest.fail('max packet exec failed: %s' % reason)
        reactor.crash()

    def dataReceived(self, data):
        self.testBuf += data

    def extReceived(self, dataType, data):
        theTest.assertEquals(dataType, connection.EXTENDED_DATA_STDERR)
        self.testExtBuf += data

    def request_exit_status(self, status):
        self.status = struct.unpack('>L', status)[0]
        
    def eofReceived(self):
        log.msg('eof received')
        self.eofCalled = 1

    def closed(self):
        global theTest
        if self.status != 0:
            theTest.fail('echo exit status was not 0: %i' % self.status)
            reactor.crash()
        theTest.assertEquals(self.testBuf, 'hello\r\n')
        theTest.assertEquals(self.testExtBuf, 'hello\r\n')
        theTest.assertEquals(self.localWindowLeft, 12)
        theTest.assert_(self.eofCalled)
        log.msg('finished max packet')
        self.conn.addResult()
        self.loseConnection()
        return 1

class SSHTestShellChannel(channel.SSHChannel):
    
    name = 'session'
    testBuf = ''
    eofCalled = 0

    def openFailed(self, reason):
        theTest.fail('shell open failed: %s' % reason)
        reactor.crash()

    def channelOpen(self, ignored):
        data = session.packRequest_pty_req('conch-test-term', (24, 80, 0, 0), '')
        d = self.conn.sendRequest(self, 'pty-req', data, 1)
        d.addCallback(self._cbPtyReq)
        d.addErrback(self._ebPtyReq)
        log.msg('opened shell')

    def _cbPtyReq(self, ignored):
        d = self.conn.sendRequest(self, 'shell', '', 1)
        d.addCallback(self._cbShellOpen)
        d.addErrback(self._ebShellOpen)

    def _ebPtyReq(self, reason):
        theTest.fail('pty request failed: %s' % reason)
        reactor.crash()

    def _cbShellOpen(self, ignored):
        self.write('testing the shell!')
        self.loseConnection()

    def _ebShellOpen(self, reason):
        theTest.fail('shell request failed: %s' % reason)
        reactor.crash()

    def dataReceived(self, data):
        self.testBuf += data

    def request_exit_status(self, status):
        self.status = struct.unpack('>L', status)[0]

    def eofReceived(self):
        self.eofCalled = 1

    def closed(self):
        log.msg('calling shell closed')
        if self.status != 0:
            log.msg('shell exit status was not 0: %i' % self.status)
            reactor.crash()
        theTest.assertEquals(self.testBuf, 'testing the shell!\r\n')
        theTest.assert_(self.eofCalled)
        self.conn.addResult()
        self.loseConnection()

class SSHTestSubsystemChannel(channel.SSHChannel):

    name = 'session'

    def openFailed(self, reason):
        global theTest
        theTest.fail('subsystem open failed: %s' % reason)
        reactor.crash()

    def channelOpen(self, ignore):
        d = self.conn.sendRequest(self, 'subsystem', common.NS('not-crazy'), 1)
        d.addCallback(self._cbRequestWorked)
        d.addErrback(self._ebRequestFailed)


    def _cbRequestWorked(self, ignored):
        global theTest
        theTest.fail('opened non-crazy subsystem')
        reactor.crash()

    def _ebRequestFailed(self, ignored):
        d = self.conn.sendRequest(self, 'subsystem', common.NS('crazy'), 1)
        d.addCallback(self._cbRealRequestWorked)
        d.addErrback(self._ebRealRequestFailed)

    def _cbRealRequestWorked(self, ignored):
        d1 = self.conn.sendGlobalRequest('foo', 'bar', 1)
        d1.addErrback(self._ebFirstGlobal)

        d2 = self.conn.sendGlobalRequest('foo-2', 'bar2', 1)
        d2.addCallback(lambda x,s=self: theTest.assertEquals(x, 'data'))
        d2.addErrback(self._ebSecondGlobal)
        
        d3 = self.conn.sendGlobalRequest('bar', 'foo', 1)
        d3.addCallback(self._cbThirdGlobal)
        d3.addErrback(lambda x,s=self: s.conn.addResult() and s.loseConnection())

    def _ebRealRequestFailed(self, reason):
        global theTest
        theTest.fail('opening crazy subsystem failed: %s' % reason)
        reactor.crash()

    def _ebFirstGlobal(self, reason):
        global theTest
        theTest.fail('first global request failed: %s' % reason)
        reactor.crash()

    def _ebSecondGlobal(self, reason):
        global theTest
        theTest.fail('second global request failed: %s' % reason)
        reactor.crash()

    def _cbThirdGlobal(self, ignored):
        global theTest
        theTest.fail('second global request succeeded')
        reactor.crash()

class SSHTestFactory(factory.SSHFactory):
    noisy = 0

    services = {
        'ssh-userauth':userauth.SSHUserAuthServer,
        'ssh-connection':connection.SSHConnection
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

class SSHTestOpenSSHProcess(protocol.ProcessProtocol):

    buf = ''
    done = 0

    def outReceived(self, data):
        self.buf += data
        theTest.fac.proto.expectedLoseConnection = 1

    def errReceived(self, data):
        print "ERR(ssh): '%s'" % data

    def processEnded(self, reason):
        global theTest
        self.done = 1
        theTest.assertEquals(reason.value.exitCode, 0, 'exit code was not 0: %s' % reason.value.exitCode)
        self.buf = self.buf.replace('\r\n', '\n')
        theTest.assertEquals(self.buf, 'goodbye\n')

class SSHTransportTestCase(unittest.TestCase):

    def setUp(self):
        open('rsa_test','w').write(privateRSA_openssh)
        open('rsa_test.pub','w').write(publicRSA_openssh)
        open('dsa_test.pub','w').write(publicDSA_openssh)
        open('dsa_test','w').write(privateDSA_openssh)
        os.chmod('dsa_test', 33152)
        os.chmod('rsa_test', 33152)
        open('kh_test','w').write('localhost '+publicRSA_openssh)

    def tearDown(self):
        for f in ['rsa_test','rsa_test.pub','dsa_test','dsa_test.pub', 'kh_test']:
            os.remove(f)
        self.server.stopListening()

    def testOurServerOurClient(self):
        """test the SSH server against the SSH client
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
        fac = SSHTestFactory()
        fac.portal = p
        theTest.fac = fac
        self.server = reactor.listenTCP(0, fac, interface="127.0.0.1")
        port = self.server.getHost().port
        cfac = SSHTestClientFactory()
        def _failTest():
            reactor.crash()
            self.fail('test took too long') # logged but caught by reactor
        timeout = reactor.callLater(10, _failTest)
        reactor.connectTCP('localhost', port, cfac)

        reactor.run()

        # test finished.. might have passed, might have failed. Must cleanup.
        fac.proto.done = 1
        cfac.client.done = 1
        fac.proto.transport.loseConnection()
        cfac.client.transport.loseConnection()
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

        try:
            timeout.cancel()
        except: # really just (error.AlreadyCancelled, error.AlreadyCalled)
            pass

    def testOurServerOpenSSHClient(self):
        """test the SSH server against the OpenSSH client
        """
        if os.name != 'posix':
            raise unittest.SkipTest("cannot run on non-posix")
        cmdline = ('ssh -2 -l testuser -p %i '
                   '-oUserKnownHostsFile=kh_test '
                   '-oPasswordAuthentication=no '
                   # Always use the RSA key, since that's the one in kh_test.
                   '-oHostKeyAlgorithms=ssh-rsa '
                   '-i dsa_test '
                   'localhost '
                   'echo goodbye')
        global theTest
        theTest = self
        realm = ConchTestRealm()
        p = portal.Portal(realm)
        p.registerChecker(ConchTestPublicKeyChecker())
        fac = SSHTestFactory()
        fac.portal = p
        theTest.fac = fac
        self.server = reactor.listenTCP(0, fac, interface="127.0.0.1")
        port = self.server.getHost().port
        ssh_path = None
        for p in ['/usr', '', '/usr/local']:
            if os.path.exists(p+'/bin/ssh'):
                ssh_path = p+'/bin/ssh'
                break
        if not ssh_path:
            log.msg('skipping test, cannot find ssh')
            raise unittest.SkipTest, 'skipping test, cannot find ssh'
        cmds = (cmdline % port).split()
        p = SSHTestOpenSSHProcess()
        def _failTest():
            try:
                os.kill(p.transport.pid, 9)
            except OSError:
                pass
            try:
                fac.proto.transport.loseConnection()
            except AttributeError:
                pass
            reactor.iterate(0.1)
            reactor.iterate(0.1)
            reactor.iterate(0.1)
            p.done = 1
            self.fail('test took too long')
        timeout = reactor.callLater(10, _failTest)
        reactor.spawnProcess(p, ssh_path, cmds)
        # wait for process to finish
        while not p.done:
            reactor.iterate(0.1)

        # cleanup
        fac.proto.done = 1
        fac.proto.transport.loseConnection()
        reactor.iterate()

        try:
            timeout.cancel()
        except:
            pass

