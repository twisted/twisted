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

"""A Factory for SSH servers, along with an OpenSSHFactory to use the same data sources as OpenSSH.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import md5, os

try:
    import resource
except ImportError:
    resource = None

try:
    import PAM
except:
    pass
else: # PAM requires threading
    from twisted.python import threadable
    threadable.init(1)

from twisted.internet import protocol
from twisted.python import log

import common, keys, transport, primes, connection, userauth
from twisted.conch import error

class SSHFactory(protocol.Factory):
    services = {
        'ssh-userauth':userauth.SSHUserAuthServer,
        'ssh-connection':connection.SSHConnection
    }
    def startFactory(self):
        # disable coredumps
        if resource:
            resource.setrlimit(resource.RLIMIT_CORE, (0,0))
        else:
            log.msg('INSECURE: unable to disable core dumps.')
        if not hasattr(self,'publicKeys'):
            self.publicKeys = self.getPublicKeys()
        if not hasattr(self,'privateKeys'):
            self.privateKeys = self.getPrivateKeys()
        if not self.publicKeys or not self.privateKeys:
            raise error.ConchError('no host keys, failing')
        if not hasattr(self,'primes'):
            self.primes = self.getPrimes()
            if not self.primes:
                log.msg('disabling diffie-hellman-group-exchange because we cannot find moduli file')
                transport.SSHServerTransport.supportedKeyExchanges.remove('diffie-hellman-group-exchange-sha1')

    def buildProtocol(self, addr):
        t = transport.SSHServerTransport()
        t.supportedPublicKeys = self.privateKeys.keys()
        #if not self.primes:
        #    t.supportedKeyExchanges.remove('diffie-hellman-group-exchange-sha1')
        t.factory = self
        return t

    def getPublicKeys(self):
        """
        Called when the factory is started to get the public portions of the 
        servers host keys.  Returns a dictionary mapping SSH key types  to 
        public key strings.

        @rtype: C{dict}
        """
        raise NotImplementedError

    def getPrivateKeys(self):
        """
        Called when the factory is started to get the  private portions of the 
        servers host keys.  Returns a dictionary mapping SSH key types to 
        C{Crypto.PublicKey.pubkey.pubkey} objects.

        @rtype: C{dict}
        """
        raise NotImplementedError

    def getPrimes(self):
        """
        Called when the factory is started to get Diffie-Hellman generators and
        primes to use.  Returns a dictionary mapping number of bits to lists
        of tuple of (generator, prime).

        @rtype: C{dict}
        """

    def getDHPrime(self, bits):
        """
        Return a tuple of (g, p) for a Diffe-Hellman process, with p being as
        close to bits bits as possible.

        @type bits: C{int}
        @rtype:     C{tuple}
        """
        return primes.getDHPrimeOfBits(self.primes, bits)

    def getService(self, transport, service):
        """
        Return a class to use as a service for the given transport.

        @type transport:    C{transport.SSHServerTransport}
        @type service:      C{stR}
        @rtype:             subclass of {service.SSHService}
        """
        if transport.isAuthorized or service == 'ssh-userauth':
            return self.services[service]

class OpenSSHFactory(SSHFactory):
    dataRoot = '/usr/local/etc'
    moduliRoot = '/usr/local/etc' # for openbsd which puts moduli in a different
                                  # directory from keys
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
        try:
            return primes.parseModuliFile(self.moduliRoot+'/moduli')
        except IOError:
            return None

