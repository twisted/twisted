# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.hashlib}
"""
from twisted.trial.unittest import TestCase
from twisted.trial import util



class HashObjectTests(TestCase):
    """
    Tests for the hash object APIs presented by L{hashlib}, C{md5} and C{sha1}.
    """
    def test_deprecation(self):
        """
        Ensure the deprecation of L{twisted.python.hashlib} is working.
        """
        from twisted.python import hashlib
        warnings = self.flushWarnings(
                offendingFunctions=[self.test_deprecation])
        self.assertIdentical(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['message'],
                "twisted.python.hashlib was deprecated in "
                "Twisted 13.1.0: Please use hashlib from stdlib.")


    def test_md5(self):
        """
        L{hashlib.md5} returns an object which can be used to compute an MD5
        hash as defined by U{RFC 1321<http://www.ietf.org/rfc/rfc1321.txt>}.
        """
        from twisted.python.hashlib import md5

        # Test the result using values from section A.5 of the RFC.
        self.assertEqual(
            md5().hexdigest(), "d41d8cd98f00b204e9800998ecf8427e")
        self.assertEqual(
            md5("a").hexdigest(), "0cc175b9c0f1b6a831c399e269772661")
        self.assertEqual(
            md5("abc").hexdigest(), "900150983cd24fb0d6963f7d28e17f72")
        self.assertEqual(
            md5("message digest").hexdigest(),
            "f96b697d7cb7938d525a2f31aaf161d0")
        self.assertEqual(
            md5("abcdefghijklmnopqrstuvwxyz").hexdigest(),
            "c3fcd3d76192e4007dfb496cca67e13b")
        self.assertEqual(
            md5("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                "0123456789").hexdigest(),
            "d174ab98d277d9f5a5611c2c9f419d9f")
        self.assertEqual(
            md5("1234567890123456789012345678901234567890123456789012345678901"
                "2345678901234567890").hexdigest(),
            "57edf4a22be3c955ac49da2e2107b67a")

        # It should have digest and update methods, too.
        self.assertEqual(
            md5().digest().encode('hex'),
            "d41d8cd98f00b204e9800998ecf8427e")
        hash = md5()
        hash.update("a")
        self.assertEqual(
            hash.digest().encode('hex'),
            "0cc175b9c0f1b6a831c399e269772661")

        # Instances of it should have a digest_size attribute
        self.assertEqual(md5().digest_size, 16)
    test_md5.suppress = [util.suppress(message="twisted.python.hashlib"
          "was deprecated in Twisted 13.1.0: Please use hashlib from stdlib.")]


    def test_sha1(self):
        """
        L{hashlib.sha1} returns an object which can be used to compute a SHA1
        hash as defined by U{RFC 3174<http://tools.ietf.org/rfc/rfc3174.txt>}.
        """

        from twisted.python.hashlib import sha1

        def format(s):
            return ''.join(s.split()).lower()
        # Test the result using values from section 7.3 of the RFC.
        self.assertEqual(
            sha1("abc").hexdigest(),
            format(
                "A9 99 3E 36 47 06 81 6A BA 3E 25 71 78 50 C2 6C 9C D0 D8 9D"))
        self.assertEqual(
            sha1("abcdbcdecdefdefgefghfghighijhi"
                 "jkijkljklmklmnlmnomnopnopq").hexdigest(),
            format(
                "84 98 3E 44 1C 3B D2 6E BA AE 4A A1 F9 51 29 E5 E5 46 70 F1"))

        # It should have digest and update methods, too.
        self.assertEqual(
            sha1("abc").digest().encode('hex'),
            format(
                "A9 99 3E 36 47 06 81 6A BA 3E 25 71 78 50 C2 6C 9C D0 D8 9D"))
        hash = sha1()
        hash.update("abc")
        self.assertEqual(
            hash.digest().encode('hex'),
            format(
                "A9 99 3E 36 47 06 81 6A BA 3E 25 71 78 50 C2 6C 9C D0 D8 9D"))

        # Instances of it should have a digest_size attribute.
        self.assertEqual(
            sha1().digest_size, 20)
    test_sha1.suppress = [util.suppress(message="twisted.python.hashlib"
          "was deprecated in Twisted 13.1.0: Please use hashlib from stdlib.")]
