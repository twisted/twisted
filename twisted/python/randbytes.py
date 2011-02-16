# -*- test-case-name: twisted.test.test_randbytes -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Cryptographically secure random implementation, with fallback on normal random.
"""

# System imports
import warnings, os, random

getrandbits = getattr(random, 'getrandbits', None)


class SecureRandomNotAvailable(RuntimeError):
    """
    Exception raised when no secure random algorithm is found.
    """



class SourceNotAvailable(RuntimeError):
    """
    Internal exception used when a specific random source is not available.
    """



class RandomFactory(object):
    """
    Factory providing L{secureRandom} and L{insecureRandom} methods.

    You shouldn't have to instantiate this class, use the module level
    functions instead: it is an implementation detail and could be removed or
    changed arbitrarily.

    @cvar randomSources: list of file sources used when os.urandom is not
        available.
    @type randomSources: C{tuple}
    """
    randomSources = ('/dev/urandom',)
    getrandbits = getrandbits


    def _osUrandom(self, nbytes):
        """
        Wrapper around C{os.urandom} that cleanly manage its absence.
        """
        try:
            return os.urandom(nbytes)
        except (AttributeError, NotImplementedError), e:
            raise SourceNotAvailable(e)


    def _fileUrandom(self, nbytes):
        """
        Wrapper around random file sources.

        This method isn't meant to be call out of the class and could be
        removed arbitrarily.
        """
        for src in self.randomSources:
            try:
                f = file(src, 'rb')
            except (IOError, OSError):
                pass
            else:
                bytes = f.read(nbytes)
                f.close()
                return bytes
        raise SourceNotAvailable("File sources not available: %s" %
                                 (self.randomSources,))


    def secureRandom(self, nbytes, fallback=False):
        """
        Return a number of secure random bytes.

        @param nbytes: number of bytes to generate.
        @type nbytes: C{int}
        @param fallback: Whether the function should fallback on non-secure
            random or not.  Default to C{False}.
        @type fallback: C{bool}

        @return: a string of random bytes.
        @rtype: C{str}
        """
        for src in ("_osUrandom", "_fileUrandom"):
            try:
                return getattr(self, src)(nbytes)
            except SourceNotAvailable:
                pass
        if fallback:
            warnings.warn(
                "urandom unavailable - "
                "proceeding with non-cryptographically secure random source",
                category=RuntimeWarning,
                stacklevel=2)
            return self.insecureRandom(nbytes)
        else:
            raise SecureRandomNotAvailable("No secure random source available")


    def _randBits(self, nbytes):
        """
        Wrapper around C{os.getrandbits}.
        """
        if self.getrandbits is not None:
            n = self.getrandbits(nbytes * 8)
            hexBytes = ("%%0%dx" % (nbytes * 2)) % n
            return hexBytes.decode('hex')
        raise SourceNotAvailable("random.getrandbits is not available")


    def _randRange(self, nbytes):
        """
        Wrapper around C{random.randrange}.
        """
        bytes = ""
        for i in xrange(nbytes):
            bytes += chr(random.randrange(0, 255))
        return bytes


    def insecureRandom(self, nbytes):
        """
        Return a number of non secure random bytes.

        @param nbytes: number of bytes to generate.
        @type nbytes: C{int}

        @return: a string of random bytes.
        @rtype: C{str}
        """
        for src in ("_randBits", "_randRange"):
            try:
                return getattr(self, src)(nbytes)
            except SourceNotAvailable:
                pass



factory = RandomFactory()

secureRandom = factory.secureRandom

insecureRandom = factory.insecureRandom

del factory


__all__ = ["secureRandom", "insecureRandom", "SecureRandomNotAvailable"]
