
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

import os
from twisted.conch import identity
from twisted.conch.ssh import keys, transport, factory, userauth
from twisted.cred import authorizer
from twisted.internet import reactor, defer, app
from pyunit import unittest

publicRSA = "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAEEAtGjpLkkSunM1pejcYuIPPH4vO/Duf734AKqjl2n7a4jhRJ8XRdRpw1+YZlCvQ4JJCD5wc74RWukctaO1Nkjz7w== Paul@MOO"

privateRSA = """-----BEGIN RSA PRIVATE KEY-----
MIIBNwIBAAJBALRo6S5JErpzNaXo3GLiDzx+Lzvw7n+9+ACqo5dp+2uI4USfF0XU
acNfmGZQr0OCSQg+cHO+EVrpHLWjtTZI8+8CASMCQAUnkaI8miKVk9GKT3CKHbFF
bxBXV0V6dMzRrOcRqBkD3NzN7Am6JCigGKXkUI9XywW94zCGCE+ZTLKDI+ZQU0sC
IQDoDLiPtxHzeS2S5BVL5lUb+7dZGfH6u1mb0ApLgk5bTwIhAMcHv0I6T4S8TqbU
BF/ELGtDkQe3ePO9mgR9q4E2/zVhAiANQo40GRb3+Eu/QDu7Mbu4dMimAXuKq564
ckm7LAR6PwIgYKv9z7XsG+ZvWFhZ5V9IxmKlh2e+Z8J+Ai5pPsLw/KsCIF0pE6qv
cXe26viSsgdUpS7mgSJABCwOYRBE+BlwH2tU
-----END RSA PRIVATE KEY-----"""

publicDSA = "ssh-dss AAAAB3NzaC1kc3MAAABBAIbwTOSsZ7Bl7U1KyMNqV13Tu7yRAtTr70PVI3QnfrPumf2UzCgpL1ljbKxSfAi05XvrE/1vfCFAsFYXRZLhQy0AAAAVAM965Akmo6eAi7K+k9qDR4TotFAXAAAAQADZlpTW964haQWS4vC063NGdldT6xpUGDcDRqbm90CoPEa2RmNOuOqi8lnbhYraEzypYH3K4Gzv/bxCBnKtHRUAAABAK+1osyWBS0+P90u/rAuko6chZ98thUSY2kLSHp6hLKyy2bjnT29h7haELE+XHfq2bM9fckDx2FLOSIJzy83VmQ== Paul@MOO"

privateDSA = """-----BEGIN DSA PRIVATE KEY-----
MIH4AgEAAkEAhvBM5KxnsGXtTUrIw2pXXdO7vJEC1OvvQ9UjdCd+s+6Z/ZTMKCkv
WWNsrFJ8CLTle+sT/W98IUCwVhdFkuFDLQIVAM965Akmo6eAi7K+k9qDR4TotFAX
AkAA2ZaU1veuIWkFkuLwtOtzRnZXU+saVBg3A0am5vdAqDxGtkZjTrjqovJZ24WK
2hM8qWB9yuBs7/28QgZyrR0VAkAr7WizJYFLT4/3S7+sC6SjpyFn3y2FRJjaQtIe
nqEsrLLZuOdPb2HuFoQsT5cd+rZsz19yQPHYUs5IgnPLzdWZAhUAl1TqdmlAG/b4
nnVchGiO9sML8MM=
-----END DSA PRIVATE KEY-----"""

class SSHKeysHandlingTestCase(unittest.TestCase):
    """
    test the handling of reading/signing/verifying with RSA and DSA keys
    assumed test keys are in test/
    """

    def setUp(self):
        open('rsa_test','w').write(privateRSA)
        open('rsa_test.pub','w').write(publicRSA)
        open('dsa_test.pub','w').write(publicDSA)
        open('dsa_test','w').write(privateDSA)

    def tearDown(self):
        for f in ['rsa_test','rsa_test.pub','dsa_test','dsa_test.pub']:
            os.remove(f)

    def testDSA(self):
        privKey = keys.getPrivateKeyObject('dsa_test')
        pubKey = keys.getPublicKeyObject('dsa_test.pub')
        self._testKey(privKey, pubKey)
        self._testKeyFromString(privKey, pubKey, privateDSA, publicDSA)

    def testRSA(self):
        privKey = keys.getPrivateKeyObject('rsa_test')
        pubKey = keys.getPublicKeyObject('rsa_test.pub')
        self._testKey(privKey, pubKey)
        self._testKeyFromString(privKey, pubKey, privateRSA, publicRSA)

    def _testKey(self, priv, pub):
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
        pubFS = keys.getPublicKeyObject(b64data = pubData)
        self.assert_(privFS.__dict__ == privKey.__dict__,
                     'getting %s private key from string failed' % keyType)
        self.assert_(pubFS.__dict__ == pubKey.__dict__,
                     'getting %s public key from string failed' % keyType)

theTest = None

