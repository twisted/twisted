# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""A Factory for SSH servers, along with an OpenSSHFactory to use the same data sources as OpenSSH.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import md5

try:
    import resource
except ImportError:
    resource = None

from twisted.internet import protocol
from twisted.python import log

from twisted.conch import error

import transport, userauth, connection

import random

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
            #if not self.primes:
            #    log.msg('disabling diffie-hellman-group-exchange because we cannot find moduli file')
            #    transport.SSHServerTransport.supportedKeyExchanges.remove('diffie-hellman-group-exchange-sha1')
            if self.primes:
                self.primesKeys = self.primes.keys()

    def buildProtocol(self, addr):
        t = transport.SSHServerTransport()
        t.supportedPublicKeys = self.privateKeys.keys()
        if not self.primes:
            ske = t.supportedKeyExchanges[:]
            ske.remove('diffie-hellman-group-exchange-sha1')
            t.supportedKeyExchanges = ske
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
        self.primesKeys.sort(lambda x,y,b=bits:cmp(abs(x-b), abs(x-b)))
        realBits = self.primesKeys[0]
        return random.choice(self.primes[realBits])

    def getService(self, transport, service):
        """
        Return a class to use as a service for the given transport.

        @type transport:    L{transport.SSHServerTransport}
        @type service:      C{stR}
        @rtype:             subclass of L{service.SSHService}
        """
        if transport.isAuthorized or service == 'ssh-userauth':
            return self.services[service]


