# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.python.randbytes}.
"""

import os, sys

from twisted.trial import unittest
from twisted.python import randbytes

try:
    from Crypto.Util import randpool
except ImportError:
    randpool = None



class SecureRandomTestCaseBase(object):
    """
    Base class for secureRandom test cases.
    """

    def _check(self, source):
        """
        The given random bytes source should return the number of bytes
        requested each time it is called and should probably not return the
        same bytes on two consecutive calls (although this is a perfectly
        legitimate occurrence and rejecting it may generate a spurious failure
        -- maybe we'll get lucky and the heat death with come first).
        """
        for nbytes in range(17, 25):
            s = source(nbytes)
            self.assertEquals(len(s), nbytes)
            s2 = source(nbytes)
            self.assertEquals(len(s2), nbytes)
            # This is crude but hey
            self.assertNotEquals(s2, s)



class SecureRandomTestCase(SecureRandomTestCaseBase, unittest.TestCase):
    """
    Test secureRandom under normal conditions.
    """

    def test_normal(self):
        """
        L{randbytes.secureRandom} should return a string of the requested
        length and make some effort to make its result otherwise unpredictable.
        """
        self._check(randbytes.secureRandom)



class ConditionalSecureRandomTestCase(SecureRandomTestCaseBase,
                                      unittest.TestCase):
    """
    Test random sources one by one, then remove it to.
    """

    def setUp(self):
        """
        Create a L{randbytes.RandomFactory} to use in the tests.
        """
        self.factory = randbytes.RandomFactory()


    def errorFactory(self, nbytes):
        """
        A factory raising an error when a source is not available.
        """
        raise randbytes.SourceNotAvailable()


    def test_osUrandom(self):
        """
        L{RandomFactory._osUrandom} should work as a random source whenever
        L{os.urandom} is available.
        """
        try:
            self._check(self.factory._osUrandom)
        except randbytes.SourceNotAvailable:
            # Not available on Python 2.3
            self.assertTrue(sys.version_info < (2, 4))


    def test_fileUrandom(self):
        """
        L{RandomFactory._fileUrandom} should work as a random source whenever
        C{/dev/urandom} is available.
        """
        try:
            self._check(self.factory._fileUrandom)
        except randbytes.SourceNotAvailable:
            # The test should only fail in /dev/urandom doesn't exist
            self.assertFalse(os.path.exists('/dev/urandom'))


    def test_cryptoRandom(self):
        """
        L{RandomFactory._cryptoRandom} should work as a random source whenever
        L{PyCrypto} is installed.
        """
        try:
            self._check(self.factory._cryptoRandom)
        except randbytes.SourceNotAvailable:
            # It fails if PyCrypto is not here
            self.assertIdentical(randpool, None)


    def test_withoutOsUrandom(self):
        """
        If L{os.urandom} is not available but L{PyCrypto} is,
        L{RandomFactory.secureRandom} should still work as a random source.
        """
        self.factory._osUrandom = self.errorFactory
        self._check(self.factory.secureRandom)

    if randpool is None:
        test_withoutOsUrandom.skip = "PyCrypto not available"


    def test_withoutOsAndFileUrandom(self):
        """
        Remove C{os.urandom} and /dev/urandom read.
        """
        self.factory._osUrandom = self.errorFactory
        self.factory._fileUrandom = self.errorFactory
        self._check(self.factory.secureRandom)

    if randpool is None:
        test_withoutOsAndFileUrandom.skip = "PyCrypto not available"


    def test_withoutAnything(self):
        """
        Remove all secure sources and assert it raises a failure. Then try the
        fallback parameter.
        """
        self.factory._osUrandom = self.errorFactory
        self.factory._fileUrandom = self.errorFactory
        self.factory._cryptoRandom = self.errorFactory
        self.assertRaises(randbytes.SecureRandomNotAvailable,
                          self.factory.secureRandom, 18)
        def wrapper():
            return self.factory.secureRandom(18, fallback=True)
        s = self.assertWarns(
            RuntimeWarning,
            "Neither PyCrypto nor urandom available - "
            "proceeding with non-cryptographically secure random source",
            __file__,
            wrapper)
        self.assertEquals(len(s), 18)



class RandomTestCaseBase(SecureRandomTestCaseBase, unittest.TestCase):
    """
    'Normal' random test cases.
    """

    def test_normal(self):
        """
        Test basic case.
        """
        self._check(randbytes.insecureRandom)


    def test_withoutGetrandbits(self):
        """
        Test C{insecureRandom} without C{random.getrandbits}.
        """
        factory = randbytes.RandomFactory()
        factory.getrandbits = None
        self._check(factory.insecureRandom)