class ConchTestIdentity(identity.ConchIdentity):

    def validatePublicKey(self, pubKey):
        global theTest
        theTest.assert_(pubKey==keys.getPublicKeyString('dsa_test.pub'), 'bad public key')
        return defer.succeed(1)

    def verifyPlainPassword(self, password):
        global theTest
        theTest.assert_(password == 'testpass', 'bad password')
        return defer.succeed(1)

class ConchTestAuthorizer(authorizer.Authorizer):
    
    def addIdentity(self, ident):
        self.ident = ident

    def getIdentityRequest(self, name):
        global theTest
        theTest.assert_(name == 'testuser')
        return defer.succeed(self.ident)

class SSHTestBase:

    allowedToError = 0

    def connectionLost(self):
        global theTest
        if not hasattr(self,'expectedLoseConnection'):
            theTest.reactorRunning = 0
            theTest.fail('unexpectedly lost connection %s' % self)
        theTest.reactorRunning = 0

    def receiveError(self, reasonCode, desc):
        global theTest
        theTest.reactorRunning = 0
        self.expectedLoseConnection = 1
        if not self.allowedToError:
            theTest.fail('got disconnect for %s: reason %s, desc: %s' %
                           (self, reasonCode, desc))

    def receiveUnimplemented(self, seqID):
        global theTest
        theTest.reactorRunning = 0
        theTest.fail('got unimplemented: seqid %s'  % seqID)

class SSHTestServer(SSHTestBase, transport.SSHServerTransport): pass

class SSHTestServerAuth(userauth.SSHUserAuthServer):

    def areDone(self):
        return len(self.authenticatedWith)==2

class SSHTestClientAuth(userauth.SSHUserAuthClient):

    hasTriedNone = 0 # have we tried the 'none' auth yet?
    canSucceedPublicKey = 0 # can we succed with this yet?
    canSucceedPassword = 0
    
    def ssh_USERAUTH_SUCCESS(self, packet):
        if not self.canSucceedPassword and self.canSucceedPublicKey:
            global theTest
            theTest.reactorRunning = 0
            theTest.fail('got USERAUTH_SUCESS before password and publickey')
        userauth.SSHUserAuthClient.ssh_USERAUTH_SUCCESS(self, packet)
 
    def getPassword(self):
        self.canSucceedPassword = 1
        return defer.succeed('testpass')

    def getPrivateKey(self):
        self.canSucceedPublicKey = 1
        return keys.getPrivateKeyObject('dsa_test')

    def getPublicKey(self):
        return keys.getPublicKeyString('dsa_test.pub')

class SSHTestClient(SSHTestBase, transport.SSHClientTransport):

    def checkFingerprint(self, fp):
        global theTest
        theTest.assertEquals(fp,'34:f1:6f:02:29:ad:17:f9:8f:96:8a:9b:94:c7:49:43')
        return 1

    def connectionSecure(self):
        self.requestService(SSHTestClientAuth('testuser',SSHTestConnection()))

class SSHTestConnection:

    name = 'ssh-connection'

    def serviceStarted(self):
        #self.transport.expectedLostConnection = 1
        if not hasattr(self.transport, 'factory'):
            # make the client end the connection
            global theTest
            theTest.reactorRunning = 0

class SSHTestFactory(factory.SSHFactory):

    services = {
        'ssh-userauth':SSHTestServerAuth,
        'ssh-connection':SSHTestConnection
    }

    def buildProtocol(self, addr):
        if hasattr(self, 'proto'):
            global theTest
            theTest.reactorRunning = 0
            theTest.fail('connected twice to factory')
        self.proto = SSHTestServer()
        self.proto.supportedPublicKeys = self.privateKeys.keys()
        self.proto.factory = self
        return self.proto

    def getPublicKeys(self):
        return {
            'ssh-rsa':keys.getPublicKeyString('rsa_test.pub'),
            'ssh-dss':keys.getPublicKeyString('dsa_test.pub')
        }

    def getPrivateKeys(self):
        return {
            'ssh-rsa':keys.getPrivateKeyObject('rsa_test'),
            'ssh-dss':keys.getPrivateKeyObject('dsa_test')
        }

    def getPrimes(self):
        return {
            2048:[(transport.DH_GENERATOR, transport.DH_PRIME)]
        }

