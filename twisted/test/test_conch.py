
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
from twisted.internet import reactor, defer
from twisted.conch import keys, transport, factory, userauth
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


class ConchKeysHandlingTestCase(unittest.TestCase):
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



class SSHTestBase:

    def connectionLost(self):
        if not hasattr(self,'expectedLoseConnection'):
            self.test.fail('unexpectedly lost connection')
        self.test.reactorRunning = 0

    def receiveError(self, reasonCode, desc):
        self.test.fail('got disconnect: reason %s, desc: %s' %
                       (reasonCode, desc))
        self.test.reactorRunning = 0

    def receiveUnimplemented(self, seqID):
        self.test.fail('got unimplemented: seqid %s'  % seqID)
        self.test.reactorRunning = 0


class SSHTestServer(SSHTestBase, transport.SSHServerTransport): pass

class SSHTestServerAuth(userauth.SSHUserAuthServer):

    def areDone(self):
        #self.tranport.factory.services['ssh-connection'] = SSHTestConnection
        return len(self.authenticatedWith)==2

    def isValidKeyFor(self, user, pubKey):
        self.transport.factory.test.assert_(user=='testuser','bad username')
        self.transport.factory.test.assert_(pubKey==keys.getPublicKeyString('dsa_test.pub'), 'bad public key')
        return 1

    def verifyPassword(self,user, password):
        self.transport.factory.test.assert_(user=='testuser','bad username')
        self.transport.factory.test.assert_(password=='testpass','bad password')
        return 1

class SSHTestClientAuth(userauth.SSHUserAuthClient):
    
    def getPassword(self):
        return defer.succeed('testpass')

    def getPrivateKey(self):
        return keys.getPrivateKeyObject('dsa_test')

    def getPublicKey(self):
        return keys.getPublicKeyString('dsa_test.pub')

class SSHTestClient(SSHTestBase, transport.SSHClientTransport):

    def checkFingerprint(self, fp):
        self.test.assertEquals(fp,'34:f1:6f:02:29:ad:17:f9:8f:96:8a:9b:94:c7:49:43')
        return 1

    def connectionSecure(self):
        self.requestService(SSHTestClientAuth('testuser',SSHTestConnection()))

class SSHTestConnection:

    name = 'ssh-connection'

    def serviceStarted(self):
        #self.transport.expectedLostConnection = 1
        if not hasattr(self.transport, 'factory'):
            # make the client end the connection
            self.transport.test.reactorRunning = 0

class SSHTestFactory(factory.SSHFactory):

    services = {
        'ssh-userauth':SSHTestServerAuth,
        'ssh-connection':SSHTestConnection
    }

    def buildProtocol(self, addr):
        if hasattr(self, 'proto'):
            self.test.fail('connected twice to factory')
        self.proto = SSHTestServer()
        self.proto.supportedPublicKeys = self.privateKeys.keys()
        self.proto.test = self.test
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

class ConchTransportTest(unittest.TestCase):

    def setUp(self):
        open('rsa_test','w').write(privateRSA)
        open('rsa_test.pub','w').write(publicRSA)
        open('dsa_test.pub','w').write(publicDSA)
        open('dsa_test','w').write(privateDSA)

    def tearDown(self):
        for f in ['rsa_test','rsa_test.pub','dsa_test','dsa_test.pub']:
            os.remove(f)

    def testOurServerOurClient(self):
        fac = SSHTestFactory()
        fac.test = self
        client = SSHTestClient()
        client.test = self
        client.serverfac = fac
        reactor.listenTCP(66722, fac)
        reactor.clientTCP('localhost', 66722, client)
        self.reactorRunning = 1
        while self.reactorRunning:
            reactor.iterate(0.1)