import md5, os

from twisted.internet import protocol

import common, userauth, keys, transport, primes, connection

class Nothing: pass
class SSHFactory(protocol.Factory):
    services = {
        'ssh-userauth':userauth.SSHUserAuthServer,
        'ssh-connection':connection.SSHConnection
    }
    def startFactory(self):
        if not hasattr(self,'publicKeys'):
            self.publicKeys = self.getPublicKey()
        if not hasattr(self,'privateKeys'):
            self.privateKeys = self.getPrivateKey()
        if not hasattr(self,'primes'):
            self.primes = self.getPrimes()

    def buildProtocol(self, addr):
        t = transport.SSHServerTransport()
        t.supportedPublicKeys = self.privateKeys.keys()
        t.factory = self
        return t

    def getFingerprint(self):
        return ':'.join(map(lambda c:'%02x'%ord(c),md5.new(self.publicKey).digest()))

    def getDHPrime(self, bits):
        # returns g, p
        return primes.getDHPrimeOfBits(self.primes, bits)

class OpenSSHFactory(SSHFactory):
    dataRoot = '/usr/local/etc'
    def getPublicKey(self):
        ks = {}
        for file in os.listdir(self.dataRoot):
            if file[:9] == 'ssh_host_' and file[-8:]=='_key.pub':
                try:
                    k = keys.getPublicKeyString(self.dataRoot+'/'+file)
                    t = common.getNS(k)[0]
                    ks[t] = k
                except:
                    print 'bad key file', file
        return ks
    def getPrivateKey(self):
        ks = {}
        for file in os.listdir(self.dataRoot):
            if file[:9] == 'ssh_host_' and file[-4:]=='_key':
                try:
                    k = keys.getPrivateKeyObject(self.dataRoot+'/'+file)
                    t = keys.objectType(k)
                    ks[t] = k
                except:
                    print 'bad key file', file
        return ks
    def getPrimes(self):
        return primes.parseModuliFile(self.dataRoot+'/moduli')
