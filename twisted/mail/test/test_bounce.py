# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Test cases for bounce message generation
"""

from twisted.trial import unittest
from twisted.mail import bounce
import rfc822, cStringIO

class BounceTests(unittest.TestCase):
    """
    testcases for bounce message generation
    """

    def testBounceFormat(self):
        from_, to, s = bounce.generateBounce(cStringIO.StringIO('''\
From: Moshe Zadka <moshez@example.com>
To: nonexistent@example.org
Subject: test

'''), 'moshez@example.com', 'nonexistent@example.org')
        self.assertEqual(from_, '')
        self.assertEqual(to, 'moshez@example.com')
        mess = rfc822.Message(cStringIO.StringIO(s))
        self.assertEqual(mess['To'], 'moshez@example.com')
        self.assertEqual(mess['From'], 'postmaster@example.org')
        self.assertEqual(mess['subject'], 'Returned Mail: see transcript for details')

    def testBounceMIME(self):
        pass
