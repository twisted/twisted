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
import md5, os

from twisted.internet import protocol
from twisted.python import log

import common, userauth, keys, transport, primes, connection

class SSHFactory(protocol.Factory):
    services = {
        'ssh-userauth':userauth.SSHUserAuthServer,
        'ssh-connection':connection.SSHConnection
    }
    def startFactory(self):
        if not hasattr(self,'publicKeys'):
            self.publicKeys = self.getPublicKeys()
        if not hasattr(self,'privateKeys'):
            self.privateKeys = self.getPrivateKeys()
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

    def getService(self, transport, service):
        if transport.isAuthorized or service == 'ssh-userauth':
            return self.services[service]

class OpenSSHFactory(SSHFactory):
    dataRoot = '/usr/local/etc'
    def getPublicKeys(self):
        ks = {}
        for file in os.listdir(self.dataRoot):
            if file[:9] == 'ssh_host_' and file[-8:]=='_key.pub':
                try:
                    k = keys.getPublicKeyString(self.dataRoot+'/'+file)
                    t = common.getNS(k)[0]
                    ks[t] = k
                except:
                    log.msg('bad public key file %s' % file)
        return ks
    def getPrivateKeys(self):
        ks = {}
        for file in os.listdir(self.dataRoot):
            if file[:9] == 'ssh_host_' and file[-4:]=='_key':
                try:
                    k = keys.getPrivateKeyObject(self.dataRoot+'/'+file)
                    t = keys.objectType(k)
                    ks[t] = k
                except:
                    log.msg('bad private key file %s' % file)
        return ks
    def getPrimes(self):
        return primes.parseModuliFile(self.dataRoot+'/moduli')
