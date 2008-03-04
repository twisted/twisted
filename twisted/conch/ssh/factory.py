# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A Factory for SSH servers, along with an OpenSSHFactory to use the same
data sources as OpenSSH.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

try:
    import resource
except ImportError:
    resource = None

from twisted.internet import protocol
from twisted.python import log

from twisted.conch import error
import keys
import transport, userauth, connection

import random
import warnings

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
            warned = False
            for keyType, value in self.publicKeys.items():
                if isinstance(value, str):
                    if not warned:
                        warnings.warn("Returning a mapping from strings to "
                                "strings from getPublicKeys() is "
                                "deprecated.  Return a mapping from "
                                "strings to Key objects instead.",
                                DeprecationWarning, stacklevel=2)
                        warned = True
                    self.publicKeys[keyType] = keys.Key.fromString(value)
        if not hasattr(self,'privateKeys'):
            self.privateKeys = self.getPrivateKeys()
            warned = False
            for keyType, value in self.privateKeys.items():
                if not isinstance(value, keys.Key):
                    if not warned:
                        warnings.warn("Returning a mapping from strings to "
                                "PyCrypto key objects from getPrivateKeys() "
                                "is deprecated.  Return a mapping from "
                                "strings to Key objects instead.",
                                DeprecationWarning, stacklevel=2)
                        warned = True
                    self.privateKeys[keyType] = keys.Key(value)
        if not self.publicKeys or not self.privateKeys:
            raise error.ConchError('no host keys, failing')
        if not hasattr(self,'primes'):
            self.primes = self.getPrimes()

    def buildProtocol(self, addr):
        t = transport.SSHServerTransport()
        t.supportedPublicKeys = self.privateKeys.keys()
        if not self.primes:
            log.msg('disabling diffie-hellman-group-exchange because we '
                    'cannot find moduli file')
            ske = t.supportedKeyExchanges[:]
            ske.remove('diffie-hellman-group-exchange-sha1')
            t.supportedKeyExchanges = ske
        t.factory = self
        return t

    def getPublicKeys(self):
        """
        Called when the factory is started to get the public portions of the
        servers host keys.  Returns a dictionary mapping SSH key types to
        public key strings.

        @rtype: C{dict}
        """
        raise NotImplementedError('getPublicKeys unimplemented')

    def getPrivateKeys(self):
        """
        Called when the factory is started to get the  private portions of the
        servers host keys.  Returns a dictionary mapping SSH key types to
        C{Crypto.PublicKey.pubkey.pubkey} objects.

        @rtype: C{dict}
        """
        raise NotImplementedError('getPrivateKeys unimplemented')

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
        primesKeys = self.primes.keys()
        primesKeys.sort(lambda x, y: cmp(abs(x - bits), abs(y - bits)))
        realBits = primesKeys[0]
        return random.choice(self.primes[realBits])

    def getService(self, transport, service):
        """
        Return a class to use as a service for the given transport.

        @type transport:    L{transport.SSHServerTransport}
        @type service:      C{str}
        @rtype:             subclass of L{service.SSHService}
        """
        if service == 'ssh-userauth' or hasattr(transport, 'avatar'):
            return self.services[service]
