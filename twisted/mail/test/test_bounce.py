# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Test cases for bounce message generation
"""

from twisted.trial import unittest
from twisted.mail import bounce
import rfc822, cStringIO

class BounceTestCase(unittest.TestCase):
    """
    testcases for bounce message generation
    """

    def testBounceFormat(self):
        from_, to, s = bounce.generateBounce(cStringIO.StringIO('''\
From: Moshe Zadka <moshez@example.com>
To: nonexistant@example.org
Subject: test

'''), 'moshez@example.com', 'nonexistant@example.org')
        self.assertEquals(from_, '')
        self.assertEquals(to, 'moshez@example.com')
        mess = rfc822.Message(cStringIO.StringIO(s))
        self.assertEquals(mess['To'], 'moshez@example.com')
        self.assertEquals(mess['From'], 'postmaster@example.org')
        self.assertEquals(mess['subject'], 'Returned Mail: see transcript for details')

    def testBounceMIME(self):
        pass