class SSHFailureTestClient(SSHTestBase, transport.SSHClientTransport):

    numFailureKinds = 8 # the number of failure tests we can do

    def __init__(self, failureKind):
        """
        failure kinds:
        0: can't match kex algs (transport)
        1: can't match key algs (transport)
        2: can't match ciphers (transport)
        3: can't match macs (transport)
        4: can't match compressions (transport)
        5: incorrect compression (transport)
        6: incorrect encryption (transport)
        7: incorrect MAC (transport)
        8: bad next service (transport)
        9: bad username (userauth)
        10: bad publickey for verify (userauth)
        11: bad publickey for check (userauth)
        12: bad signature (userauth)
        13: bad password (userauth)
        14: bad next service(userauth)
        """
        self.kind = failureKind # the type of failure this client should try
        if self.kind == 0:
            self.supportedKeyExchanges = []
        elif self.kind == 1:
            self.supportedPublicKeys = []
        elif self.kind == 2:
            self.supportedCiphers = []
        elif self.kind == 3:
            self.supportedMACs = []
        elif self.kind == 4:
            self.supportedCompressions = []

    def setPeer(self, peer):
        self.peer = peer
        if self.kind < 8:
            self.setPeerUpToDie()

    def setPeerUpToDie(self):
        self.peer.allowedToError = 1
        self.peer.expectedLoseConnection = 1
        self.expectedLoseConnection = 1

    def receiveError(self, reasonCode, desc):
        global theTest
        if self.kind in range(5):
            theTest.reactorRunning = 0
            theTest.assertEquals(reasonCode, transport.DISCONNECT_KEY_EXCHANGE_FAILED,
                                 '%s failed with %s instead of kex failed' %
                                     (self.kind, reasonCode))
        elif self.kind == 5:
            theTest.reactorRunning = 0
            theTest.assertEquals(reasonCode, transport.DISCONNECT_COMPRESSION_ERROR,
                                 '%s failed with %s instead of compression error' %
                                     (self.kind, reasonCode))
        elif self.kind == 6:
            theTest.reactorRunning = 0
            theTest.assertEquals(reasonCode, transport.DISCONNECT_PROTOCOL_ERROR,
                                 '%s failed with %s instead of protocol error' %
                                     (self.kind, reasonCode))
        elif self.kind == 7:
            theTest.reactorRunning = 0
            theTest.assertEquals(reasonCode, transport.DISCONNECT_MAC_ERROR,
                                 '%s failed with %s instead of MAC error' %
                                     (self.kind, reasonCode))
        else:
            SSHTestBase.receiveError(self, reasonCode, desc)

    def connectionSecure(self):
        class BadService:
            name = 'ssh-userauth' # yeah this is fake
            def serviceStarted(self):
                global theTest
                theTest.fail("got service connection when we should't have")
        if self.kind in range(5):
            global theTest
            theTest.fail('%s we have a secure connection, this is bad' % self.testOurServerOurClient)
            theTest.reactorRunning = 0
        elif self.kind == 5:
            class BadCompression:
                def compress(self, data):
                    return 'this is a bad compression'
                def flush(self, kind):
                    return 'this is also bad'
            self.outgoingCompression = BadCompression()
            self.setPeerUpToDie()
            self.sendIgnore('ignore this')
            self.requestService(BadService())
        elif self.kind == 6:
            class BadEncryption:
                def encrypt(self, blocks):
                    return '\00' * len(blocks)
            self.currentEncryptions.outCip = BadEncryption()
            self.setPeerUpToDie()
            self.sendIgnore('ignore this')
            self.requestService(BadService())
        elif self.kind == 7:
            class BadMAC:
                def __init__(self, real):
                    self.ds = real.digest_size
                def copy(self):
                    return self
                def update(self, data):
                    pass
                def digest(self):
                    print 'returning digest %s' % self.ds
                    return '\00' * self.ds
            self.currentEncryptions.outMAC = BadMAC(self.currentEncryptions.outMAC)
            self.setPeerUpToDie()
            #self.peer.allowedToError = 0 
            self.sendIgnore('ignore this')
            self.requestService(BadService())

class SSHTransportTestCase(unittest.TestCase):

    def setUp(self):
        open('rsa_test','w').write(privateRSA)
        open('rsa_test.pub','w').write(publicRSA)
        open('dsa_test.pub','w').write(publicDSA)
        open('dsa_test','w').write(privateDSA)

    def tearDown(self):
        for f in ['rsa_test','rsa_test.pub','dsa_test','dsa_test.pub']:
            os.remove(f)

    def testOurServerOurClient(self):
        global theTest
        theTest = self
        auth = ConchTestAuthorizer()
        ident = ConchTestIdentity('testuser', app.Application('conchtest'))
        auth.addIdentity(ident)
        fac = SSHTestFactory()
        fac.authorizer = auth
        client = SSHTestClient()
        reactor.listenTCP(66722, fac)
        reactor.clientTCP('localhost', 66722, client)
        self.reactorRunning = 1
        while self.reactorRunning:
            reactor.iterate(0.1)

    def testFailures(self):
        global theTest
        theTest = self
        auth = ConchTestAuthorizer()
        ident = ConchTestIdentity('testuser', app.Application('conchtest'))
        auth.addIdentity(ident)
        fac = SSHTestFactory()
        fac.authorizer = auth
        reactor.listenTCP(66722, fac)
        numFailureKinds = SSHFailureTestClient.numFailureKinds
        for k in range(numFailureKinds):
            client = SSHFailureTestClient(k)
            reactor.clientTCP('localhost', 66722, client)
            self.reactorRunning = 1
            reactor.iterate(0.1)
            client.setPeer(fac.proto)
            while self.reactorRunning:
                reactor.iterate(0.1)
            del fac.proto